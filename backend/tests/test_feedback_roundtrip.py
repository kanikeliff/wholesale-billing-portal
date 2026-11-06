"""Optional cross-repository regression: real Django APIs and real Team A ASGI app.

Set TEAM_A_SOURCE_PATH to the checkout's team_a_service directory. OCR replays a
saved sample; all Team A traffic stays inside FastAPI TestClient. No live keys,
network calls, production DBs, training jobs or paid extraction are involved.
"""
import copy
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest import skipUnless
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import OperationalError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITransactionTestCase

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import AuditEvent, ExtractedField, HumanDecision, OCRJob, Recommendation
from application.services.feedback_delivery_service import FeedbackDeliveryService
from infrastructure.team_a.client import TeamAClient
from infrastructure.team_a.team_a_adapter import TeamAAdapter


@skipUnless(os.getenv("TEAM_A_SOURCE_PATH"), "Set TEAM_A_SOURCE_PATH to run the actual Team A contract roundtrip.")
class FeedbackRoundtripTests(APITransactionTestCase):
    def setUp(self):
        source = Path(os.environ["TEAM_A_SOURCE_PATH"]).resolve()
        self.assertTrue((source / "team_a_service/api.py").is_file())
        sys.path.insert(0, str(source))
        self.addCleanup(lambda: sys.path.remove(str(source)))
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.temporary.name)
        self.override.enable(); self.addCleanup(self.override.disable)
        env = patch.dict(os.environ, {
            "DATABASE_URL": "", "TEAM_A_MODEL_PATH": "", "TEAM_A_ADMIN_KEY": "",
            "TEAM_A_API_KEY": "roundtrip-test-only", "OCR_PROVIDER": "sample",
            "TEAM_A_PRODUCT_MAPPINGS": str(source / "team_a_service/data/ProductNameMappings.json"),
            "TEAM_A_CARRIERS": str(source / "team_a_service/data/carriers.json"),
            "TEAM_A_TERMINAL_LOGS": str(source / "team_a_service/data/terminal_logs.json"),
        })
        env.start(); self.addCleanup(env.stop)
        from fastapi.testclient import TestClient
        self.TestClient = TestClient
        self.team_api = importlib.import_module("team_a_service.api")
        self.store_module = importlib.import_module("team_a_service.store")
        self.database_url = "sqlite:///" + str(Path(self.temporary.name) / "team-a-test.sqlite3")
        self.start_team_a()
        self.calls = []
        self.transport = type("InProcessTransport", (), {})()
        self.transport.post = self.post_to_team_a
        self.http = TeamAClient(base_url="https://team-a.test", api_key="roundtrip-test-only",
                                session=self.transport, sleeper=lambda _: None)
        self.worker = FeedbackDeliveryService(client=self.http)
        provider = patch("presentation.api.billing_views.recommendation_service.recommendation_provider",
                         TeamAAdapter(self.http))
        provider.start(); self.addCleanup(provider.stop)
        self.client.force_authenticate(get_user_model().objects.create_user(username="roundtrip-reviewer"))

    def start_team_a(self):
        self.app = self.team_api.create_app(api_key="roundtrip-test-only", database_url=self.database_url)
        self.remote = self.TestClient(self.app)
        self.addCleanup(self.remote.close)
        self.addCleanup(self.app.state.store.dispose)

    def post_to_team_a(self, url, **kwargs):
        # Refuse accidental off-process traffic: only this origin is supported.
        assert url.startswith("https://team-a.test/")
        self.calls.append((url, copy.deepcopy(kwargs["json"])))
        response = self.remote.post(url.removeprefix("https://team-a.test"),
                                    json=kwargs["json"], headers=kwargs["headers"])
        return response

    def upload_review_and_decide(self, decision="REJECT"):
        sample = Path(__file__).parent / "fixtures/ocr_samples/Sample_BOL_3.pdf"
        uploaded = self.client.post("/api/v1/billing-records/upload/", {
            "file": SimpleUploadedFile("feedback-roundtrip.pdf", sample.read_bytes(), "application/pdf")
        }, format="multipart")
        self.assertEqual(uploaded.status_code, 201, uploaded.data)
        self.receipt = uploaded.json()
        call_command("run_ocr_worker", once=True, job_id=self.receipt["jobId"])
        job = OCRJob.objects.get(pk=self.receipt["jobId"])
        self.assertEqual(job.status, "COMPLETED")
        self.detail_url = f"/api/v1/billing-records/{self.receipt['recordId']}/"
        original = self.client.get(self.detail_url).json()
        self.assertEqual(original["status"], "OCR_COMPLETE")
        evidence = list(ExtractedField.objects.filter(billing_record_id=self.receipt["recordId"]).order_by("pk").values())
        # Evaluate once before editing, then request a fresh revision afterwards.
        initial = self.client.post(self.detail_url + "evaluate/", {}, format="json")
        self.assertEqual(initial.status_code, 200, initial.data)
        self.line_id = original["lineItems"][0]["lineItemId"]
        for path, value in (("fields/carrier/", "Roundtrip Test Carrier"),
                            (f"line-items/{self.line_id}/netGallons/", 1234.5)):
            changed = self.client.patch(self.detail_url + path, {"value": value}, format="json")
            self.assertEqual(changed.status_code, 200, changed.data)
            self.assertEqual(changed.data["status"], "RECOMMENDATION_PENDING")
        evaluated = self.client.post(self.detail_url + "evaluate/", {}, format="json")
        self.assertEqual(evaluated.status_code, 200, evaluated.data)
        self.assertEqual(evaluated.data["status"], "RECOMMENDATION_READY")
        self.assertEqual(Recommendation.objects.filter(billing_record_id=self.receipt["recordId"]).count(), 2)
        final = self.client.post(self.detail_url + "decision/", {
            "decision": decision, "reason": "SIMULATED regression test only",
        }, format="json")
        self.assertEqual(final.status_code, 200, final.data)
        self.assertEqual(final.data["status"], {"APPROVE": "APPROVED", "REJECT": "REJECTED", "EXCEPTION": "EXCEPTION"}[decision])
        self.decision = HumanDecision.objects.get(billing_record_id=self.receipt["recordId"])
        self.assertEqual(self.decision.feedback_status, "PENDING")
        self.payload = copy.deepcopy(self.decision.feedback_metadata["payload"])
        self.assertEqual(self.payload["modelVersion"], evaluated.data["recommendation"]["modelVersion"])
        self.assertEqual(self.payload["finalDecision"], decision)
        self.assertEqual(self.payload["correctedFields"][0]["field"], "carrier")
        self.assertEqual(self.payload["correctedFields"][1]["lineItemId"], self.line_id)
        self.assertEqual(self.payload["correctedFields"][1]["newValue"], 1234.5)
        self.assertEqual(list(ExtractedField.objects.filter(billing_record_id=self.receipt["recordId"]).order_by("pk").values()), evidence)
        self.assertEqual(AuditEvent.objects.filter(billing_record_id=self.receipt["recordId"], event_type="HUMAN_DECISION").count(), 1)
        self.assertFalse(any("/feedback/audit" in url for url, _ in self.calls))

    def remote_entries(self):
        from sqlalchemy import select
        with self.app.state.store.engine.connect() as conn:
            return [r[0] for r in conn.execute(select(self.store_module.feedback_t.c.entry))]

    def assert_delivered(self):
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.feedback_status, "SENT")
        self.assertEqual(self.client.get(self.detail_url).json()["feedback"]["status"], "SENT")
        remote = self.remote.get("/api/v1/recommendations/" + self.receipt["recordId"],
                                 headers={"X-API-Key": "roundtrip-test-only"})
        self.assertEqual(remote.status_code, 200)
        self.assertTrue(remote.json()["feedbackReceived"])
        entries = self.remote_entries()
        self.assertEqual(len(entries), 1)
        # Team A normalizes omitted optional lineItemId to null on header edits.
        expected = [dict(item, lineItemId=item.get("lineItemId"))
                    for item in self.payload["correctedFields"]]
        self.assertEqual(entries[0]["correctedFields"], expected)
        self.assertEqual(entries[0]["teamAEvaluationSeq"], 2)
        self.assertIsNotNone(entries[0]["teamAConfidence"])
        self.assertEqual(entries[0]["warnings"], [])

    def test_new_bol_review_to_actual_team_a_store(self):
        self.upload_review_and_decide()
        self.worker.process_next()
        self.assert_delivered()
        self.assertIsNone(self.worker.process_next())

    def test_service_outage_then_due_retry_uses_same_snapshot(self):
        self.upload_review_and_decide()
        self.app.state.available = False
        self.worker.process_next()
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.feedback_status, "FAILED")
        self.assertEqual(self.client.get(self.detail_url).json()["status"], "REJECTED")
        self.assertEqual(self.remote_entries(), [])
        self.assertIsNone(self.worker.process_next())
        due = self.decision.feedback_metadata["nextAttemptAt"]
        self.app.state.available = True
        with patch("application.services.feedback_delivery_service.timezone.now",
                   return_value=timezone.datetime.fromtimestamp(due + 1, timezone.get_current_timezone())):
            FeedbackDeliveryService(client=self.http).process_next()
        self.assert_delivered()
        attempts = [p for url, p in self.calls if "/feedback/audit" in url]
        self.assertEqual(attempts, [self.payload, self.payload])

    def test_lost_ack_and_team_a_restart_do_not_duplicate_feedback(self):
        self.upload_review_and_decide()
        original = self.transport.post
        def accepted_but_ack_lost(url, **kwargs):
            original(url, **kwargs)
            raise requests.Timeout("simulated lost acknowledgment")
        self.transport.post = accepted_but_ack_lost
        self.worker.process_next()
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.feedback_status, "FAILED")
        self.assertEqual(len(self.remote_entries()), 1)
        # Restart Team A against the same isolated SQL store.
        self.remote.close(); self.app.state.store.dispose()
        self.start_team_a()
        self.transport.post = original
        due = self.decision.feedback_metadata["nextAttemptAt"]
        with patch("application.services.feedback_delivery_service.timezone.now",
                   return_value=timezone.datetime.fromtimestamp(due + 1, timezone.get_current_timezone())):
            self.worker.process_next()
        self.assert_delivered()
        self.assertFalse(self.decision.feedback_metadata["acknowledgment"]["stored"])

    def test_auth_rejection_requires_explicit_operator_retry(self):
        self.upload_review_and_decide()
        self.app.state.api_key = "different-test-key"
        self.worker.process_next()
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.feedback_status, "FAILED")
        self.assertFalse(self.decision.feedback_metadata["retryable"])
        self.assertIsNone(self.worker.process_next())
        self.app.state.api_key = "roundtrip-test-only"
        with patch.object(FeedbackDeliveryService, "_client", return_value=self.http):
            call_command("run_feedback_worker", once=True, decision_id=str(self.decision.pk), retry_rejected=True)
        self.assert_delivered()

    def test_approval_delivers_its_final_status(self):
        self.upload_review_and_decide("APPROVE")
        self.worker.process_next()
        self.assert_delivered()
        self.assertEqual(self.remote_entries()[0]["finalStatus"], "APPROVED")

    def test_exception_delivers_its_final_status(self):
        self.upload_review_and_decide("EXCEPTION")
        self.worker.process_next()
        self.assert_delivered()
        self.assertEqual(self.remote_entries()[0]["finalStatus"], "EXCEPTION")

    def test_local_ack_write_failure_recovers_after_lease_without_duplicate(self):
        self.upload_review_and_decide()
        with patch.object(self.worker, "_finish", side_effect=OperationalError("local database unavailable")):
            with self.assertRaises(OperationalError):
                self.worker.process_next()
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.feedback_status, "PENDING")
        self.assertEqual(len(self.remote_entries()), 1)
        self.assertIsNone(self.worker.process_next())
        expired = self.decision.feedback_metadata["leaseUntil"] + 1
        with patch("application.services.feedback_delivery_service.timezone.now",
                   return_value=timezone.datetime.fromtimestamp(expired, timezone.get_current_timezone())):
            self.worker.process_next()
        self.assert_delivered()
        self.assertFalse(self.decision.feedback_metadata["acknowledgment"]["stored"])

    def check_category_mismatch(self, product, supplied_e3, expected_e3):
        fixture = json.loads((Path(os.environ["TEAM_A_SOURCE_PATH"]) / "sample_data/sample_request.json").read_text())
        record = BillingRecord.objects.create(
            bol_number=fixture["bolNumber"], contract_lifting=fixture["contractLifting"],
            origin=fixture["origin"], supplier=fixture["supplier"], carrier=fixture["carrier"],
            transaction_date=fixture["transactionDate"], destination=fixture["destination"], status="OCR_COMPLETE",
        )
        source_line = fixture["lineItems"][0]
        line = LineItem.objects.create(billing_record=record, line_number=1, product=product,
                                      e3_stock_id=supplied_e3, net_gallons=source_line["netGallons"],
                                      gross_gallons=source_line["grossGallons"])
        url = f"/api/v1/billing-records/{record.pk}/"
        evaluated = self.client.post(url + "evaluate/", {}, format="json")
        self.assertEqual(evaluated.status_code, 200, evaluated.data)
        recommendation = evaluated.data["recommendation"]
        self.assertEqual(recommendation["recommendation"], "REVIEW_REQUIRED")
        flags = [f for f in recommendation["exceptionIndicators"]
                 if f["code"] == "PRODUCT_MISMATCH" and f.get("field") == "e3StockId"]
        self.assertTrue(flags, recommendation)
        self.assertEqual(flags[0]["lineItemId"], str(line.pk))
        self.assertEqual(flags[0]["severity"], "WARNING")
        self.assertEqual(recommendation["mappedEntities"]["lineItems"][0]["e3StockId"], expected_e3)
        line.refresh_from_db()
        self.assertEqual(line.e3_stock_id, supplied_e3, "Recommendation must not overwrite accepted billing values")
        saved = self.client.get(url).json()
        self.assertEqual(saved["recommendation"]["exceptionIndicators"], recommendation["exceptionIndicators"])
        self.assertEqual(saved["lineItems"][0]["e3StockId"]["normalizedValue"], supplied_e3)
        corrected = self.client.patch(url + f"line-items/{line.pk}/e3StockId/",
                                      {"value": expected_e3}, format="json")
        self.assertEqual(corrected.status_code, 200)
        fresh = self.client.post(url + "evaluate/", {}, format="json")
        self.assertEqual(fresh.status_code, 200, fresh.data)
        self.assertFalse([f for f in fresh.data["recommendation"]["exceptionIndicators"]
                          if f["code"] == "PRODUCT_MISMATCH" and f.get("field") == "e3StockId"])
        final = self.client.post(url + "decision/", {
            "decision": "REJECT", "reason": "SIMULATED Alpha product category mismatch review",
        }, format="json")
        self.assertEqual(final.status_code, 200)
        self.worker.process_next()
        decision = HumanDecision.objects.get(billing_record=record)
        self.assertEqual(decision.feedback_status, "SENT")
        correction = decision.feedback_metadata["payload"]["correctedFields"][0]
        self.assertEqual(correction, {"field": "e3StockId", "lineItemId": str(line.pk),
                                      "oldValue": supplied_e3, "newValue": expected_e3})
        remote = self.remote_entries()
        self.assertEqual(len(remote), 1)
        self.assertEqual(remote[0]["teamAOutputCorrections"], [correction])
        self.assertEqual(remote[0]["warnings"], [])

    def test_diesel_with_unleaded_e3_is_flagged_and_reviewed(self):
        self.check_category_mismatch("Ultra Low Sulfur Diesel", "UX", "UD")

    def test_unleaded_with_diesel_e3_is_flagged_and_reviewed(self):
        self.check_category_mismatch("Regular Gasoline (RUL 87 ETH)", "UD", "UX")
