"""PostgreSQL API coverage for OCR evidence and human correction review."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import AuditEvent, ExtractedField


class ReviewWorkflowAPITests(APITestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        settings = override_settings(MEDIA_ROOT=temporary_directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.url = "/api/v1/billing-records/upload/"
        self.client.force_authenticate(user=User(username="test-reviewer"))

    def test_missing_fields_corrected_with_authenticated_actor_and_immutable_ocr(self):
        sample = Path(__file__).parent / "fixtures/ocr_samples/Sample_BOL_3.pdf"
        response = self.client.post(self.url, {"file": SimpleUploadedFile(
            "renamed-sample.pdf", sample.read_bytes(), content_type="application/pdf"
        )}, format="multipart")
        self.assertEqual(response.status_code, 201)
        uploaded = response.json()
        # Keep the API test's enclosing transaction open between worker jobs.
        with patch("apps.persistence.management.commands.run_ocr_worker.close_old_connections"):
            call_command("run_ocr_worker", once=True, job_id=uploaded["jobId"])

        detail_url = f"/api/v1/billing-records/{uploaded['recordId']}/"
        original = self.client.get(detail_url).json()
        # Optional missing fields do not fail the required OCR completeness check.
        self.assertEqual(original["status"], "OCR_COMPLETE")
        validation = self.client.post(f"{detail_url}validate/").json()
        self.assertEqual(validation["nextStatus"], "NEEDS_REVIEW")
        self.assertEqual(len(validation["reviewFlags"]), 3)
        self.assertEqual(self.client.get(detail_url).json()["status"], "OCR_COMPLETE")
        evidence = list(ExtractedField.objects.filter(
            billing_record_id=uploaded["recordId"]
        ).order_by("pk").values())
        first, second = original["lineItems"]
        changes = [
            ("fields/contractLifting/", "TEST-CONTRACT"),
            (f"line-items/{first['lineItemId']}/e3StockId/", "TEST-E3-1"),
            (f"line-items/{second['lineItemId']}/e3StockId/", "TEST-E3-2"),
        ]
        for index, (path, value) in enumerate(changes):
            corrected = self.client.patch(f"{detail_url}{path}", {
                "value": value, "reviewedBy": "spoofed-actor"
            }, format="json")
            self.assertEqual(corrected.status_code, 200, corrected.data)
            self.assertEqual(corrected.json()["newValue"], value)
            self.assertEqual(corrected.json()["status"], "RECOMMENDATION_PENDING")
            self.assertTrue(corrected.json()["requiresReevaluation"])
            validation = self.client.post(f"{detail_url}validate/").json()
            self.assertEqual(len(validation["reviewFlags"]), 2 - index)
            if index == 1:
                self.assertEqual(validation["reviewFlags"][0]["lineItemId"], second["lineItemId"])

        refreshed = self.client.get(detail_url).json()
        corrected_fields = [refreshed["fields"]["contractLifting"]] + [
            line["e3StockId"] for line in refreshed["lineItems"]
        ]
        for field in corrected_fields:
            self.assertTrue(field["isCorrected"])
            self.assertEqual(field["quality"], "MISSING")  # original OCR quality
            self.assertIsNone(field["rawValue"])
            self.assertIsNone(field["confidence"])
        record = BillingRecord.objects.get(record_id=uploaded["recordId"])
        self.assertEqual(record.contract_lifting, "TEST-CONTRACT")
        self.assertEqual(record.status, "RECOMMENDATION_PENDING")
        self.assertEqual(LineItem.objects.get(line_item_id=first["lineItemId"]).e3_stock_id, "TEST-E3-1")
        self.assertEqual(validation["nextStatus"], "RECOMMENDATION_PENDING")
        self.assertEqual(list(ExtractedField.objects.filter(
            billing_record=record
        ).order_by("pk").values()), evidence)
        audits = AuditEvent.objects.filter(billing_record=record, event_type="FIELD_CORRECTION")
        self.assertEqual(audits.count(), 3)
        self.assertEqual(set(audits.values_list("actor_id", flat=True)), {"test-reviewer"})
        header_audit = audits.get(field_name="contractLifting")
        self.assertIsNone(header_audit.old_value)
        self.assertEqual(header_audit.new_value, "TEST-CONTRACT")
        self.assertEqual(header_audit.metadata["scope"], "record")
        self.assertEqual(audits.filter(metadata__scope="line_item").count(), 2)
        invalid = self.client.patch(f"{detail_url}fields/contractLifting/", {"value": None}, format="json")
        self.assertEqual(invalid.status_code, 400)
        record.refresh_from_db()
        self.assertEqual(record.contract_lifting, "TEST-CONTRACT")
        self.assertEqual(audits.count(), 3)
