
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.billing.models import BillingRecord
from apps.persistence.models import Document, OCRJob
from application.services.document_file_service import DocumentFileService
from application.services.durable_bol_upload_service import (
    DurableBOLUploadService,
)


class DurableBOLUploadServiceTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_dir.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.service = DurableBOLUploadService(
            document_file_service=DocumentFileService()
        )

    def make_pdf(self):
        return SimpleUploadedFile(
            "test.pdf",
            b"%PDF-1.4 durable upload test",
            content_type="application/pdf",
        )

    def test_upload_creates_pending_job(self):
        result = self.service.upload(self.make_pdf())

        self.assertEqual(result["status"], "UPLOADED")
        self.assertEqual(result["ocrStatus"], "PENDING")

        self.assertTrue(
            BillingRecord.objects.filter(
                record_id=result["recordId"]
            ).exists()
        )

        document = Document.objects.get(
            document_id=result["documentId"]
        )

        self.assertTrue(
            (Path(self.temp_dir.name) / document.storage_path).exists()
        )

        job = OCRJob.objects.get(job_id=result["jobId"])

        self.assertEqual(job.status, OCRJob.Status.PENDING)
        self.assertEqual(job.document_id, document.document_id)

    def test_job_failure_rolls_back_database_and_file(self):
        original_count = BillingRecord.objects.count()

        with patch.object(
            OCRJob.objects,
            "create",
            side_effect=RuntimeError("OCR job creation failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "OCR job creation failed",
            ):
                self.service.upload(self.make_pdf())

        self.assertEqual(
            BillingRecord.objects.count(),
            original_count,
        )
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(OCRJob.objects.count(), 0)

        self.assertEqual(
            list(Path(self.temp_dir.name).rglob("*.pdf")),
            [],
        )
