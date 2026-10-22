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
class BillingRecordCorrectionApiTests(SimpleTestCase):

    def setUp(self):
        self.client = APIClient()

    @patch(
        "presentation.api.billing_views."
        "correction_service.correct_record_field"
    )
    def test_record_field_correction_returns_200(
        self,
        mock_correct,
    ):
        mock_correct.return_value = {
            "recordId": "rec_001",
            "field": "carrier",
            "oldValue": "ABC Transport",
            "newValue": "XYZ Transport",
            "status": "RECOMMENDATION_PENDING",
            "requiresReevaluation": True,
        }

        response = self.client.patch(
            "/api/v1/billing-records/rec_001/fields/carrier/",
            {
                "value": "XYZ Transport",
                "reviewedBy": "user_001",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["status"],
            "RECOMMENDATION_PENDING",
        )

    def test_missing_value_returns_400(self):
        response = self.client.patch(
            "/api/v1/billing-records/rec_001/fields/carrier/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "CORRECTED_VALUE_REQUIRED",
        )

    @patch(
        "presentation.api.billing_views."
        "correction_service.correct_record_field"
    )
    def test_unknown_record_returns_404(
        self,
        mock_correct,
    ):
        mock_correct.side_effect = ValueError(
            "Billing record not found."
        )

        response = self.client.patch(
            "/api/v1/billing-records/missing/fields/carrier/",
            {
                "value": "XYZ Transport",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    @patch(
        "presentation.api.billing_views."
        "correction_service.correct_record_field"
    )
    def test_invalid_correction_returns_400(
        self,
        mock_correct,
    ):
        mock_correct.side_effect = ValueError(
            "Field 'status' is not editable."
        )

        response = self.client.patch(
            "/api/v1/billing-records/rec_001/fields/status/",
            {
                "value": "APPROVED",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "INVALID_CORRECTION",
        )

    @patch(
        "presentation.api.billing_views."
        "correction_service.correct_record_field"
    )
    def test_invalid_workflow_returns_409(
        self,
        mock_correct,
    ):
        mock_correct.side_effect = ValueError(
            "Billing record cannot be corrected while in UPLOADED status."
        )

        response = self.client.patch(
            "/api/v1/billing-records/rec_001/fields/carrier/",
            {
                "value": "XYZ Transport",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["code"],
            "INVALID_WORKFLOW_TRANSITION",
        )

    @patch(
        "presentation.api.billing_views."
        "correction_service.correct_line_item_field"
    )
    def test_line_item_correction_returns_200(
        self,
        mock_correct,
    ):
        mock_correct.return_value = {
            "recordId": "rec_001",
            "lineItemId": "1",
            "field": "grossGallons",
            "oldValue": 8550.0,
            "newValue": 8545,
            "status": "RECOMMENDATION_PENDING",
            "requiresReevaluation": True,
        }

        response = self.client.patch(
            "/api/v1/billing-records/rec_001/"
            "line-items/1/grossGallons/",
            {
                "value": 8545,
                "reviewedBy": "user_001",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.data["requiresReevaluation"]
        )
class BillingRecordDecisionApiTests(SimpleTestCase):

    def setUp(self):
        self.client = APIClient()

    @patch(
        "presentation.api.billing_views."
        "human_decision_service.submit_decision"
    )
    def test_approve_decision_returns_200(
        self,
        mock_submit,
    ):
        mock_submit.return_value = {
            "recordId": "rec_001",
            "decision": "APPROVE",
            "previousStatus": "RECOMMENDATION_READY",
            "status": "APPROVED",
            "decidedBy": "user_001",
            "reason": "Reviewed and verified.",
        }

        response = self.client.post(
            "/api/v1/billing-records/rec_001/decision/",
            {
                "decision": "APPROVE",
                "decidedBy": "user_001",
                "reason": "Reviewed and verified.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["status"],
            "APPROVED",
        )

    def test_missing_decision_returns_400(self):
        response = self.client.post(
            "/api/v1/billing-records/rec_001/decision/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "DECISION_REQUIRED",
        )

    @patch(
        "presentation.api.billing_views."
        "human_decision_service.submit_decision"
    )
    def test_invalid_decision_returns_400(
        self,
        mock_submit,
    ):
        mock_submit.side_effect = ValueError(
            "Decision must be APPROVE, REJECT, or EXCEPTION."
        )

        response = self.client.post(
            "/api/v1/billing-records/rec_001/decision/",
            {
                "decision": "DELETE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "INVALID_DECISION",
        )

    @patch(
        "presentation.api.billing_views."
        "human_decision_service.submit_decision"
    )
    def test_unknown_record_returns_404(
        self,
        mock_submit,
    ):
        mock_submit.side_effect = ValueError(
            "Billing record not found."
        )

        response = self.client.post(
            "/api/v1/billing-records/missing/decision/",
            {
                "decision": "APPROVE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data["code"],
            "BILLING_RECORD_NOT_FOUND",
        )

    @patch(
        "presentation.api.billing_views."
        "human_decision_service.submit_decision"
    )
    def test_invalid_workflow_returns_409(
        self,
        mock_submit,
    ):
        mock_submit.side_effect = ValueError(
            "Invalid workflow transition: "
            "UPLOADED -> APPROVED"
        )

        response = self.client.post(
            "/api/v1/billing-records/rec_001/decision/",
            {
                "decision": "APPROVE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.data["code"],
            "INVALID_WORKFLOW_TRANSITION",
        )


class BillingRecordListApiTests(SimpleTestCase):

    def setUp(self):
        self.client = APIClient()

    @patch(
        "presentation.api.billing_views."
        "billing_record_service.list_records"
    )
    def test_list_records_returns_200(
        self,
        mock_list,
    ):
        mock_list.return_value = [
            {
                "recordId": "rec_001",
                "status": "RECOMMENDATION_READY",
            },
            {
                "recordId": "rec_002",
                "status": "NEEDS_REVIEW",
            },
        ]

        response = self.client.get(
            "/api/v1/billing-records/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            len(response.data["records"]),
            2,
        )        