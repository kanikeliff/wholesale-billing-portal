
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
