from copy import deepcopy
from unittest import TestCase

from application.services.billing_validation_service import BillingValidationService
from application.validators.billing_record_validator import BillingRecordValidator


class FakeBillingRecordProvider:

    def __init__(self, record=None):
        self.record = record

    def get_by_id(self, record_id):
        return self.record


def clean_record():
    return {
        "recordId": "rec_test",
        "fields": {
            "transactionDate": {
                "rawValue": "09/29/2026",
                "normalizedValue": "2026-09-29",
                "confidence": 0.99,
                "quality": "OK",
            },
            "carrier": {
                "rawValue": "ABC Transport",
                "normalizedValue": "ABC Transport",
                "confidence": 0.99,
                "quality": "OK",
            },
        },
        "lineItems": [
            {
                "lineItemId": 1,
                "product": {
                    "normalizedValue": "RUL 87",
                    "quality": "OK",
                },
                "grossGallons": {
                    "normalizedValue": 8550,
                    "quality": "OK",
                },
                "netGallons": {
                    "normalizedValue": 8500,
                    "quality": "OK",
                },
                "e3StockId": {
                    "normalizedValue": "UX",
                    "quality": "OK",
                },
            }
        ],
    }


class BillingValidationServiceTests(TestCase):

    def make_service(self, record):
        return BillingValidationService(
            billing_record_provider=FakeBillingRecordProvider(record),
            validator=BillingRecordValidator(),
        )

    def test_clean_record_can_continue(self):
        result = self.make_service(clean_record()).validate_record("rec_test")

        self.assertTrue(result["valid"])
        self.assertEqual(result["blockingIssues"], [])
        self.assertEqual(result["reviewFlags"], [])
        self.assertEqual(
            result["nextStatus"],
            "RECOMMENDATION_PENDING",
        )

    def test_low_confidence_creates_review_flag(self):
        record = clean_record()

        record["fields"]["carrier"]["quality"] = "LOW_CONFIDENCE"
        record["fields"]["carrier"]["confidence"] = 0.68

        result = self.make_service(record).validate_record("rec_test")

        self.assertTrue(result["valid"])
        self.assertEqual(result["blockingIssues"], [])
        self.assertEqual(len(result["reviewFlags"]), 1)
        self.assertEqual(
            result["reviewFlags"][0]["code"],
            "LOW_CONFIDENCE",
        )
        self.assertEqual(
            result["nextStatus"],
            "NEEDS_REVIEW",
        )

    def test_missing_field_creates_review_flag(self):
        record = clean_record()

        record["lineItems"][0]["e3StockId"] = {
            "rawValue": None,
            "normalizedValue": None,
            "confidence": None,
            "quality": "MISSING",
        }

        result = self.make_service(record).validate_record("rec_test")

        self.assertTrue(result["valid"])
        self.assertEqual(
            result["reviewFlags"][0]["code"],
            "MISSING_FIELD",
        )
        self.assertEqual(
            result["nextStatus"],
            "NEEDS_REVIEW",
        )

    def test_negative_gallons_is_blocking(self):
        record = clean_record()

        record["lineItems"][0]["grossGallons"][
            "normalizedValue"
        ] = -10

        result = self.make_service(record).validate_record("rec_test")

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["blockingIssues"][0]["code"],
            "NEGATIVE_GALLONS",
        )
        self.assertEqual(
            result["nextStatus"],
            "EXCEPTION",
        )

    def test_non_numeric_gallons_is_blocking(self):
        record = clean_record()

        record["lineItems"][0]["grossGallons"][
            "normalizedValue"
        ] = "not-a-number"

        result = self.make_service(record).validate_record("rec_test")

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["blockingIssues"][0]["code"],
            "INVALID_NUMERIC_VALUE",
        )

    def test_invalid_date_is_blocking(self):
        record = clean_record()

        record["fields"]["transactionDate"][
            "normalizedValue"
        ] = "09-29-2026"

        result = self.make_service(record).validate_record("rec_test")

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["blockingIssues"][0]["code"],
            "INVALID_DATE",
        )

    def test_empty_line_items_is_blocking(self):
        record = clean_record()
        record["lineItems"] = []

        result = self.make_service(record).validate_record("rec_test")

        self.assertFalse(result["valid"])
        self.assertEqual(
            result["blockingIssues"][0]["code"],
            "INVALID_LINE_ITEMS",
        )

    def test_unknown_record_raises_error(self):
        service = self.make_service(None)

        with self.assertRaises(ValueError):
            service.validate_record("does-not-exist")
