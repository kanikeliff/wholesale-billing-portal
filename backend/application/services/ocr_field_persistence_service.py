from django.db import transaction

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import Document, ExtractedField, AuditEvent


class OCRFieldPersistenceService:

    @transaction.atomic
    def persist(self, *, record_id, document_id, canonical):
        record = BillingRecord.objects.get(record_id=record_id)

        document = Document.objects.get(
            document_id=document_id,
            billing_record=record,
        )

        line_items = {
            item.line_number: item
            for item in LineItem.objects.filter(billing_record=record)
        }

        extracted_fields = []

        def add_field(field_name, field, line_item=None):
            raw = field.get("rawValue")

            extracted_fields.append(
                ExtractedField(
                    billing_record=record,
                    document=document,
                    line_item=line_item,
                    field_name=field_name,
                    raw_value=str(raw) if raw is not None else None,
                    normalized_value=field.get("normalizedValue"),
                    confidence=field.get("confidence"),
                    quality=(
                        ExtractedField.Quality.MISSING
                        if field.get("unresolved")
                        else ExtractedField.Quality.OK
                    ),
                    metadata={
                        "source": "saved_ocr_extraction"
                    },
                )
            )

        for name, field in canonical["fields"].items():
            add_field(name, field)

        for item in canonical["lineItems"]:
            line_item = line_items[item["lineNumber"]]

            for name in (
                "product",
                "netGallons",
                "grossGallons",
                "e3StockId",
            ):
                add_field(name, item[name], line_item)

        ExtractedField.objects.bulk_create(extracted_fields)

        AuditEvent.objects.create(
            billing_record=record,
            event_type="OCR_COMPLETED",
            actor_id="system",
            metadata={
                "documentId": str(document.document_id),
                "extractedFieldCount": len(extracted_fields),
                "source": "saved_ocr_extraction",
            },
        )

        return len(extracted_fields)
