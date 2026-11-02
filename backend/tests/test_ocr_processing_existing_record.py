
from django.test import TestCase

from apps.billing.models import BillingRecord, LineItem
from application.services.ocr_processing_service import OCRProcessingService
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter


class OCRProcessingExistingRecordTests(TestCase):

    def setUp(self):
        self.record = BillingRecord.objects.create(
            status="OCR_PROCESSING"
        )
        self.service = OCRProcessingService(
            adapter=BolLabAdapter(),
            billing_record_repository=DjangoBillingRecordRepository(),
        )

    def test_valid_ocr_updates_existing_record(self):
        extraction = {
            "bol_number": "BOL-100",
            "origin": "Syracuse",
            "supplier": "Supplier A",
            "transaction_date": "2026-09-17",
            "products": [
                {
                    "product": "ULSD",
                    "net_gallons": "8500",
                    "gross_gallons": "8550",
                }
            ],
        }

        result = self.service.persist_extraction_for_record(
            self.record.record_id,
            extraction,
        )

        self.record.refresh_from_db()

        self.assertEqual(
            result["recordId"],
            str(self.record.record_id),
        )
        self.assertEqual(BillingRecord.objects.count(), 1)
        self.assertEqual(self.record.bol_number, "BOL-100")
        self.assertEqual(self.record.status, "OCR_COMPLETE")
        self.assertEqual(
            LineItem.objects.filter(billing_record=self.record).count(),
            1,
        )

    def test_missing_bol_number_needs_review(self):
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

        result = self.service.persist_extraction_for_record(
            self.record.record_id,
            extraction,
        )

        self.record.refresh_from_db()

        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertEqual(self.record.status, "NEEDS_REVIEW")
        self.assertEqual(BillingRecord.objects.count(), 1)
