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
