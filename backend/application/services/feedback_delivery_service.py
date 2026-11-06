"""Durable, leased feedback outbox. No network call holds a DB transaction."""
import os
import uuid
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.persistence.models import HumanDecision
from core.exceptions.integration_exception import IntegrationException
from infrastructure.team_a.client import TeamAClient


class FeedbackDeliveryService:
    LEASE_SECONDS = 120

    def __init__(self, client=None):
        self.client = client

    def _client(self):
        if self.client is not None:
            return self.client
        if os.getenv("USE_MOCK_TEAM_A", "true").lower() != "false":
            raise RuntimeError("Live Team A feedback is not configured.")
        base_url, key = os.getenv("TEAM_A_BASE_URL"), os.getenv("TEAM_A_API_KEY")
        if not base_url or not key:
            raise RuntimeError("Team A feedback configuration is incomplete.")
        return TeamAClient(base_url=base_url, api_key=key, timeout=30)

    @transaction.atomic
    def claim(self, decision_id=None):
        now = timezone.now()
        timestamp = now.timestamp()
        query = HumanDecision.objects.filter(
            feedback_status__in=["PENDING", "FAILED"],
            feedback_metadata__has_key="payload",
        ).filter(
            ~Q(feedback_metadata__has_key="retryable") | Q(feedback_metadata__retryable=True),
        ).filter(
            ~Q(feedback_metadata__has_key="leaseUntil") | Q(feedback_metadata__leaseUntil__lte=timestamp),
        ).filter(
            ~Q(feedback_metadata__has_key="nextAttemptAt") | Q(feedback_metadata__nextAttemptAt__lte=timestamp),
        ).order_by("created_at", "pk")
        if decision_id:
            query = query.filter(pk=decision_id)
        # LIMIT 1 avoids fetching/locking the retry backlog on every poll.
        decision = query.select_for_update(skip_locked=True).first()
        if decision is None:
            return None
        meta = dict(decision.feedback_metadata)
        token = str(uuid.uuid4())
        meta.update({"leaseToken": token,
                     "leaseUntil": (now + timedelta(seconds=self.LEASE_SECONDS)).timestamp(),
                     "attempts": meta.get("attempts", 0) + 1,
                     "lastAttemptAt": now.isoformat()})
        decision.feedback_metadata = meta
        decision.save(update_fields=["feedback_metadata"])
        return decision.pk, token, meta["payload"]

    def process_next(self, decision_id=None):
        claim = self.claim(decision_id)
        if claim is None:
            return None
        pk, token, payload = claim
        try:
            ack = self._client().send_feedback(payload)
        except Exception as error:
            # Persist only controlled categories, never remote text or credentials.
            retryable = error.retryable if isinstance(error, IntegrationException) else True
            return self._finish(pk, token, retryable=retryable, failed=True)
        return self._finish(pk, token, acknowledgment=ack)

    @transaction.atomic
    def _finish(self, pk, token, *, acknowledgment=None, retryable=True, failed=False):
        decision = HumanDecision.objects.select_for_update().get(pk=pk)
        meta = dict(decision.feedback_metadata)
        if meta.get("leaseToken") != token:
            return None
        meta.pop("leaseToken", None)
        meta.pop("leaseUntil", None)
        if failed:
            decision.feedback_status = "FAILED"
            meta.update({"retryable": retryable,
                         "errorCode": "DELIVERY_UNAVAILABLE" if retryable else "DELIVERY_REJECTED",
                         "nextAttemptAt": (timezone.now() + timedelta(
                             seconds=min(3600, 30 * 2 ** min(meta["attempts"] - 1, 7))
                         )).timestamp()})
        else:
            decision.feedback_status = "SENT"
            decision.feedback_sent_at = timezone.now()
            meta.update({"acknowledgment": acknowledgment, "retryable": False})
            meta.pop("errorCode", None)
            meta.pop("nextAttemptAt", None)
        decision.feedback_metadata = meta
        decision.save(update_fields=["feedback_status", "feedback_sent_at", "feedback_metadata"])
        return {"humanDecisionId": str(pk), "status": decision.feedback_status}
