from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from presentation.api.upload_views import BillingRecordUploadView


class BillingRecordUploadAPITests(SimpleTestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/billing-records/upload/"

        self.mock_service = Mock()
        BillingRecordUploadView.upload_service = self.mock_service

    def tearDown(self):
        BillingRecordUploadView.upload_service = None

    def test_upload_requires_file(self):
        response = self.client.post(
            self.url,
            {},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "FILE_REQUIRED",
        )

    def test_valid_pdf_returns_created(self):
        uploaded_file = SimpleUploadedFile(
            "sample.pdf",
            b"%PDF-1.4 fake pdf content",
            content_type="application/pdf",
        )

        self.mock_service.upload.return_value = {
            "recordId": "record-123",
            "status": "OCR_COMPLETE",
            "documentId": "document-123",
            "filename": "sample.pdf",
        }

        response = self.client.post(
            self.url,
            {
                "file": uploaded_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["recordId"],
            "record-123",
        )
        self.assertEqual(
            response.data["status"],
            "OCR_COMPLETE",
        )

    def test_unconfigured_service_returns_503(self):
        BillingRecordUploadView.upload_service = None

        uploaded_file = SimpleUploadedFile(
            "sample.pdf",
            b"%PDF-1.4 fake pdf content",
            content_type="application/pdf",
        )

        response = self.client.post(
            self.url,
            {
                "file": uploaded_file,
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.data["code"],
            "OCR_SERVICE_NOT_CONFIGURED",
        )
