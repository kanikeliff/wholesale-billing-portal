from unittest.mock import patch

from django.test import TestCase

from apps.billing.models import BillingRecord
from apps.persistence.models import AuditEvent, HumanDecision
from infrastructure.database.django_persistence_human_decision_repository import (
    DjangoPersistenceHumanDecisionRepository,
)


class HumanDecisionAuditTests(TestCase):

    def setUp(self):
        self.record = BillingRecord.objects.create(
            bol_number="AUDIT-TEST",
            status="RECOMMENDATION_READY",
        )
        self.repository = DjangoPersistenceHumanDecisionRepository()

    def submit(self):
        return self.repository.store_decision_and_update_status(
            record_id=self.record.record_id,
            decision="REJECT",
            previous_status="RECOMMENDATION_READY",
            resulting_status="REJECTED",
            decided_by="test-reviewer",
            reason="Audit integration test",
        )

    def test_decision_creates_audit_event(self):
        decision = self.submit()
        self.record.refresh_from_db()

        self.assertEqual(self.record.status, "REJECTED")

        self.assertEqual(
            HumanDecision.objects.filter(
                billing_record=self.record
            ).count(),
            1,
        )

        event = AuditEvent.objects.get(
            billing_record=self.record,
            event_type="HUMAN_DECISION",
        )

        self.assertEqual(event.old_value, "RECOMMENDATION_READY")
        self.assertEqual(event.new_value, "REJECTED")
        self.assertEqual(event.actor_id, "test-reviewer")
        self.assertEqual(
            event.metadata["humanDecisionId"],
            str(decision.human_decision_id),
        )

    def test_audit_failure_rolls_back_everything(self):
        with patch(
            "infrastructure.database."
            "django_persistence_human_decision_repository."
            "AuditEvent.objects.create",
            side_effect=RuntimeError("audit write failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "audit write failed",
            ):
                self.submit()

        self.record.refresh_from_db()

        self.assertEqual(
            self.record.status,
            "RECOMMENDATION_READY",
        )
        self.assertFalse(
            HumanDecision.objects.filter(
                billing_record=self.record
            ).exists()
        )
        self.assertFalse(
            AuditEvent.objects.filter(
                billing_record=self.record
            ).exists()
        )
