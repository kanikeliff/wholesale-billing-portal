
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import BillingRecord
from apps.persistence.models import Document, OCRJob
from django.contrib.auth import get_user_model

class OCRJobStatusAPITests(TestCase):

    def setUp(self):
        self.record = BillingRecord.objects.create(
            status="UPLOADED"
        )

        self.document = Document.objects.create(
            billing_record=self.record,
            original_filename="sample.pdf",
            storage_path="bols/sample.pdf",
        )

        self.job = OCRJob.objects.create(
            document=self.document,
            status=OCRJob.Status.PENDING,
        )
        user = get_user_model().objects.create_user(
            username="ocr_status_tester",
            password="test_password-123",
        )
        self.client.force_login(user)

    def test_pending_job_status(self):
        response = self.client.get(
            reverse(
                "ocr-job-status",
                kwargs={"job_id": self.job.job_id},
            )
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(
            data["jobId"],
            str(self.job.job_id),
        )
        self.assertEqual(data["ocrStatus"], "PENDING")
        self.assertEqual(data["recordStatus"], "UPLOADED")
        self.assertEqual(data["attemptCount"], 0)
        self.assertEqual(data["maxAttempts"], self.job.max_attempts)

    def test_unknown_job_returns_404(self):
        from uuid import uuid4

        response = self.client.get(
            reverse(
                "ocr-job-status",
                kwargs={"job_id": uuid4()},
            )
        )

        self.assertEqual(response.status_code, 404)
    def test_unauthenticated_user_cannot_access_job(self):
        self.client.logout()

        response = self.client.get(
            reverse(
                "ocr-job-status",
                kwargs={"job_id": self.job.job_id},
            )
        )

        self.assertEqual(response.status_code, 403)