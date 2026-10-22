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
