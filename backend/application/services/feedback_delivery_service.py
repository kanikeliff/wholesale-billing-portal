"""Durable, leased feedback outbox. No network call holds a DB transaction."""
import os
import uuid
from datetime import timedelta

from django.db import transaction
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
        query = HumanDecision.objects.filter(
            feedback_status__in=["PENDING", "FAILED"],
            feedback_metadata__has_key="payload",
        ).order_by("created_at", "pk")
        if decision_id:
            query = query.filter(pk=decision_id)
        # Short locks coordinate web/worker processes. A lease survives crashes.
        for decision in query.select_for_update(skip_locked=True).iterator():
            meta = dict(decision.feedback_metadata)
            if not meta.get("retryable", True):
                continue
            if float(meta.get("leaseUntil", 0)) > now.timestamp():
                continue
            if float(meta.get("nextAttemptAt", 0)) > now.timestamp():
                continue
            token = str(uuid.uuid4())
            meta.update({"leaseToken": token,
                         "leaseUntil": (now + timedelta(seconds=self.LEASE_SECONDS)).timestamp(),
                         "attempts": meta.get("attempts", 0) + 1,
                         "lastAttemptAt": now.isoformat()})
            decision.feedback_metadata = meta
            decision.save(update_fields=["feedback_metadata"])
            return decision.pk, token, meta["payload"]
        return None

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
