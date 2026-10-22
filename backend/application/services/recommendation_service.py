from core.enums.record_status import RecordStatus
from core.exceptions.integration_exception import IntegrationException


class RecommendationService:

    def __init__(
        self,
        recommendation_provider,
        billing_record_provider=None,
        workflow_service=None,
    ):
        self.recommendation_provider = recommendation_provider
        self.billing_record_provider = billing_record_provider
        self.workflow_service = workflow_service

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

        # If already pending, this is a retry attempt.
        if current_status != RecordStatus.RECOMMENDATION_PENDING.value:
            self.workflow_service.validate_transition(
                current_status,
                RecordStatus.RECOMMENDATION_PENDING.value,
            )

        try:
            recommendation = self.recommendation_provider.evaluate(record)

            self.workflow_service.validate_transition(
                RecordStatus.RECOMMENDATION_PENDING.value,
                RecordStatus.RECOMMENDATION_READY.value,
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
