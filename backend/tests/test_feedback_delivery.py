import copy
from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.db import connection, transaction
from django.test import TransactionTestCase, SimpleTestCase
from django.utils import timezone

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import AuditEvent, HumanDecision, Recommendation
from application.services.feedback_delivery_service import FeedbackDeliveryService
from application.services.human_decision_service import HumanDecisionService
from application.services.workflow_service import WorkflowService
from infrastructure.database.django_billing_record_repository import DjangoBillingRecordRepository
from infrastructure.database.django_persistence_human_decision_repository import DjangoPersistenceHumanDecisionRepository
from infrastructure.team_a.client import TeamAClient
from infrastructure.team_a.exceptions import TeamAIntegrationError, TeamAUnavailableError


class FeedbackDeliveryTests(TransactionTestCase):
    def setUp(self):
        self.record = BillingRecord.objects.create(bol_number="MOCK-FEEDBACK", status="RECOMMENDATION_READY")
        self.line = LineItem.objects.create(billing_record=self.record, line_number=1, net_gallons=100)
        self.recommendation = Recommendation.objects.create(
            billing_record=self.record, revision=1, recommendation="REVIEW_REQUIRED",
            model_version="test-model", matched_terminal_log_id="test-log",
        )
        self.repo = DjangoPersistenceHumanDecisionRepository()
        self.client = Mock()
        self.client.send_feedback.side_effect = lambda p: {"recordId": p["recordId"], "stored": True, "entryId": 1, "warnings": []}
        self.worker = FeedbackDeliveryService(client=self.client)

    def decide(self):
        return self.repo.store_decision_and_update_status(
            record_id=self.record.pk, decision="APPROVE", previous_status="RECOMMENDATION_READY",
            resulting_status="APPROVED", decided_by="test-reviewer", reason="Mock only",
        )

    def test_portal_decision_queues_corrected_fields_then_delivers(self):
        AuditEvent.objects.create(billing_record=self.record, event_type="FIELD_CORRECTION",
                                  field_name="carrier", old_value="typo", new_value="correct")
        AuditEvent.objects.create(billing_record=self.record, line_item=self.line,
                                  event_type="FIELD_CORRECTION", field_name="netGallons", old_value=110, new_value=100)
        service = HumanDecisionService(
            billing_record_provider=DjangoBillingRecordRepository(), workflow_service=WorkflowService(),
            billing_record_repository=DjangoBillingRecordRepository(), decision_repository=self.repo,
        )
        result = service.submit_decision(str(self.record.pk), "APPROVE", reason="Mock only")
        self.assertEqual(result["status"], "APPROVED")
        decision = HumanDecision.objects.get(billing_record=self.record)
        payload = decision.feedback_metadata["payload"]
        self.assertEqual(payload["modelVersion"], "test-model")
        self.assertEqual(payload["matchedTerminalLogId"], "test-log")
        self.assertEqual(len(payload["correctedFields"]), 2)
        self.assertEqual(payload["correctedFields"][1]["lineItemId"], str(self.line.pk))
        self.assertNotIn("decidedBy", payload)
        self.worker.process_next()
        decision.refresh_from_db()
        self.assertEqual(decision.feedback_status, "SENT")
        self.assertIsNotNone(decision.feedback_sent_at)
        self.assertEqual(self.client.send_feedback.call_args.args[0], payload)
        public = DjangoBillingRecordRepository().get_by_id(str(self.record.pk))["feedback"]
        self.assertEqual(public["status"], "SENT")
        self.assertNotIn("payload", public)
        self.assertIsNone(self.worker.process_next())
        self.assertEqual(self.client.send_feedback.call_count, 1)

    def test_snapshot_is_immutable_and_network_runs_after_commit(self):
        decision = self.decide()
        payload = copy.deepcopy(decision.feedback_metadata["payload"])
        self.recommendation.model_version = "later-model"
        self.recommendation.save()
        AuditEvent.objects.create(billing_record=self.record, event_type="FIELD_CORRECTION", field_name="carrier", new_value="later")
        def send(p):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(p, payload)
            return {"recordId": p["recordId"], "stored": False, "entryId": 2}
        self.client.send_feedback.side_effect = send
        self.worker.process_next()
        decision.refresh_from_db()
        self.assertEqual(decision.feedback_status, "SENT")

    def test_outage_keeps_decision_and_retries_same_payload(self):
        decision = self.decide()
        self.client.send_feedback.side_effect = TeamAUnavailableError("timeout")
        self.worker.process_next()
        decision.refresh_from_db(); self.record.refresh_from_db()
        self.assertEqual(self.record.status, "APPROVED")
        self.assertEqual(decision.feedback_status, "FAILED")
        self.assertTrue(decision.feedback_metadata["retryable"])
        self.assertIsNone(self.worker.process_next())
        original = copy.deepcopy(decision.feedback_metadata["payload"])
        decision.feedback_metadata["nextAttemptAt"] = 0
        decision.save()
        self.client.send_feedback.side_effect = lambda p: {"recordId": p["recordId"], "stored": False, "entryId": 1}
        self.worker.process_next()
        decision.refresh_from_db()
        self.assertEqual(decision.feedback_status, "SENT")
        self.assertEqual(decision.feedback_metadata["attempts"], 2)
        self.assertEqual(self.client.send_feedback.call_args.args[0], original)

    def test_rejection_requires_operator_attention_and_redacts_remote_error(self):
        decision = self.decide()
        self.client.send_feedback.side_effect = TeamAIntegrationError("secret-key upstream", status_code=401)
        self.worker.process_next(); decision.refresh_from_db()
        self.assertFalse(decision.feedback_metadata["retryable"])
        self.assertNotIn("secret-key", str(decision.feedback_metadata))
        self.assertIsNone(self.worker.process_next())

    def test_leased_job_cannot_be_claimed_twice_and_expired_worker_cannot_finish(self):
        decision = self.decide()
        claim = self.worker.claim()
        self.assertIsNone(FeedbackDeliveryService(client=self.client).claim())
        decision.refresh_from_db()
        decision.feedback_metadata["leaseUntil"] = (timezone.now() - timedelta(seconds=1)).timestamp()
        decision.save()
        replacement = self.worker.claim()
        self.assertNotEqual(claim[1], replacement[1])
        self.assertIsNone(self.worker._finish(decision.pk, claim[1], acknowledgment={}))

    def test_rollback_does_not_queue_or_send(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.decide()
                raise RuntimeError("rollback")
        self.assertFalse(HumanDecision.objects.exists())
        self.assertIsNone(self.worker.process_next())
        self.client.send_feedback.assert_not_called()

    def test_historical_decisions_without_snapshot_are_not_backfilled(self):
        HumanDecision.objects.create(billing_record=self.record, decision="REJECT", previous_status="RECOMMENDATION_READY", resulting_status="REJECTED")
        self.assertIsNone(self.worker.process_next())

    def test_stale_second_decision_is_rejected(self):
        self.decide()
        with self.assertRaisesRegex(ValueError, "status changed"):
            self.decide()
        self.assertEqual(HumanDecision.objects.count(), 1)


    def test_authenticated_decision_api_to_feedback_http_acknowledgment(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        user = get_user_model().objects.create_user(username="feedback-reviewer")
        api = APIClient()
        api.force_authenticate(user=user)
        response = api.post(f"/api/v1/billing-records/{self.record.pk}/decision/",
                            {"decision": "REJECT", "reason": "Mock feedback test"}, format="json")
        self.assertEqual(response.status_code, 200)
        session = Mock()
        session.post.return_value.status_code = 200
        session.post.return_value.json.return_value = {
            "recordId": str(self.record.pk), "stored": True, "entryId": 42, "warnings": [],
        }
        transport = TeamAClient(base_url="https://team-a.test", api_key="test-secret", session=session)
        FeedbackDeliveryService(client=transport).process_next()
        sent = session.post.call_args.kwargs["json"]
        self.assertEqual(sent["finalDecision"], "REJECT")
        self.assertEqual(sent["finalStatus"], "REJECTED")
        detail = api.get(f"/api/v1/billing-records/{self.record.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["feedback"]["status"], "SENT")

    def test_operator_can_retry_rejected_delivery_without_changing_payload(self):
        from django.core.management import call_command
        decision = self.decide()
        original = copy.deepcopy(decision.feedback_metadata["payload"])
        self.client.send_feedback.side_effect = TeamAIntegrationError("unauthorized", status_code=401)
        self.worker.process_next()
        self.client.send_feedback.side_effect = lambda p: {"recordId": p["recordId"], "stored": True, "entryId": 3}
        with patch.object(FeedbackDeliveryService, "_client", return_value=self.client):
            call_command("run_feedback_worker", once=True, decision_id=str(decision.pk), retry_rejected=True)
        decision.refresh_from_db()
        self.assertEqual(decision.feedback_status, "SENT")
        self.assertEqual(decision.feedback_metadata["payload"], original)


class FeedbackClientTests(SimpleTestCase):
    def setUp(self):
        self.session = Mock()
        self.client = TeamAClient(base_url="https://team-a.test", api_key="secret-key", session=self.session)
        self.payload = {"recordId": "mock-1"}

    def response(self, status, data):
        response = Mock(status_code=status)
        response.json.return_value = data
        self.session.post.return_value = response

    def test_acknowledgment_and_idempotent_redelivery(self):
        for stored in (True, False):
            self.response(200, {"recordId": "mock-1", "stored": stored, "entryId": 1})
            self.assertEqual(self.client.send_feedback(self.payload)["stored"], stored)
        self.assertEqual(self.session.post.call_args.args[0], "https://team-a.test/api/v1/feedback/audit")
        self.assertEqual(self.session.post.call_args.kwargs["headers"]["X-API-Key"], "secret-key")

    def test_malformed_or_mismatched_ack_is_not_success(self):
        for body in ({}, {"recordId": "other", "stored": True, "entryId": 1},
                     {"recordId": "mock-1", "stored": "true", "entryId": 1}):
            self.response(200, body)
            with self.assertRaises(TeamAUnavailableError):
                self.client.send_feedback(self.payload)

    def test_temporary_http_errors_are_retriable(self):
        for status in (408, 429, 500, 503):
            self.response(status, {})
            with self.assertRaises(TeamAUnavailableError):
                self.client.send_feedback(self.payload)

    def test_network_failure_is_retriable_and_does_not_retry_inline(self):
        self.session.post.side_effect = requests.ConnectionError("secret-key")
        with self.assertRaises(TeamAUnavailableError):
            self.client.send_feedback(self.payload)
        self.assertEqual(self.session.post.call_count, 1)

    def test_unauthorized_is_not_retriable(self):
        self.response(401, {"code": "UNAUTHORIZED", "message": "no"})
        with self.assertRaises(TeamAIntegrationError) as caught:
            self.client.send_feedback(self.payload)
        self.assertFalse(caught.exception.retryable)
