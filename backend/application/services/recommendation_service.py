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

        if current_status != RecordStatus.RECOMMENDATION_PENDING.value:
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
            )

            return {
                "recordId": record_id,
                "status": RecordStatus.RECOMMENDATION_READY.value,
                "pending": False,
                "recommendation": recommendation,
            }

        except IntegrationException as error:
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
    ):
        if self.recommendation_repository is not None:
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
