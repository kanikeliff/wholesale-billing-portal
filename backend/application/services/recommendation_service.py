from core.enums.record_status import RecordStatus
from core.exceptions.integration_exception import IntegrationException


class RecommendationService:

    def __init__(
        self,
        recommendation_provider,
        billing_record_provider=None,
        workflow_service=None,
        billing_record_repository=None,
        recommendation_repository=None,
    ):
        self.recommendation_provider = recommendation_provider
        self.billing_record_provider = billing_record_provider
        self.workflow_service = workflow_service
        self.billing_record_repository = billing_record_repository
        self.recommendation_repository = recommendation_repository

    def evaluate_record(self, record):
        if record is None:
            raise ValueError("Billing record is required.")

        return self.recommendation_provider.evaluate(record)

    def evaluate_record_by_id(self, record_id):
        if self.billing_record_provider is None:
            raise ValueError("Billing record provider is required.")

        if self.workflow_service is None:
            raise ValueError("Workflow service is required.")

        record = self.billing_record_provider.get_by_id(record_id)

        if record is None:
            raise ValueError("Billing record not found.")

        current_status = record.get("status")

        evaluation_version = None
        start_method = getattr(self.billing_record_repository, "start_recommendation", None)
        if start_method is not None and record.get("updatedAt"):
            evaluation_version = start_method(record_id, record["updatedAt"])
        elif current_status != RecordStatus.RECOMMENDATION_PENDING.value:
            self.workflow_service.validate_transition(
                current_status,
                RecordStatus.RECOMMENDATION_PENDING.value,
            )

            self._persist_status(
                record_id,
                RecordStatus.RECOMMENDATION_PENDING.value,
            )

        try:
            recommendation = self.recommendation_provider.evaluate(record)

            self.workflow_service.validate_transition(
                RecordStatus.RECOMMENDATION_PENDING.value,
                RecordStatus.RECOMMENDATION_READY.value,
            )

            self._persist_success(
                record_id,
                recommendation,
                expected_updated_at=evaluation_version,
            )

            return {
                "recordId": record_id,
                "status": RecordStatus.RECOMMENDATION_READY.value,
                "pending": False,
                "recommendation": recommendation,
            }

        except IntegrationException as error:
            current_check = getattr(self.billing_record_repository, "evaluation_is_current", None)
            if evaluation_version is not None and current_check is not None and not current_check(record_id, evaluation_version):
                raise ValueError("Billing record changed during evaluation; reload and evaluate again.") from None
            if error.retryable:
                return {
                    "recordId": record_id,
                    "status": RecordStatus.RECOMMENDATION_PENDING.value,
                    "pending": True,
                    "error": error.to_dict(),
                }

            raise

    def _persist_status(self, record_id, status):
        if self.billing_record_repository is None:
            return

        self.billing_record_repository.update_status(
            record_id,
            status,
        )

    def _persist_success(
        self,
        record_id,
        recommendation,
        expected_updated_at=None,
    ):
        if self.recommendation_repository is not None:
            guarded_method = getattr(self.recommendation_repository, "store_revision_if_current", None)
            if expected_updated_at is not None and guarded_method is not None:
                guarded_method(record_id, recommendation, expected_updated_at)
                return
            atomic_method = getattr(
                self.recommendation_repository,
                "store_revision_and_mark_ready",
                None,
            )

            if atomic_method is not None:
                atomic_method(
                    record_id,
                    recommendation,
                )
                return

            self.recommendation_repository.store_revision(
                record_id,
                recommendation,
            )

        self._persist_status(
            record_id,
            RecordStatus.RECOMMENDATION_READY.value,
        )
