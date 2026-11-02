
from django.test import TestCase

from apps.billing.models import BillingRecord, LineItem
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)


class OCRRecordUpdateTests(TestCase):

    def setUp(self):
        self.repository = DjangoBillingRecordRepository()
        self.record = BillingRecord.objects.create(
            status="OCR_PROCESSING"
        )

        self.data = {
            "bol_number": "BOL-100",
            "origin": "Syracuse",
            "supplier": "Supplier A",
            "status": "OCR_COMPLETE",
            "line_items": [
                {
                    "line_number": 1,
                    "product": "ULSD",
                    "net_gallons": 8500,
                    "gross_gallons": 8550,
                }
            ],
        }

    def test_updates_existing_record_without_creating_new_one(self):
        original_id = self.record.record_id

        updated = self.repository.update_from_ocr(
            original_id,
            self.data,
        )

        self.assertEqual(updated.record_id, original_id)
        self.assertEqual(BillingRecord.objects.count(), 1)

        self.record.refresh_from_db()
        self.assertEqual(self.record.bol_number, "BOL-100")
        self.assertEqual(self.record.status, "OCR_COMPLETE")

        self.assertEqual(
            LineItem.objects.filter(billing_record=self.record).count(),
            1,
        )

    def test_prevents_updates_after_human_decision(self):
        self.record.status = "APPROVED"
        self.record.save()

        with self.assertRaises(ValueError):
            self.repository.update_from_ocr(
                self.record.record_id,
                self.data,
            )

        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "APPROVED")
        self.assertIsNone(self.record.bol_number)
        self.assertEqual(LineItem.objects.count(), 0)
