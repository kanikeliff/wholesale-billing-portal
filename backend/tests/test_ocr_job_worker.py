
import tempfile
import json
import json
from pathlib import Path
from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.billing.models import BillingRecord
from apps.persistence.models import OCRJob, Document
from application.services.document_file_service import DocumentFileService
from application.services.ocr_job_worker import OCRJobWorker
from apps.persistence.models import ExtractedField, AuditEvent

class OCRJobWorkerTests(TestCase):

    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)

        settings_override = override_settings(
            MEDIA_ROOT=temporary_directory.name
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.record = BillingRecord.objects.create(status="UPLOADED")

        from uuid import uuid4

        document_id = uuid4()

        DocumentFileService().store_uploaded_document(
            record_id=self.record.record_id,
            document_id=document_id,
            original_filename="sample.pdf",
            file_bytes=b"%PDF-1.4\nmock pdf content",
            mime_type="application/pdf",
        )

        self.document = Document.objects.get(document_id=document_id)

        self.job = OCRJob.objects.create(document=self.document)

        self.extractor = Mock(
            return_value={
                "bol_number": "BOL-100",
                "origin": "Syracuse",
                "transaction_date": "2026-09-17",
                "products": [
                    {
                        "product": "ULSD",
                        "net_gallons": "8500",
                        "gross_gallons": "8550",
                    }
                ],
            }
        )

        self.worker = OCRJobWorker(extractor=self.extractor)
    def test_worker_completes_job(self):
        result = self.worker.process_next_job()

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        # OCR job completed successfully.
        self.assertEqual(
            self.job.status,
            OCRJob.Status.COMPLETED,
        )
        self.assertEqual(self.job.attempt_count, 1)

        # The original BillingRecord was updated.
        self.assertEqual(self.record.status, "OCR_COMPLETE")
        self.assertEqual(self.record.bol_number, "BOL-100")

        self.assertEqual(
            result["recordId"],
            str(self.record.record_id),
        )

        # OCR must not create a duplicate BillingRecord.
        self.assertEqual(BillingRecord.objects.count(), 1)

        # Extracted fields must be persisted in PostgreSQL.
        extracted_fields = ExtractedField.objects.filter(
            billing_record=self.record,
            document=self.document,
        )

        self.assertGreater(
            extracted_fields.count(),
            0,
        )

        # Verify the BOL number field was saved.
        bol_field = extracted_fields.get(
            field_name="bolNumber",
        )

        self.assertEqual(
           bol_field.normalized_value,
            "BOL-100",
        )

        # Verify the audit event was created.
        audit_event = AuditEvent.objects.get(
            billing_record=self.record,
            event_type="OCR_COMPLETED",
        )

        self.assertEqual(
            audit_event.metadata["documentId"],
            str(self.document.document_id),
        )

        self.assertEqual(
           audit_event.metadata["extractedFieldCount"],
            extracted_fields.count(),
        )

        self.extractor.assert_called_once()

    def test_future_retry_job_is_not_claimed(self):
        self.job.status = OCRJob.Status.RETRY_PENDING
        self.job.next_retry_at = (
            timezone.now() + timedelta(hours=1)
        )
        self.job.save()

        result = self.worker.process_next_job()

        self.assertIsNone(result)
        self.extractor.assert_not_called()

        self.job.refresh_from_db()
        self.assertEqual(self.job.attempt_count, 0)

    def test_failed_extraction_schedules_retry(self):
        self.extractor.side_effect = TimeoutError("OCR timeout")

        with self.assertRaises(TimeoutError):
            self.worker.process_next_job()

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        self.assertEqual(self.job.status, OCRJob.Status.RETRY_PENDING)
        self.assertEqual(self.job.attempt_count, 1)
        self.assertIsNotNone(self.job.next_retry_at)
        self.assertEqual(self.record.status, "OCR_PROCESSING")

    def test_exhausted_attempts_moves_record_to_exception(self):
        self.job.max_attempts = 1
        self.job.save()

        self.extractor.side_effect = RuntimeError("OCR unavailable")

        with self.assertRaises(RuntimeError):
            self.worker.process_next_job()

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        self.assertEqual(self.job.status, OCRJob.Status.FAILED)
        self.assertEqual(self.job.attempt_count, 1)
        self.assertEqual(self.record.status, "EXCEPTION")
        self.assertIsNone(self.job.next_retry_at)

    def test_stale_job_is_scheduled_for_retry(self):
        self.job.status = OCRJob.Status.PROCESSING
        self.job.attempt_count = 1
        self.job.started_at = (
            timezone.now() - timedelta(minutes=20)
        )
        self.job.save()

        self.record.status = "OCR_PROCESSING"
        self.record.save()

        recovered = self.worker.recover_stale_jobs(
            timeout_minutes=10
        )

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        self.assertEqual(recovered, 1)
        self.assertEqual(
            self.job.status,
            OCRJob.Status.RETRY_PENDING,
        )
        self.assertIsNotNone(self.job.next_retry_at)
        self.assertEqual(self.job.error_code, "WORKER_TIMEOUT")
        self.assertEqual(self.record.status, "OCR_PROCESSING")

    def test_stale_job_with_no_attempts_left_fails(self):
        self.job.status = OCRJob.Status.PROCESSING
        self.job.attempt_count = 3
        self.job.max_attempts = 3
        self.job.started_at = (
            timezone.now() - timedelta(minutes=20)
        )
        self.job.save()

        self.record.status = "OCR_PROCESSING"
        self.record.save()

        recovered = self.worker.recover_stale_jobs(
            timeout_minutes=10
        )

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        self.assertEqual(recovered, 1)
        self.assertEqual(self.job.status, OCRJob.Status.FAILED)
        self.assertEqual(self.record.status, "EXCEPTION")
        self.assertIsNone(self.job.next_retry_at)
    
    def test_obsolete_attempt_cannot_overwrite_new_attempt(self):
        def delayed_extractor(**kwargs):
            # Simulate recovery while the original extractor runs.
            OCRJob.objects.filter(job_id=self.job.job_id).update(
                started_at=timezone.now() - timedelta(minutes=20)
            )

            recovered = self.worker.recover_stale_jobs(
                timeout_minutes=10
            )
            self.assertEqual(recovered, 1)

            # Another worker claims the recovered job.
            new_job_id = self.worker.claim_next_job()
            self.assertEqual(new_job_id, self.job.job_id)

            return {
                "bol_number": "STALE-RESULT",
                "origin": "Syracuse",
                "transaction_date": "2026-09-17",
                "products": [
                    {
                        "product": "ULSD",
                        "net_gallons": "8500",
                        "gross_gallons": "8550",
                    }
                ],
            }

        self.extractor.side_effect = delayed_extractor

        result = self.worker.process_next_job()

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        self.assertIsNone(result)
        self.assertEqual(self.job.attempt_count, 2)
        self.assertEqual(self.job.status, OCRJob.Status.PROCESSING)
        self.assertEqual(self.record.status, "OCR_PROCESSING")
        self.assertIsNone(self.record.bol_number)
        self.assertEqual(BillingRecord.objects.count(), 1)

    def test_ocr_verification_flags_require_human_review(self):
        extraction = self.extractor.return_value

        self.extractor.return_value = {
            "extraction": extraction,
            "ocrReviewFlags": [
                {"code": "LOW_CONFIDENCE"}
            ],
            "verification": {
                "reviewRequired": True
            },
        }

        result = self.worker.process_next_job()

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        self.assertEqual(self.job.status, OCRJob.Status.COMPLETED)
        self.assertEqual(self.record.status, "NEEDS_REVIEW")
        self.assertEqual(result["status"], "NEEDS_REVIEW")

        self.assertEqual(
            self.job.raw_result["verification"]["reviewRequired"],
            True,
        )
        self.assertEqual(
            len(self.job.raw_result["ocrReviewFlags"]),
            1,
        )
        



    def test_saved_real_ocr_result_persists_correctly(self):
        fixture_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "ocr_samples"
            / "Sample_BOL_1_ocr_result.json"
        )

        with fixture_path.open("r", encoding="utf-8") as file:
            ocr_result = json.load(file)

        # Replay a saved real OCR response.
        # This test does not make an external OCR API call.
        self.extractor.return_value = ocr_result

        result = self.worker.process_next_job()

        self.job.refresh_from_db()
        self.record.refresh_from_db()

        # Verify job completion and human-review routing.
        self.assertEqual(
            self.job.status,
            OCRJob.Status.COMPLETED,
        )
        self.assertEqual(self.record.status, "NEEDS_REVIEW")
        self.assertEqual(self.job.attempt_count, 1)

        # Verify normalized billing data.
        self.assertEqual(self.record.bol_number, "0000813492")
        self.assertEqual(
            self.record.supplier,
            "VALERO MARKETING & SUPPLY",
        )
        self.assertEqual(self.record.carrier, "JP NOONAN")

        # No duplicate billing record.
        self.assertEqual(BillingRecord.objects.count(), 1)

        # Seven BOL fields and four line-item fields.
        fields = ExtractedField.objects.filter(
            billing_record=self.record,
            document=self.document,
        )

        self.assertEqual(fields.count(), 11)

        self.assertEqual(
            fields.get(field_name="bolNumber").normalized_value,
            "0000813492",
        )
        self.assertEqual(
            str(fields.get(field_name="netGallons").normalized_value),
            "6939.0",
        )
        self.assertEqual(
            str(fields.get(field_name="grossGallons").normalized_value),
            "7000.0",
        )

        # Missing information must remain unresolved.
        self.assertEqual(
            fields.get(field_name="e3StockId").quality,
            ExtractedField.Quality.MISSING,
        )

        # The original OCR response must be preserved.
        self.assertEqual(self.job.raw_result, ocr_result)

        # Verify audit event and its source metadata.
        audit_event = AuditEvent.objects.get(
            billing_record=self.record,
            event_type="OCR_COMPLETED",
        )

        self.assertEqual(
            audit_event.metadata["documentId"],
            str(self.document.document_id),
        )
        self.assertEqual(
            audit_event.metadata["extractedFieldCount"],
            fields.count(),
        )
        self.assertEqual(
            audit_event.metadata["source"],
            "ocr_pipeline",
        )

        # Every extracted field must have the same source.
        self.assertTrue(
            all(
                field.metadata["source"] == "ocr_pipeline"
                for field in fields
            )
        )

        self.assertEqual(
            result["recordId"],
            str(self.record.record_id),
        )
        self.extractor.assert_called_once()
