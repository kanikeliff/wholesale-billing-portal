"""Offline bridge tests using the OCR team's recorded, provenance-labeled pilot.

The extractor is mocked; these are not new live OCR results.
"""
import copy
import hashlib
import importlib.metadata
import json
import os
from decimal import Decimal
from pathlib import Path
import tempfile
from unittest import skipUnless
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from apps.billing.models import BillingRecord
from apps.persistence.models import AuditEvent, ExtractedField, OCRJob
from application.services.ocr_job_worker import OCRJobWorker
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter
from infrastructure.ocr.live_ocr_client import LiveOCRClient, LiveOCRError
from infrastructure.ocr.runtime_configuration import (
    OCRRuntimeUnavailable, is_numeric_confidence_enabled,
)

try:
    HAS_CONFIDENCE_PACKAGE = importlib.metadata.version("mirabito-ocr") == "0.3.0"
except importlib.metadata.PackageNotFoundError:
    HAS_CONFIDENCE_PACKAGE = False

FIXTURES = Path(__file__).parent / "fixtures/ocr_samples"


class NumericConfidenceSettingTests(SimpleTestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_legacy_mode_is_the_default(self):
        self.assertFalse(is_numeric_confidence_enabled())

    @patch.dict(os.environ, {"OCR_INCLUDE_CONFIDENCE": "true"})
    def test_numeric_mode_requires_explicit_opt_in(self):
        self.assertTrue(is_numeric_confidence_enabled())

    @patch.dict(os.environ, {"OCR_INCLUDE_CONFIDENCE": "typo"})
    def test_invalid_opt_in_is_rejected(self):
        with self.assertRaises(OCRRuntimeUnavailable):
            is_numeric_confidence_enabled()


@skipUnless(HAS_CONFIDENCE_PACKAGE, "Install the pinned OCR 0.3.0 package for numeric bridge tests.")
class NumericConfidenceBridgeTests(APITestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_authenticate(user=User(username="test-reviewer"))
        self.numeric = json.loads((FIXTURES / "Sample_BOL_3_numeric_certainty.json").read_text())
        self.legacy_record = BillingRecord.objects.create(status="NEEDS_REVIEW")
        self.legacy_field = ExtractedField.objects.create(
            billing_record=self.legacy_record, field_name="bolNumber",
            raw_value="LEGACY", normalized_value="LEGACY", confidence=None,
        )

    def upload_job(self):
        pdf = (FIXTURES / "Sample_BOL_3.pdf").read_bytes()
        with patch.dict(os.environ, {"OCR_PROVIDER": "live"}), patch(
            "application.services.durable_bol_upload_service.ensure_live_worker_ready"
        ):
            response = self.client.post("/api/v1/billing-records/upload/", {
                "file": SimpleUploadedFile("Sample_BOL_3.pdf", pdf, content_type="application/pdf"),
            }, format="multipart")
        self.assertEqual(response.status_code, 201)
        return OCRJob.objects.get(pk=response.data["jobId"])

    def complete_job(self, result=None):
        job = self.upload_job()
        extractor = Mock(return_value=copy.deepcopy(self.numeric if result is None else result))
        OCRJobWorker(extractor=extractor, provider="live").process_next_job(job_id=job.pk)
        extractor.assert_called_once()
        job.refresh_from_db()
        return job

    def test_upload_worker_database_and_reload_preserve_scores_nulls_and_warnings(self):
        job = self.complete_job()
        record = job.document.billing_record
        self.assertEqual(job.status, "COMPLETED")
        self.assertEqual(record.status, "NEEDS_REVIEW")
        self.assertEqual(record.line_items.count(), 2)
        fields = ExtractedField.objects.filter(billing_record=record)
        origin = fields.get(field_name="origin")
        self.assertEqual(origin.confidence, Decimal("0.9900"))
        self.assertEqual(origin.raw_value, self.numeric["extraction"]["origin"])
        self.assertEqual(origin.quality, "LOW_CONFIDENCE")
        self.assertEqual(origin.metadata["confidenceMetadata"], self.numeric["confidenceMetadata"])
        self.assertEqual(origin.metadata["reviewEvidence"][0]["code"], "LOW_CONFIDENCE")
        for field in fields.filter(field_name__in=["contractLifting", "e3StockId"]):
            self.assertIsNone(field.confidence)
            self.assertIsNone(field.normalized_value)
            self.assertEqual(field.quality, "MISSING")
        self.assertEqual(fields.filter(field_name="e3StockId").count(), 2)
        self.assertEqual(job.raw_result["fieldConfidence"], self.numeric["fieldConfidence"])
        self.assertEqual(AuditEvent.objects.filter(billing_record=record, event_type="OCR_COMPLETED").count(), 1)
        for _ in range(2):
            response = self.client.get(f"/api/v1/billing-records/{record.pk}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["fields"]["origin"]["confidence"], 0.99)
            self.assertEqual(response.data["fields"]["origin"]["quality"], "LOW_CONFIDENCE")
            self.assertIsNone(response.data["fields"]["contractLifting"]["confidence"])
            for line in response.data["lineItems"]:
                self.assertIsNone(line["e3StockId"]["normalizedValue"])
                self.assertIsNone(line["e3StockId"]["confidence"])
        self.legacy_field.refresh_from_db()
        self.assertIsNone(self.legacy_field.confidence)
        self.assertEqual(self.legacy_field.raw_value, "LEGACY")

    def test_default_or_sample_result_keeps_null_confidence(self):
        legacy = {"extraction": self.numeric["extraction"], "fieldConfidence": None}
        job = self.complete_job(legacy)
        fields = ExtractedField.objects.filter(billing_record_id=job.document.billing_record_id)
        self.assertFalse(fields.exclude(confidence=None).exists())
        self.assertFalse(any("confidenceMetadata" in field.metadata for field in fields))

    def test_correction_does_not_change_the_original_score_raw_value_or_quality(self):
        job = self.complete_job()
        record_id = job.document.billing_record_id
        field = ExtractedField.objects.get(billing_record_id=record_id, field_name="origin")
        original = (field.raw_value, field.confidence, field.quality, field.metadata)
        response = self.client.patch(f"/api/v1/billing-records/{record_id}/fields/origin/",
            {"value": "Human-reviewed origin"}, format="json")
        self.assertEqual(response.status_code, 200)
        field.refresh_from_db()
        self.assertEqual((field.raw_value, field.confidence, field.quality, field.metadata), original)
        detail = self.client.get(f"/api/v1/billing-records/{record_id}/").data["fields"]["origin"]
        self.assertEqual(detail["normalizedValue"], "Human-reviewed origin")
        self.assertTrue(detail["isCorrected"])
        self.assertEqual(detail["confidence"], 0.99)

    def test_mismatched_extraction_fails_without_partial_fields_or_line_items(self):
        result = copy.deepcopy(self.numeric)
        result["extraction"]["origin"] = "Different candidate"
        job = self.upload_job()
        worker = OCRJobWorker(extractor=Mock(return_value=result), provider="live")
        with self.assertRaisesRegex(ValueError, "different extraction"):
            worker.process_next_job(job_id=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, "FAILED")
        record = job.document.billing_record
        self.assertEqual(record.status, "EXCEPTION")
        self.assertFalse(record.line_items.exists())
        self.assertFalse(record.extracted_fields.exists())

    def test_helper_rejects_bad_pointers_and_row_order_and_keeps_normalization_failures_null(self):
        from mirabito_ocr import apply_confidence_to_canonical
        for mutate in (lambda r: r["fieldConfidence"].pop("/bol_number"),
                       lambda r: r["fieldConfidence"].update({"/origin": 1.1})):
            result = copy.deepcopy(self.numeric)
            mutate(result)
            with self.assertRaises(ValueError):
                apply_confidence_to_canonical(BolLabAdapter().adapt(result["extraction"]), result)
        canonical = BolLabAdapter().adapt(self.numeric["extraction"])
        canonical["lineItems"].reverse()
        with self.assertRaises(ValueError):
            apply_confidence_to_canonical(canonical, self.numeric)
        result = copy.deepcopy(self.numeric)
        result["extraction"]["transaction_date"] = "unparseable"
        result["confidenceMetadata"]["extractionSha256"] = hashlib.sha256(
            json.dumps(result["extraction"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        canonical = apply_confidence_to_canonical(BolLabAdapter().adapt(result["extraction"]), result)
        self.assertIsNone(canonical["fields"]["transactionDate"]["confidence"])
        self.assertEqual(canonical["lineItems"][0]["ocrEvidence"]["productCodeConfidence"], 0.99)
        self.assertIsNone(canonical["lineItems"][0]["e3StockId"]["confidence"])


@skipUnless(HAS_CONFIDENCE_PACKAGE, "Install pinned OCR 0.3.0 to test live client opt-in wiring.")
class NumericConfidenceClientTests(SimpleTestCase):
    @patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={})
    @patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test-placeholder", "OCR_BUDGET_LEDGER": ""}, clear=True)
    def test_live_pipeline_is_explicitly_opted_in_only_when_enabled(self, config):
        with tempfile.TemporaryDirectory() as directory:
            for enabled in (False, True):
                with patch.dict(os.environ, {"OCR_INCLUDE_CONFIDENCE": str(enabled).lower()}), patch(
                    "mirabito_ocr.pipeline.GPTBolPipeline"
                ) as pipeline, patch("infrastructure.ocr.live_ocr_client.tempfile.mkdtemp", return_value=directory):
                    pipeline.return_value.extract_bytes.return_value = {}
                    client = LiveOCRClient()
                    result = client.submit_document(document_id="offline", file_bytes=b"unused", filename="offline.pdf")
                    self.assertIs(pipeline.call_args.kwargs["include_confidence"], enabled)
                    self.assertIs(result["metadata"]["liveOCR"]["includeConfidence"], enabled)

    @patch("infrastructure.ocr.live_ocr_client.importlib.metadata.version", return_value="0.2.0")
    def test_old_installed_package_is_rejected(self, version):
        with self.assertRaisesRegex(LiveOCRError, "verified OCR handoff"):
            LiveOCRClient()

    @patch("infrastructure.ocr.live_ocr_client.hashlib.sha256")
    def test_changed_runtime_files_are_rejected(self, checksum):
        checksum.return_value.hexdigest.return_value = "not-the-pinned-checksum"
        with self.assertRaisesRegex(LiveOCRError, "pinned handoff"):
            LiveOCRClient()
