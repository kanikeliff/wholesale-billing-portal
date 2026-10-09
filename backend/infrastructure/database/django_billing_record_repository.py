from django.db import transaction

from apps.billing.models import BillingRecord, LineItem
from domain.repositories.billing_record_repository import BillingRecordRepository


class DjangoBillingRecordRepository(BillingRecordRepository):

    @transaction.atomic
    def create_billing_record(self, data):
        record_data = data.copy()
        line_items_data = record_data.pop("line_items", [])

        record = BillingRecord.objects.create(**record_data)

        for item_data in line_items_data:
            LineItem.objects.create(
                billing_record=record,
                **item_data,
            )

        return record

    def get_billing_record(self, record_id):
        return (
            BillingRecord.objects
            .prefetch_related("line_items")
            .get(record_id=record_id)
        )
