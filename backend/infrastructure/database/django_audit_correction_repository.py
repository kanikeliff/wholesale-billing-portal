from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import AuditEvent


class DjangoAuditCorrectionRepository:

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
    def apply_record_field_correction(
        self,
        *,
        record_id,
        field_name,
        old_value,
        new_value,
        reviewed_by=None,
        resulting_status="RECOMMENDATION_PENDING",
    ):
        model_field = self.RECORD_FIELD_MAP.get(field_name)

        if model_field is None:
            raise ValueError(
                f"Field '{field_name}' is not editable."
            )

        try:
            record = (
                BillingRecord.objects
                .select_for_update()
                .get(record_id=record_id)
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
        record.status = resulting_status

        record.save(
            update_fields=[
                model_field,
                "status",
                "updated_at",
            ]
        )

        return AuditEvent.objects.create(
            billing_record=record,
            event_type="FIELD_CORRECTION",
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            actor_id=reviewed_by,
            metadata={
                "scope": "record",
            },
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
        resulting_status="RECOMMENDATION_PENDING",
    ):
        model_field = self.LINE_ITEM_FIELD_MAP.get(field_name)

        if model_field is None:
            raise ValueError(
                f"Line-item field '{field_name}' is not editable."
            )

        try:
            record = (
                BillingRecord.objects
                .select_for_update()
                .get(record_id=record_id)
            )
        except (BillingRecord.DoesNotExist, ValueError):
            raise ValueError("Billing record not found.")

        try:
            line_item = (
                LineItem.objects
                .select_for_update()
                .get(
                    line_item_id=line_item_id,
                    billing_record=record,
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

        record.status = resulting_status
        record.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return AuditEvent.objects.create(
            billing_record=record,
            line_item=line_item,
            event_type="FIELD_CORRECTION",
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            actor_id=reviewed_by,
            metadata={
                "scope": "line_item",
            },
        )
