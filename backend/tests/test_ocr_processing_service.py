from django.test import SimpleTestCase

from application.services.ocr_processing_service import (
    OCRProcessingService,
)
from infrastructure.ocr.bol_lab_adapter import (
    BolLabAdapter,
)


class FakeRecord:
    record_id = "record-001"

    def __init__(self, status):
        self.status = status


class FakeBillingRecordRepository:

    def __init__(self):
        self.created = []

    def create_billing_record(self, data):
        self.created.append(data)
        return FakeRecord(data["status"])


class OCRProcessingServiceTests(SimpleTestCase):

    def setUp(self):
        self.repository = FakeBillingRecordRepository()

        self.service = OCRProcessingService(
            adapter=BolLabAdapter(),
            billing_record_repository=self.repository,
        )

    def test_valid_extraction_is_persisted(self):
        extraction = {
            "bol_number": "BOL-100",
            "contract_number": "LIFT-1",
            "origin": "Syracuse",
            "supplier": "Supplier A",
            "carrier": "Mirabito",
            "transaction_date": "2026-09-17",
            "destination": "Binghamton",
            "products": [
                {
                    "product": "ULSD",
                    "product_code": "403100",
                    "net_gallons": "8500",
                    "gross_gallons": "8550",
                    "e3_stock_id": None,
                }
            ],
        }

        result = self.service.persist_extraction(extraction)

        self.assertEqual(
            result["recordId"],
            "record-001",
        )

        self.assertEqual(
            result["status"],
            "OCR_COMPLETE",
        )

        created = self.repository.created[0]

        self.assertEqual(
            created["bol_number"],
            "BOL-100",
        )

        self.assertEqual(
            created["line_items"][0]["product"],
            "ULSD",
        )

        self.assertEqual(
            created["line_items"][0]["net_gallons"],
            8500.0,
        )

    def test_missing_required_field_needs_review(self):
        extraction = {
            "bol_number": None,
            "origin": "Syracuse",
            "transaction_date": "2026-09-17",
            "products": [
                {
                    "product": "ULSD",
                    "net_gallons": "8500",
                    "gross_gallons": "8550",
                }
            ],
        }

        result = self.service.persist_extraction(extraction)

        self.assertEqual(
            result["status"],
            "NEEDS_REVIEW",
        )

    def test_empty_products_needs_review(self):
        extraction = {
            "bol_number": "BOL-100",
            "origin": "Syracuse",
            "transaction_date": "2026-09-17",
            "products": [],
        }

        result = self.service.persist_extraction(extraction)

        self.assertEqual(
            result["status"],
            "NEEDS_REVIEW",
        )
