from django.test import SimpleTestCase
from rest_framework.test import APIClient


class BillingRecordApiTests(SimpleTestCase):

    def setUp(self):
        self.client = APIClient()

    def test_get_billing_record(self):
        response = self.client.get(
            "/api/v1/billing-records/rec_001/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["recordId"],
            "rec_001",
        )

    def test_validate_billing_record(self):
        response = self.client.post(
            "/api/v1/billing-records/rec_001/validate/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["recordId"],
            "rec_001",
        )
        self.assertTrue(response.data["valid"])
        self.assertEqual(
            response.data["nextStatus"],
            "NEEDS_REVIEW",
        )

        codes = {
            item["code"]
            for item in response.data["reviewFlags"]
        }

        self.assertIn(
            "LOW_CONFIDENCE",
            codes,
        )
        self.assertIn(
            "MISSING_FIELD",
            codes,
        )

    def test_unknown_billing_record_returns_404(self):
        response = self.client.post(
            "/api/v1/billing-records/not-found/validate/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data["code"],
            "BILLING_RECORD_NOT_FOUND",
        )


from unittest.mock import patch

from core.exceptions.integration_exception import IntegrationException


class BillingRecordRecommendationApiTests(SimpleTestCase):

    def setUp(self):
        self.client = APIClient()

    def test_evaluate_billing_record_returns_200(self):
        response = self.client.post(
            "/api/v1/billing-records/rec_001/evaluate/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["recordId"],
            "rec_001",
        )
        self.assertEqual(
            response.data["status"],
            "RECOMMENDATION_READY",
        )
        self.assertFalse(response.data["pending"])

    def test_unknown_record_returns_404(self):
        response = self.client.post(
            "/api/v1/billing-records/missing/evaluate/",
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data["code"],
            "BILLING_RECORD_NOT_FOUND",
        )

    @patch(
        "presentation.api.billing_views."
        "recommendation_service.evaluate_record_by_id"
    )
    def test_retryable_failure_returns_202(
        self,
        mock_evaluate,
    ):
        mock_evaluate.return_value = {
            "recordId": "rec_001",
            "status": "RECOMMENDATION_PENDING",
            "pending": True,
            "error": {
                "code": "TEAM_A_UNAVAILABLE",
                "message": "Team A service is unavailable.",
                "details": None,
            },
        }

        response = self.client.post(
            "/api/v1/billing-records/rec_001/evaluate/",
            format="json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data["pending"])
        self.assertEqual(
            response.data["status"],
            "RECOMMENDATION_PENDING",
        )

    @patch(
        "presentation.api.billing_views."
        "recommendation_service.evaluate_record_by_id"
    )
    def test_invalid_workflow_returns_409(
        self,
        mock_evaluate,
    ):
        mock_evaluate.side_effect = ValueError(
            "Invalid workflow transition: "
            "UPLOADED -> RECOMMENDATION_PENDING"
        )

        response = self.client.post(
            "/api/v1/billing-records/rec_001/evaluate/",
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["code"],
            "INVALID_WORKFLOW_TRANSITION",
        )

    @patch(
        "presentation.api.billing_views."
        "recommendation_service.evaluate_record_by_id"
    )
    def test_non_retryable_team_a_failure_returns_502(
        self,
        mock_evaluate,
    ):
        mock_evaluate.side_effect = IntegrationException(
            "TEAM_A_BAD_REQUEST",
            "Team A rejected the request.",
            status_code=400,
            retryable=False,
        )

        response = self.client.post(
            "/api/v1/billing-records/rec_001/evaluate/",
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.data["code"],
            "TEAM_A_BAD_REQUEST",
        )
