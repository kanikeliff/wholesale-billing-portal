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


    def test_document_storage_failure_rolls_back_persisted_record(self):
        uploaded_file = SimpleUploadedFile(
            "rollback.pdf",
            b"%PDF-1.4 rollback test content",
            content_type="application/pdf",
        )

        self.ocr_client.submit_document.return_value = {
            "extraction": {
                "bol_number": "BOL-ROLLBACK",
                "origin": "Albany",
                "transaction_date": "2026-10-29",
                "products": [],
            }
        }

        self.ocr_processing_service.persist_extraction.return_value = {
            "recordId": "record-rollback",
            "status": "OCR_COMPLETE",
        }

        document_file_service = Mock()
        document_file_service.store_uploaded_document.side_effect = (
            RuntimeError("document storage failed")
        )

        service = BOLUploadService(
            ocr_client=self.ocr_client,
            ocr_processing_service=self.ocr_processing_service,
            document_file_service=document_file_service,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "document storage failed",
        ):
            service.upload(uploaded_file)

        (
            self.ocr_processing_service
            .rollback_persisted_record
            .assert_called_once_with(
                "record-rollback"
            )
        )


    def test_rollback_failure_does_not_mask_document_storage_error(self):
        uploaded_file = SimpleUploadedFile(
            "rollback-mask.pdf",
            b"%PDF-1.4 rollback masking test",
            content_type="application/pdf",
        )

        self.ocr_client.submit_document.return_value = {
            "extraction": {
                "bol_number": "BOL-ROLLBACK-MASK",
                "origin": "Albany",
                "transaction_date": "2026-10-29",
                "products": [],
            }
        }

        self.ocr_processing_service.persist_extraction.return_value = {
            "recordId": "record-rollback-mask",
            "status": "OCR_COMPLETE",
        }

        self.ocr_processing_service.rollback_persisted_record.side_effect = (
            RuntimeError("rollback failed")
        )

        document_file_service = Mock()
        document_file_service.store_uploaded_document.side_effect = (
            RuntimeError("document storage failed")
        )

        service = BOLUploadService(
            ocr_client=self.ocr_client,
            ocr_processing_service=self.ocr_processing_service,
            document_file_service=document_file_service,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "document storage failed",
        ) as error_context:
            service.upload(uploaded_file)

        (
            self.ocr_processing_service
            .rollback_persisted_record
            .assert_called_once_with(
                "record-rollback-mask"
            )
        )

        notes = getattr(
            error_context.exception,
            "__notes__",
            [],
        )

        self.assertTrue(
            any(
                "rollback also failed" in note
                for note in notes
            )
        )
