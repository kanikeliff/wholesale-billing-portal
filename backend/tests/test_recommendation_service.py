from django.test import SimpleTestCase

from application.services.recommendation_service import RecommendationService
from application.services.workflow_service import WorkflowService
from core.exceptions.integration_exception import IntegrationException


class FakeBillingRecordProvider:

    def __init__(self, record=None):
        self.record = record

    def get_by_id(self, record_id):
        return self.record


class FakeRecommendationProvider:

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def evaluate(self, record):
        self.calls += 1

        if self.error:
            raise self.error

        return self.response


class RecommendationServiceTests(SimpleTestCase):

    def build_service(
        self,
        *,
        record,
        response=None,
        error=None,
    ):
        return RecommendationService(
            recommendation_provider=FakeRecommendationProvider(
                response=response,
                error=error,
            ),
            billing_record_provider=FakeBillingRecordProvider(record),
            workflow_service=WorkflowService(),
        )

    def test_successful_evaluation_becomes_ready(self):
        service = self.build_service(
            record={
                "recordId": "rec_001",
                "status": "OCR_COMPLETE",
            },
            response={
                "recommendation": "APPROVE_RECOMMENDED",
                "confidence": 0.95,
            },
        )

        result = service.evaluate_record_by_id("rec_001")

        self.assertEqual(
            result["status"],
            "RECOMMENDATION_READY",
        )
        self.assertFalse(result["pending"])

    def test_ready_record_can_be_re_evaluated(self):
        service = self.build_service(
            record={
                "recordId": "rec_001",
                "status": "RECOMMENDATION_READY",
            },
            response={
                "recommendation": "REVIEW_REQUIRED",
                "confidence": 0.70,
            },
        )

        result = service.evaluate_record_by_id("rec_001")

        self.assertEqual(
            result["status"],
            "RECOMMENDATION_READY",
        )

    def test_pending_record_can_be_retried(self):
        service = self.build_service(
            record={
                "recordId": "rec_001",
                "status": "RECOMMENDATION_PENDING",
            },
            response={
                "recommendation": "APPROVE_RECOMMENDED",
                "confidence": 0.91,
            },
        )

        result = service.evaluate_record_by_id("rec_001")

        self.assertEqual(
            result["status"],
            "RECOMMENDATION_READY",
        )

    def test_retryable_failure_stays_pending(self):
        service = self.build_service(
            record={
                "recordId": "rec_001",
                "status": "OCR_COMPLETE",
            },
            error=IntegrationException(
                "TEAM_A_UNAVAILABLE",
                "Team A service is unavailable.",
                status_code=503,
                retryable=True,
            ),
        )

        result = service.evaluate_record_by_id("rec_001")

        self.assertEqual(
            result["status"],
            "RECOMMENDATION_PENDING",
        )
        self.assertTrue(result["pending"])

    def test_non_retryable_failure_is_raised(self):
        service = self.build_service(
            record={
                "recordId": "rec_001",
                "status": "OCR_COMPLETE",
            },
            error=IntegrationException(
                "TEAM_A_BAD_REQUEST",
                "Team A rejected the request.",
                status_code=400,
                retryable=False,
            ),
        )

        with self.assertRaises(IntegrationException):
            service.evaluate_record_by_id("rec_001")

    def test_unknown_record_raises_error(self):
        service = self.build_service(
            record=None,
            response={},
        )

        with self.assertRaisesMessage(
            ValueError,
            "Billing record not found.",
        ):
            service.evaluate_record_by_id("missing")

    def test_invalid_workflow_transition_is_rejected(self):
        service = self.build_service(
            record={
                "recordId": "rec_001",
                "status": "UPLOADED",
            },
            response={},
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid workflow transition",
        ):
            service.evaluate_record_by_id("rec_001")


class FakeBillingRecordRepository:

    def __init__(self):
        self.status_updates = []

    def update_status(self, record_id, status):
        self.status_updates.append(
            {
                "recordId": record_id,
                "status": status,
            }
        )


class FakeRecommendationRepository:

    def __init__(self):
        self.atomic_calls = []

    def store_revision_and_mark_ready(
        self,
        record_id,
        recommendation_data,
    ):
        self.atomic_calls.append(
            {
                "recordId": record_id,
                "recommendation": recommendation_data,
            }
        )


class RecommendationPersistenceTests(SimpleTestCase):

    def test_status_is_persisted_as_pending_before_evaluation(self):
        billing_repository = FakeBillingRecordRepository()

        service = RecommendationService(
            recommendation_provider=FakeRecommendationProvider(
                response={
                    "recommendation": "APPROVE_RECOMMENDED",
                    "confidence": 0.95,
                }
            ),
            billing_record_provider=FakeBillingRecordProvider(
                {
                    "recordId": "rec_001",
                    "status": "OCR_COMPLETE",
                }
            ),
            workflow_service=WorkflowService(),
            billing_record_repository=billing_repository,
        )

        service.evaluate_record_by_id("rec_001")

        self.assertEqual(
            billing_repository.status_updates[0],
            {
                "recordId": "rec_001",
                "status": "RECOMMENDATION_PENDING",
            },
        )

    def test_success_uses_atomic_recommendation_persistence(self):
        billing_repository = FakeBillingRecordRepository()
        recommendation_repository = FakeRecommendationRepository()

        recommendation = {
            "recommendation": "APPROVE_RECOMMENDED",
            "confidence": 0.95,
        }

        service = RecommendationService(
            recommendation_provider=FakeRecommendationProvider(
                response=recommendation,
            ),
            billing_record_provider=FakeBillingRecordProvider(
                {
                    "recordId": "rec_001",
                    "status": "OCR_COMPLETE",
                }
            ),
            workflow_service=WorkflowService(),
            billing_record_repository=billing_repository,
            recommendation_repository=recommendation_repository,
        )

        result = service.evaluate_record_by_id("rec_001")

        self.assertEqual(
            result["status"],
            "RECOMMENDATION_READY",
        )

        self.assertEqual(
            len(recommendation_repository.atomic_calls),
            1,
        )

        self.assertEqual(
            recommendation_repository.atomic_calls[0]["recordId"],
            "rec_001",
        )

        self.assertEqual(
            recommendation_repository.atomic_calls[0]["recommendation"],
            recommendation,
        )

    def test_retryable_failure_leaves_record_pending(self):
        billing_repository = FakeBillingRecordRepository()
        recommendation_repository = FakeRecommendationRepository()

        service = RecommendationService(
            recommendation_provider=FakeRecommendationProvider(
                error=IntegrationException(
                    "TEAM_A_UNAVAILABLE",
                    "Team A service is unavailable.",
                    status_code=503,
                    retryable=True,
                )
            ),
            billing_record_provider=FakeBillingRecordProvider(
                {
                    "recordId": "rec_001",
                    "status": "OCR_COMPLETE",
                }
            ),
            workflow_service=WorkflowService(),
            billing_record_repository=billing_repository,
            recommendation_repository=recommendation_repository,
        )

        result = service.evaluate_record_by_id("rec_001")

        self.assertTrue(result["pending"])

        self.assertEqual(
            billing_repository.status_updates,
            [
                {
                    "recordId": "rec_001",
                    "status": "RECOMMENDATION_PENDING",
                }
            ],
        )

        self.assertEqual(
            recommendation_repository.atomic_calls,
            [],
        )

    def test_already_pending_record_is_not_written_pending_again(self):
        billing_repository = FakeBillingRecordRepository()

        service = RecommendationService(
            recommendation_provider=FakeRecommendationProvider(
                response={
                    "recommendation": "REVIEW_REQUIRED",
                    "confidence": 0.70,
                }
            ),
            billing_record_provider=FakeBillingRecordProvider(
                {
                    "recordId": "rec_001",
                    "status": "RECOMMENDATION_PENDING",
                }
            ),
            workflow_service=WorkflowService(),
            billing_record_repository=billing_repository,
        )

        service.evaluate_record_by_id("rec_001")

        self.assertNotIn(
            {
                "recordId": "rec_001",
                "status": "RECOMMENDATION_PENDING",
            },
            billing_repository.status_updates,
        )
