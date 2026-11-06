from datetime import date
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import CharField, OuterRef, Prefetch, Subquery
from django.db.models.functions import Cast, JSONObject

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

    @transaction.atomic
    def update_from_ocr(self, record_id, data):
        record = (
            BillingRecord.objects
            .select_for_update()
            .get(record_id=record_id)
        )

        if record.status != "OCR_PROCESSING":
            raise ValueError(
                f"OCR update is not allowed in status {record.status}."
            )

        record_data = data.copy()
        line_items_data = record_data.pop("line_items", [])

        for field_name, value in record_data.items():
            if field_name not in {
                "bol_number", "contract_lifting", "origin",
                "supplier", "carrier", "transaction_date",
                "destination", "status",
            }:
                raise ValueError(f"Unsupported OCR field: {field_name}")

            setattr(record, field_name, value)

        record.save()

        for item_data in line_items_data:
            LineItem.objects.update_or_create(
                billing_record=record,
                line_number=item_data["line_number"],
                defaults={
                    key: value
                    for key, value in item_data.items()
                    if key != "line_number"
                },
            )

        return record

    def _read_queryset(self):
        # Keep the API shape while loading evidence for the entire batch once.
        # The latest OCR summary excludes its potentially large raw_result JSON.
        from apps.persistence.models import AuditEvent, ExtractedField, HumanDecision, OCRJob
        latest_job = (
            OCRJob.objects.filter(document__billing_record_id=OuterRef("pk"))
            .order_by("-created_at", "-pk")
            .annotate(summary=JSONObject(
                jobId=Cast("job_id", output_field=CharField()), status="status",
                errorCode="error_code", errorMessage="error_message",
            )).values("summary")[:1]
        )
        return BillingRecord.objects.annotate(
            _read_ocr_job=Subquery(latest_job),
        ).prefetch_related(
            "line_items",
            Prefetch("extracted_fields", queryset=ExtractedField.objects.only(
                "billing_record_id", "line_item_id", "field_name", "raw_value", "confidence", "quality",
            ).order_by("created_at", "pk"), to_attr="_read_extracted"),
            Prefetch("audit_events", queryset=AuditEvent.objects.filter(
                event_type="FIELD_CORRECTION",
            ).only("billing_record_id", "field_name", "line_item_id"), to_attr="_read_corrections"),
            Prefetch("human_decisions", queryset=HumanDecision.objects.only(
                "billing_record_id", "feedback_status", "feedback_metadata", "feedback_sent_at",
            ).order_by("-created_at", "-pk")[:1], to_attr="_read_decisions"),
        )

    def get_billing_record(self, record_id):
        return self._read_queryset().get(record_id=record_id)

    def get_by_id(self, record_id):
        try:
            record = self.get_billing_record(record_id)
        except (BillingRecord.DoesNotExist, ValueError, ValidationError):
            return None
        return self._to_dict(record)

    def list_records(self):
        return [self._to_dict(record) for record in self._read_queryset().order_by("-created_at", "-pk")]

    def update_status(self, record_id, status):
        updated = BillingRecord.objects.filter(
            record_id=record_id
        ).update(status=status)

        if updated == 0:
            raise ValueError("Billing record not found.")


    @transaction.atomic
    def delete_billing_record(self, record_id):
        try:
            record = (
                BillingRecord.objects
                .select_for_update()
                .get(record_id=record_id)
            )
        except (BillingRecord.DoesNotExist, ValueError, ValidationError):
            return False

        record.delete()
        return True

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
        except (BillingRecord.DoesNotExist, ValueError, ValidationError):
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

        # Attach persisted OCR metadata without changing current values.
        line_items_by_id = {
            item["lineItemId"]: item for item in line_items
        }

        extracted_fields = getattr(record, "_read_extracted", None)
        if extracted_fields is None:
            extracted_fields = record.extracted_fields.only(
                "billing_record_id", "line_item_id", "field_name", "raw_value", "confidence", "quality",
            ).order_by("created_at", "pk")

        for extracted in extracted_fields:
            if extracted.line_item_id is None:
                target = fields.get(extracted.field_name)
            else:
                line = line_items_by_id.get(
                    str(extracted.line_item_id)
                )
                target = (
                    line.get(extracted.field_name)
                    if line is not None
                    else None
                )

            if target is None:
                continue

            target["rawValue"] = extracted.raw_value
            target["confidence"] = (
                float(extracted.confidence)
                if extracted.confidence is not None
                else None
            )
            target["quality"] = extracted.quality

        # Corrections resolve current review warnings without rewriting OCR
        # evidence. Scope by line item so correcting one line cannot hide another.
        corrections = getattr(record, "_read_corrections", None)
        if corrections is None:
            corrections = record.audit_events.filter(event_type="FIELD_CORRECTION").only(
                "billing_record_id", "field_name", "line_item_id",
            )
        for correction in corrections:
            if correction.line_item_id is None:
                target = fields.get(correction.field_name)
            else:
                line = line_items_by_id.get(str(correction.line_item_id))
                target = line.get(correction.field_name) if line else None
            if target is not None:
                target["isCorrected"] = True

        if hasattr(record, "_read_ocr_job"):
            ocr_job = record._read_ocr_job
            if ocr_job:
                # SQLite casts UUIDs without hyphens; keep the public UUID format.
                ocr_job["jobId"] = str(UUID(ocr_job["jobId"]))
        else:
            from apps.persistence.models import OCRJob
            latest_job = OCRJob.objects.filter(document__billing_record=record).only(
                "status", "error_code", "error_message",
            ).order_by("-created_at", "-pk").first()
            ocr_job = ({
                "jobId": str(latest_job.pk), "status": latest_job.status,
                "errorCode": latest_job.error_code, "errorMessage": latest_job.error_message,
            } if latest_job else None)

        decisions = getattr(record, "_read_decisions", None)
        latest_decision = (decisions[0] if decisions else None) if decisions is not None else (
            record.human_decisions.order_by("-created_at", "-pk").first()
        )
        feedback = None
        if latest_decision:
            metadata = latest_decision.feedback_metadata or {}
            feedback = {
                "humanDecisionId": str(latest_decision.pk),
                "status": latest_decision.feedback_status,
                "attempts": metadata.get("attempts", 0),
                "retryable": metadata.get("retryable", False),
                "queued": "payload" in metadata,
                "sentAt": latest_decision.feedback_sent_at.isoformat() if latest_decision.feedback_sent_at else None,
                "errorCode": metadata.get("errorCode"),
            }

        return {
            "recordId": str(record.record_id),
            "ocrJob": ocr_job,
            "feedback": feedback,
            "status": record.status,
            "fields": fields,
            "lineItems": line_items,
            "createdAt": record.created_at.isoformat(),
            "updatedAt": record.updated_at.isoformat(),
        }
