from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.billing.models import BillingRecord, LineItem
from domain.repositories.billing_record_repository import BillingRecordRepository


class DjangoBillingRecordRepository(BillingRecordRepository):

    RECORD_FIELD_MAP = {
        "bolNumber": "bol_number",
        "contractLifting": "contract_lifting",
        "origin": "origin",
        "supplier": "supplier",
        "carrier": "carrier",
        "transactionDate": "transaction_date",
        "destination": "destination",
    }

    LINE_ITEM_FIELD_MAP = {
        "product": "product",
        "grossGallons": "gross_gallons",
        "netGallons": "net_gallons",
        "e3StockId": "e3_stock_id",
    }

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

    def get_by_id(self, record_id):
        try:
            record = self.get_billing_record(record_id)
        except (BillingRecord.DoesNotExist, ValueError):
            return None

        return self._to_dict(record)

    def list_records(self):
        records = (
            BillingRecord.objects
            .prefetch_related("line_items")
            .order_by("-created_at")
        )

        return [
            self._to_dict(record)
            for record in records
        ]

    def update_status(self, record_id, status):
        updated = BillingRecord.objects.filter(
            record_id=record_id
        ).update(status=status)

        if updated == 0:
            raise ValueError("Billing record not found.")

    @transaction.atomic
    def apply_record_field_correction(
        self,
        *,
        record_id,
        field_name,
        old_value,
        new_value,
        reviewed_by=None,
    ):
        model_field = self.RECORD_FIELD_MAP.get(field_name)

        if model_field is None:
            raise ValueError(
                f"Field '{field_name}' is not editable."
            )

        try:
            record = BillingRecord.objects.select_for_update().get(
                record_id=record_id
            )
        except (BillingRecord.DoesNotExist, ValueError):
            raise ValueError("Billing record not found.")

        value = new_value

        if field_name == "transactionDate":
            if isinstance(new_value, str):
                try:
                    value = date.fromisoformat(new_value)
                except ValueError:
                    raise ValueError(
                        "transactionDate must use YYYY-MM-DD format."
                    )

        setattr(record, model_field, value)
        record.status = "RECOMMENDATION_PENDING"

        record.save(
            update_fields=[
                model_field,
                "status",
                "updated_at",
            ]
        )

    @transaction.atomic
    def apply_line_item_correction(
        self,
        *,
        record_id,
        line_item_id,
        field_name,
        old_value,
        new_value,
        reviewed_by=None,
    ):
        model_field = self.LINE_ITEM_FIELD_MAP.get(field_name)

        if model_field is None:
            raise ValueError(
                f"Line-item field '{field_name}' is not editable."
            )

        try:
            line_item = (
                LineItem.objects
                .select_for_update()
                .select_related("billing_record")
                .get(
                    line_item_id=line_item_id,
                    billing_record_id=record_id,
                )
            )
        except (LineItem.DoesNotExist, ValueError):
            raise ValueError("Line item not found.")

        value = new_value

        if field_name in {"grossGallons", "netGallons"}:
            try:
                value = Decimal(str(new_value))
            except Exception:
                raise ValueError(
                    f"{field_name} must be numeric."
                )

        setattr(line_item, model_field, value)
        line_item.save(
            update_fields=[model_field]
        )

        BillingRecord.objects.filter(
            record_id=record_id
        ).update(
            status="RECOMMENDATION_PENDING"
        )

    def _to_dict(self, record):
        transaction_date = (
            record.transaction_date.isoformat()
            if record.transaction_date
            else None
        )

        fields = {
            "bolNumber": {
                "normalizedValue": record.bol_number,
            },
            "contractLifting": {
                "normalizedValue": record.contract_lifting,
            },
            "origin": {
                "normalizedValue": record.origin,
            },
            "supplier": {
                "normalizedValue": record.supplier,
            },
            "carrier": {
                "normalizedValue": record.carrier,
            },
            "transactionDate": {
                "normalizedValue": transaction_date,
            },
            "destination": {
                "normalizedValue": record.destination,
            },
        }

        line_items = []

        for item in record.line_items.all():
            line_items.append(
                {
                    "lineItemId": str(item.line_item_id),
                    "lineNumber": item.line_number,
                    "product": {
                        "normalizedValue": item.product,
                    },
                    "e3StockId": {
                        "normalizedValue": item.e3_stock_id,
                    },
                    "standardName": {
                        "normalizedValue": item.standard_name,
                    },
                    "netGallons": {
                        "normalizedValue": (
                            float(item.net_gallons)
                            if item.net_gallons is not None
                            else None
                        ),
                    },
                    "grossGallons": {
                        "normalizedValue": (
                            float(item.gross_gallons)
                            if item.gross_gallons is not None
                            else None
                        ),
                    },
                }
            )

        return {
            "recordId": str(record.record_id),
            "status": record.status,
            "fields": fields,
            "lineItems": line_items,
            "createdAt": record.created_at.isoformat(),
            "updatedAt": record.updated_at.isoformat(),
        }
