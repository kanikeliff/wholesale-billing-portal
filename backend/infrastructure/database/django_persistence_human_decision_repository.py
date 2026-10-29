from django.db import transaction
from django.utils import timezone

from apps.billing.models import BillingRecord
from apps.persistence.models import HumanDecision, Recommendation


class DjangoPersistenceHumanDecisionRepository:

    @transaction.atomic
    def store_decision(
        self,
        *,
        record_id,
        decision,
        previous_status,
        resulting_status,
        decided_by=None,
        reason=None,
    ):
        try:
            record = (
                BillingRecord.objects
                .select_for_update()
                .get(record_id=record_id)
            )
        except (BillingRecord.DoesNotExist, ValueError):
            raise ValueError("Billing record not found.")

        current_recommendation = (
            Recommendation.objects
            .filter(
                billing_record=record,
                is_current=True,
            )
            .first()
        )

        return HumanDecision.objects.create(
            billing_record=record,
            recommendation=current_recommendation,
            decision=decision,
            previous_status=previous_status,
            resulting_status=resulting_status,
            decided_by=decided_by,
            reason=reason,
            feedback_status=HumanDecision.FeedbackStatus.PENDING,
        )


    @transaction.atomic
    def store_decision_and_update_status(
        self,
        *,
        record_id,
        decision,
        previous_status,
        resulting_status,
        decided_by=None,
        reason=None,
    ):
        try:
            record = (
                BillingRecord.objects
                .select_for_update()
                .get(record_id=record_id)
            )
        except (BillingRecord.DoesNotExist, ValueError):
            raise ValueError("Billing record not found.")

        current_recommendation = (
            Recommendation.objects
            .filter(
                billing_record=record,
                is_current=True,
            )
            .first()
        )

        human_decision = HumanDecision.objects.create(
            billing_record=record,
            recommendation=current_recommendation,
            decision=decision,
            previous_status=previous_status,
            resulting_status=resulting_status,
            decided_by=decided_by,
            reason=reason,
            feedback_status=HumanDecision.FeedbackStatus.PENDING,
        )

        record.status = resulting_status
        record.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return human_decision

    def list_history(self, record_id):
        return list(
            HumanDecision.objects
            .filter(billing_record_id=record_id)
            .select_related("recommendation")
            .order_by("created_at")
        )

    def get_pending_feedback(self):
        return list(
            HumanDecision.objects
            .filter(
                feedback_status=HumanDecision.FeedbackStatus.PENDING
            )
            .select_related(
                "billing_record",
                "recommendation",
            )
            .order_by("created_at")
        )

    @transaction.atomic
    def mark_feedback_sent(
        self,
        human_decision_id,
        metadata=None,
    ):
        decision = self._lock_decision(human_decision_id)

        decision.feedback_status = (
            HumanDecision.FeedbackStatus.SENT
        )
        decision.feedback_sent_at = timezone.now()

        merged_metadata = dict(
            decision.feedback_metadata or {}
        )
        merged_metadata.update(metadata or {})
        decision.feedback_metadata = merged_metadata

        decision.save(
            update_fields=[
                "feedback_status",
                "feedback_sent_at",
                "feedback_metadata",
            ]
        )

        return decision

    @transaction.atomic
    def mark_feedback_failed(
        self,
        human_decision_id,
        metadata=None,
    ):
        decision = self._lock_decision(human_decision_id)

        decision.feedback_status = (
            HumanDecision.FeedbackStatus.FAILED
        )

        merged_metadata = dict(
            decision.feedback_metadata or {}
        )
        merged_metadata.update(metadata or {})
        decision.feedback_metadata = merged_metadata

        decision.save(
            update_fields=[
                "feedback_status",
                "feedback_metadata",
            ]
        )

        return decision

    def _lock_decision(self, human_decision_id):
        try:
            return (
                HumanDecision.objects
                .select_for_update()
                .get(
                    human_decision_id=human_decision_id
                )
            )
        except (HumanDecision.DoesNotExist, ValueError):
            raise ValueError("Human decision not found.")
