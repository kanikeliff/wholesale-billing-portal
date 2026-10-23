from unittest import TestCase
from unittest.mock import Mock

from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)

from application.services.bol_upload_service import (
    BOLUploadService,
    EmptyFileError,
    UnsupportedFileTypeError,
)


class BOLUploadServiceTests(TestCase):

    def setUp(self):
        self.ocr_client = Mock()
        self.ocr_processing_service = Mock()

        self.service = BOLUploadService(
            ocr_client=self.ocr_client,
            ocr_processing_service=self.ocr_processing_service,
        )

    def test_valid_pdf_upload_is_processed(self):
        uploaded_file = SimpleUploadedFile(
            "sample.pdf",
            b"%PDF-1.4 fake pdf content",
            content_type="application/pdf",
        )

        self.ocr_client.submit_document.return_value = {
            "extraction": {
                "bol_number": "BOL-100",
                "origin": "Syracuse",
                "transaction_date": "2026-10-23",
                "products": [],
            }
        }

        self.ocr_processing_service.persist_extraction.return_value = {
            "recordId": "record-123",
            "status": "NEEDS_REVIEW",
        }

        result = self.service.upload(
            uploaded_file
        )

        self.assertEqual(
            result["recordId"],
            "record-123",
        )

        self.assertEqual(
            result["status"],
            "NEEDS_REVIEW",
        )

        self.assertEqual(
            result["filename"],
            "sample.pdf",
        )

        self.ocr_client.submit_document.assert_called_once()

        self.ocr_processing_service.persist_extraction.assert_called_once()

    def test_invalid_extension_is_rejected(self):
        uploaded_file = SimpleUploadedFile(
            "malware.exe",
            b"abcdef",
            content_type="application/octet-stream",
        )

        with self.assertRaises(
            UnsupportedFileTypeError
        ):
            self.service.upload(
                uploaded_file
            )

    def test_empty_file_is_rejected(self):
        uploaded_file = SimpleUploadedFile(
            "empty.pdf",
            b"",
            content_type="application/pdf",
        )

        with self.assertRaises(
            EmptyFileError
        ):
            self.service.upload(
                uploaded_file
            )

    def test_fake_pdf_content_is_rejected(self):
        uploaded_file = SimpleUploadedFile(
            "fake.pdf",
            b"this is not actually a pdf",
            content_type="application/pdf",
        )

        with self.assertRaises(
            UnsupportedFileTypeError
        ):
            self.service.upload(
                uploaded_file
            )

    def test_valid_png_upload_is_processed(self):
        uploaded_file = SimpleUploadedFile(
            "sample.png",
            b"\x89PNG\r\n\x1a\nfake image content",
            content_type="image/png",
        )

        self.ocr_client.submit_document.return_value = {
            "extraction": {
                "bol_number": "BOL-200",
                "origin": "Albany",
                "transaction_date": "2026-10-23",
                "products": [],
            }
        }

        self.ocr_processing_service.persist_extraction.return_value = {
            "recordId": "record-456",
            "status": "OCR_COMPLETE",
        }

        result = self.service.upload(
            uploaded_file
        )

        self.assertEqual(
            result["recordId"],
            "record-456",
        )

    def test_valid_jpeg_upload_is_processed(self):
        uploaded_file = SimpleUploadedFile(
            "sample.jpg",
            b"\xff\xd8\xfffake jpeg content",
            content_type="image/jpeg",
        )

        self.ocr_client.submit_document.return_value = {
            "extraction": {
                "bol_number": "BOL-300",
                "origin": "Binghamton",
                "transaction_date": "2026-10-23",
                "products": [],
            }
        }

        self.ocr_processing_service.persist_extraction.return_value = {
            "recordId": "record-789",
            "status": "OCR_COMPLETE",
        }

        result = self.service.upload(
            uploaded_file
        )

        self.assertEqual(
            result["recordId"],
            "record-789",
        )