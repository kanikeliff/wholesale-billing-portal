from django.test import SimpleTestCase

from application.services.correction_service import CorrectionService
from application.services.workflow_service import WorkflowService


class FakeBillingRecordProvider:

    def __init__(self, record=None):
        self.record = record

    def get_by_id(self, record_id):
        return self.record


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


class FakeCorrectionRepository:

    def __init__(self):
        self.record_corrections = []
        self.line_item_corrections = []

    def apply_record_field_correction(
        self,
        **kwargs,
    ):
        self.record_corrections.append(kwargs)

    def apply_line_item_correction(
        self,
        **kwargs,
    ):
        self.line_item_corrections.append(kwargs)


def build_record(status="NEEDS_REVIEW"):
    return {
        "recordId": "rec_001",
        "status": status,
        "fields": {
            "carrier": {
                "rawValue": "ABC Transport",
                "normalizedValue": "ABC Transport",
                "confidence": 0.68,
                "quality": "LOW_CONFIDENCE",
            },
            "origin": {
                "rawValue": "Albany Terminal",
                "normalizedValue": "Albany Terminal",
                "confidence": 0.97,
                "quality": "OK",
            },
        },
        "lineItems": [
            {
                "lineItemId": 1,
                "product": {
                    "rawValue": "RUL 87 ETH",
                    "normalizedValue": "RUL 87 ETH",
                },
                "grossGallons": {
                    "rawValue": "8550",
                    "normalizedValue": 8550.0,
                },
                "netGallons": {
                    "rawValue": "8500",
                    "normalizedValue": 8500.0,
                },
                "e3StockId": {
                    "rawValue": None,
                    "normalizedValue": None,
                },
            }
        ],
    }


class CorrectionServiceTests(SimpleTestCase):

    def build_service(
        self,
        record,
        *,
        correction_repository=None,
        billing_repository=None,
    ):
        return CorrectionService(
            billing_record_provider=FakeBillingRecordProvider(
                record
            ),
            correction_repository=correction_repository,
            billing_record_repository=billing_repository,
            workflow_service=WorkflowService(),
        )

    def test_record_field_correction_is_accepted(self):
        correction_repository = FakeCorrectionRepository()
        billing_repository = FakeBillingRecordRepository()

        service = self.build_service(
            build_record(),
            correction_repository=correction_repository,
            billing_repository=billing_repository,
        )

        result = service.correct_record_field(
            "rec_001",
            "carrier",
            "XYZ Transport",
            reviewed_by="user_001",
        )

        self.assertEqual(
            result["oldValue"],
            "ABC Transport",
        )
        self.assertEqual(
            result["newValue"],
            "XYZ Transport",
        )
        self.assertEqual(
            result["status"],
            "RECOMMENDATION_PENDING",
        )
        self.assertTrue(
            result["requiresReevaluation"]
        )

    def test_record_field_correction_preserves_original_evidence(self):
        record = build_record()
        original_raw_value = (
            record["fields"]["carrier"]["rawValue"]
        )

        service = self.build_service(record)

        service.correct_record_field(
            "rec_001",
            "carrier",
            "XYZ Transport",
        )

        self.assertEqual(
            record["fields"]["carrier"]["rawValue"],
            original_raw_value,
        )

    def test_correction_is_sent_to_repository(self):
        correction_repository = FakeCorrectionRepository()

        service = self.build_service(
            build_record(),
            correction_repository=correction_repository,
        )

        service.correct_record_field(
            "rec_001",
            "carrier",
            "XYZ Transport",
            reviewed_by="user_001",
        )

        self.assertEqual(
            len(
                correction_repository.record_corrections
            ),
            1,
        )

        correction = (
            correction_repository.record_corrections[0]
        )

        self.assertEqual(
            correction["old_value"],
            "ABC Transport",
        )
        self.assertEqual(
            correction["new_value"],
            "XYZ Transport",
        )

    def test_correction_marks_record_pending(self):
        billing_repository = FakeBillingRecordRepository()

        service = self.build_service(
            build_record(),
            billing_repository=billing_repository,
        )

        service.correct_record_field(
            "rec_001",
            "carrier",
            "XYZ Transport",
        )

        self.assertEqual(
            billing_repository.status_updates,
            [
                {
                    "recordId": "rec_001",
                    "status": "RECOMMENDATION_PENDING",
                }
            ],
        )

    def test_ready_record_can_be_corrected(self):
        service = self.build_service(
            build_record(
                status="RECOMMENDATION_READY"
            )
        )

        result = service.correct_record_field(
            "rec_001",
            "carrier",
            "XYZ Transport",
        )

        self.assertEqual(
            result["status"],
            "RECOMMENDATION_PENDING",
        )

    def test_uploaded_record_cannot_be_corrected(self):
        service = self.build_service(
            build_record(status="UPLOADED")
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot be corrected",
        ):
            service.correct_record_field(
                "rec_001",
                "carrier",
                "XYZ Transport",
            )

    def test_non_editable_record_field_is_rejected(self):
        service = self.build_service(
            build_record()
        )

        with self.assertRaisesRegex(
            ValueError,
            "not editable",
        ):
            service.correct_record_field(
                "rec_001",
                "status",
                "APPROVED",
            )

    def test_line_item_correction_is_accepted(self):
        correction_repository = FakeCorrectionRepository()

        service = self.build_service(
            build_record(),
            correction_repository=correction_repository,
        )

        result = service.correct_line_item_field(
            "rec_001",
            1,
            "grossGallons",
            8545,
            reviewed_by="user_001",
        )

        self.assertEqual(
            result["oldValue"],
            8550.0,
        )
        self.assertEqual(
            result["newValue"],
            8545,
        )

        self.assertEqual(
            len(
                correction_repository.line_item_corrections
            ),
            1,
        )

    def test_negative_gallons_are_rejected(self):
        service = self.build_service(
            build_record()
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot be negative",
        ):
            service.correct_line_item_field(
                "rec_001",
                1,
                "grossGallons",
                -100,
            )

    def test_non_numeric_gallons_are_rejected(self):
        service = self.build_service(
            build_record()
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be numeric",
        ):
            service.correct_line_item_field(
                "rec_001",
                1,
                "netGallons",
                "abc",
            )

    def test_unknown_line_item_is_rejected(self):
        service = self.build_service(
            build_record()
        )

        with self.assertRaisesMessage(
            ValueError,
            "Line item not found.",
        ):
            service.correct_line_item_field(
                "rec_001",
                999,
                "product",
                "ULSD",
            )

    def test_unknown_record_is_rejected(self):
        service = self.build_service(None)

        with self.assertRaisesMessage(
            ValueError,
            "Billing record not found.",
        ):
            service.correct_record_field(
                "missing",
                "carrier",
                "XYZ Transport",
            )
