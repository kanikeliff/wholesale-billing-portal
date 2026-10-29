import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.test import TestCase

from apps.billing.models import BillingRecord
from apps.persistence.models import Document
from application.services.document_file_service import DocumentFileService


class DocumentFileServiceTests(TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.storage = FileSystemStorage(
            location=self.temp_directory.name,
            base_url="/media/",
        )

        self.service = DocumentFileService()

        self.record = BillingRecord.objects.create(
            bol_number="DOCUMENT-ROLLBACK-TEST",
            status="OCR_COMPLETE",
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_serialize_failure_rolls_back_document_and_deletes_file(self):
        document_id = str(uuid.uuid4())

        with patch(
            "application.services.document_file_service.default_storage",
            self.storage,
        ):
            with patch.object(
                self.service,
                "serialize",
                side_effect=RuntimeError("serialization failed"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "serialization failed",
                ):
                    self.service.store_uploaded_document(
                        record_id=self.record.record_id,
                        document_id=document_id,
                        original_filename="rollback.pdf",
                        file_bytes=b"%PDF-1.4 rollback test content",
                        mime_type="application/pdf",
                    )

        self.assertFalse(
            Document.objects.filter(
                document_id=document_id,
            ).exists()
        )

        remaining_files = [
            path
            for path in Path(
                self.temp_directory.name
            ).rglob("*")
            if path.is_file()
        ]

        self.assertEqual(
            remaining_files,
            [],
        )
