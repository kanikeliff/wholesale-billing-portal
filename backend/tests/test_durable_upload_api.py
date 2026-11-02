
import tempfile

from django.contrib.auth.models import User

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.billing.models import BillingRecord
from apps.persistence.models import Document, OCRJob


class DurableUploadAPITests(APITestCase):

    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)

        settings_override = override_settings(
            MEDIA_ROOT=temporary_directory.name
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.url = "/api/v1/billing-records/upload/"

        self.client.force_authenticate(
            user=User(username="test-reviewer")
        )

    def test_sample_upload_worker_review_and_multiple_corrections(self):
        from pathlib import Path
        from unittest.mock import patch
        from django.core.management import call_command
        from apps.persistence.models import AuditEvent

        sample = Path(__file__).parent / "fixtures/ocr_samples/Sample_BOL_1.pdf"
        response = self.client.post(self.url, {"file": SimpleUploadedFile(
            "renamed.pdf", sample.read_bytes(), content_type="application/pdf"
        )}, format="multipart")
        self.assertEqual(response.status_code, 201)
        uploaded = response.json()
        detail_url = f"/api/v1/billing-records/{uploaded['recordId']}/"
        self.assertEqual(self.client.get(detail_url).json()["status"], "UPLOADED")
        # The command normally closes connections between jobs; this API test
        # deliberately shares Django TestCase's enclosing transaction.
        with patch("apps.persistence.management.commands.run_ocr_worker.close_old_connections"):
            call_command("run_ocr_worker", once=True, job_id=uploaded["jobId"])
        job = OCRJob.objects.get(job_id=uploaded["jobId"])
        self.assertEqual(job.status, "COMPLETED", job.error_message)
        data = self.client.get(detail_url).json()
        self.assertIn(data["status"], ["OCR_COMPLETE", "NEEDS_REVIEW"])
        for field in data["fields"].values():
            self.assertIsNone(field["confidence"])
        missing = [field for field in data["fields"].values() if field["quality"] == "MISSING"]
        self.assertTrue(missing)
        self.assertTrue(all(field["normalizedValue"] is None for field in missing))
        original = data["fields"]["carrier"]["rawValue"]
        for field, value in [("carrier", "Reviewed carrier"), ("destination", "Reviewed destination")]:
            correction = self.client.patch(
                f"{detail_url}fields/{field}/", {"value": value}, format="json"
            )
            self.assertEqual(correction.status_code, 200, correction.data)
        refreshed = self.client.get(detail_url).json()
        self.assertEqual(refreshed["fields"]["carrier"]["normalizedValue"], "Reviewed carrier")
        self.assertEqual(refreshed["fields"]["destination"]["normalizedValue"], "Reviewed destination")
        self.assertEqual(refreshed["fields"]["carrier"]["rawValue"], original)
        self.assertIsNone(refreshed["fields"]["carrier"]["confidence"])
        self.assertEqual(AuditEvent.objects.filter(
            billing_record_id=uploaded["recordId"], event_type="FIELD_CORRECTION"
        ).count(), 2)

    def test_upload_creates_pending_ocr_job(self):
        uploaded_file = SimpleUploadedFile(
            "sample.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {"file": uploaded_file},
            format="multipart",
        )
        print("UPLOAD RESPONSE:", response.status_code, response.json()) 
        self.assertEqual(response.status_code, 201)

        data = response.json()

        self.assertEqual(data["status"], "UPLOADED")
        self.assertEqual(data["ocrStatus"], "PENDING")

        self.assertIn("recordId", data)
        self.assertIn("documentId", data)
        self.assertIn("jobId", data)

        record = BillingRecord.objects.get(
            record_id=data["recordId"]
        )

        document = Document.objects.get(
            document_id=data["documentId"]
        )

        job = OCRJob.objects.get(
            job_id=data["jobId"]
        )

        self.assertEqual(record.status, "UPLOADED")
        self.assertEqual(
            document.billing_record_id,
            record.record_id,
        )
        self.assertEqual(job.document_id, document.document_id)
        self.assertEqual(job.status, OCRJob.Status.PENDING)

        self.assertEqual(BillingRecord.objects.count(), 1)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(OCRJob.objects.count(), 1)

    def test_upload_without_file_returns_400(self):
        response = self.client.post(
            self.url,
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["code"],
            "FILE_REQUIRED",
        )
        self.assertEqual(BillingRecord.objects.count(), 0)
        self.assertEqual(OCRJob.objects.count(), 0)


    def test_anonymous_upload_returns_403(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.url,
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(BillingRecord.objects.count(), 0)
        self.assertEqual(OCRJob.objects.count(), 0)
