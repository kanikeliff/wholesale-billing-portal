import os
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.billing.models import BillingRecord
from apps.persistence.models import OCRJob
from infrastructure.ocr.runtime_configuration import OCRRuntimeUnavailable


class LiveUploadRoutingTests(APITestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = override_settings(MEDIA_ROOT=folder.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.client.force_authenticate(user=User(username="test-reviewer"))

    def upload(self):
        return self.client.post("/api/v1/billing-records/upload/", {
            "file": SimpleUploadedFile("new.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        }, format="multipart")

    @patch.dict(os.environ, {"OCR_PROVIDER": "live"})
    @patch("application.services.durable_bol_upload_service.ensure_live_worker_ready")
    def test_normal_upload_routes_to_live_job(self, ready):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["ocrProvider"], "live")
        job = OCRJob.objects.get(job_id=response.data["jobId"])
        self.assertEqual(job.raw_result["requestedProvider"], "live")
        self.assertEqual(job.max_attempts, 1)
        ready.assert_called_once()

    @patch.dict(os.environ, {"OCR_PROVIDER": "live"})
    @patch("application.services.durable_bol_upload_service.ensure_live_worker_ready",
           side_effect=OCRRuntimeUnavailable("OCR_WORKER_UNAVAILABLE", "OCR service is not running."))
    def test_missing_worker_returns_error_without_a_blank_record(self, ready):
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "OCR_WORKER_UNAVAILABLE")
        self.assertFalse(BillingRecord.objects.exists())
        self.assertFalse(OCRJob.objects.exists())

    @patch.dict(os.environ, {"OCR_PROVIDER": "live"})
    @patch("application.services.durable_bol_upload_service.ensure_live_worker_ready",
           side_effect=OCRRuntimeUnavailable("OCR_BUDGET_EXHAUSTED", "OCR test budget is exhausted."))
    def test_exhausted_budget_returns_error_without_inference_or_record(self, ready):
        response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "OCR_BUDGET_EXHAUSTED")
        self.assertFalse(BillingRecord.objects.exists())

    @patch.dict(os.environ, {"OCR_PROVIDER": "live", "OCR_ENFORCE_BUDGET": "false"})
    def test_normal_upload_is_accepted_with_an_exhausted_legacy_test_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = Path(folder) / "worker.json"
            ledger = Path(folder) / "budget.json"
            worker.write_text(json.dumps({"pid": os.getpid(), "provider": "live", "budgetEnforced": False}))
            ledger.write_text(json.dumps({"limitUSD": "4", "reservedUSD": "4.50"}))
            before = ledger.read_bytes()
            with patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={
                "workerState": str(worker), "budgetLedger": str(ledger),
            }):
                response = self.upload()
            self.assertEqual(response.status_code, 201)
            job = OCRJob.objects.get(job_id=response.data["jobId"])
            self.assertEqual(job.status, "PENDING")
            self.assertEqual(job.attempt_count, 0)
            self.assertEqual(ledger.read_bytes(), before)
