from decimal import Decimal

from django.db import transaction
from django.db.models import Max

from apps.billing.models import BillingRecord
from apps.persistence.models import Recommendation
from core.enums.record_status import RecordStatus


class DjangoPersistenceRecommendationRepository:

    def store_revision(self, record_id, recommendation_data):
        with transaction.atomic():
            record = self._lock_record(record_id)

            return self._store_revision_locked(
                record,
                recommendation_data,
            )

    def store_revision_and_mark_ready(
        self,
        record_id,
        recommendation_data,
    ):
        with transaction.atomic():
            record = self._lock_record(record_id)

            recommendation = self._store_revision_locked(
                record,
                recommendation_data,
            )

            record.status = RecordStatus.RECOMMENDATION_READY.value
            record.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return recommendation

    def get_current(self, record_id):
        return (
            Recommendation.objects
            .filter(
                billing_record_id=record_id,
                is_current=True,
            )
            .first()
        )

    def list_history(self, record_id):
        return list(
            Recommendation.objects
            .filter(billing_record_id=record_id)
            .order_by("revision")
        )

    def _lock_record(self, record_id):
        try:
            return (
                BillingRecord.objects
                .select_for_update()
                .get(record_id=record_id)
            )
        except (BillingRecord.DoesNotExist, ValueError):
            raise ValueError("Billing record not found.")

    def _store_revision_locked(
        self,
        record,
        recommendation_data,
    ):
        if not isinstance(recommendation_data, dict):
            raise ValueError(
                "Recommendation data must be a dictionary."
            )

        recommendation_value = recommendation_data.get(
            "recommendation"
        )

        if not recommendation_value:
            raise ValueError(
                "Recommendation value is required."
            )

        Recommendation.objects.filter(
            billing_record=record,
            is_current=True,
        ).update(is_current=False)

        max_revision = (
            Recommendation.objects
            .filter(billing_record=record)
            .aggregate(max_revision=Max("revision"))
            .get("max_revision")
        )

        next_revision = (max_revision or 0) + 1

        confidence = recommendation_data.get("confidence")

        if confidence is not None:
            confidence = Decimal(str(confidence))

        return Recommendation.objects.create(
            billing_record=record,
            revision=next_revision,
            recommendation=recommendation_value,
            confidence=confidence,
            model_version=recommendation_data.get(
                "modelVersion"
            ),
            matched_terminal_log_id=recommendation_data.get(
                "matchedTerminalLogId"
            ),
            rationale=recommendation_data.get("rationale"),
            mapped_entities=recommendation_data.get(
                "mappedEntities"
            ) or {},
            exception_indicators=recommendation_data.get(
                "exceptionIndicators"
            ) or [],
            raw_response=recommendation_data,
            is_current=True,
        )
