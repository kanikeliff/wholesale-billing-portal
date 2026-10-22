from core.enums.record_status import RecordStatus


class CorrectionService:

    EDITABLE_RECORD_FIELDS = {
        "bolNumber",
        "contractLifting",
        "origin",
        "supplier",
        "carrier",
        "transactionDate",
        "destination",
    }

    EDITABLE_LINE_ITEM_FIELDS = {
        "product",
        "grossGallons",
        "netGallons",
        "e3StockId",
    }

    CORRECTABLE_STATUSES = {
        RecordStatus.NEEDS_REVIEW.value,
        RecordStatus.RECOMMENDATION_READY.value,
    }

    def __init__(
        self,
        billing_record_provider,
        correction_repository=None,
        billing_record_repository=None,
        workflow_service=None,
    ):
        self.billing_record_provider = billing_record_provider
        self.correction_repository = correction_repository
        self.billing_record_repository = billing_record_repository
        self.workflow_service = workflow_service

    def correct_record_field(
        self,
        record_id,
        field_name,
        new_value,
        *,
        reviewed_by=None,
    ):
        record = self._get_record(record_id)

        self._validate_correctable_status(record)
        self._validate_record_field(field_name)
        self._validate_value(field_name, new_value)

        old_value = self._get_record_field_value(
            record,
            field_name,
        )

        if self.correction_repository is not None:
            self.correction_repository.apply_record_field_correction(
                record_id=record_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                reviewed_by=reviewed_by,
            )

        self._mark_recommendation_pending(
            record_id,
            record["status"],
        )

        return {
            "recordId": record_id,
            "field": field_name,
            "oldValue": old_value,
            "newValue": new_value,
            "status": RecordStatus.RECOMMENDATION_PENDING.value,
            "requiresReevaluation": True,
        }

    def correct_line_item_field(
        self,
        record_id,
        line_item_id,
        field_name,
        new_value,
        *,
        reviewed_by=None,
    ):
        record = self._get_record(record_id)

        self._validate_correctable_status(record)
        self._validate_line_item_field(field_name)
        self._validate_value(field_name, new_value)

        line_item = self._find_line_item(
            record,
            line_item_id,
        )

        old_value = self._get_line_item_field_value(
            line_item,
            field_name,
        )

        if self.correction_repository is not None:
            self.correction_repository.apply_line_item_correction(
                record_id=record_id,
                line_item_id=line_item_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                reviewed_by=reviewed_by,
            )

        self._mark_recommendation_pending(
            record_id,
            record["status"],
        )

        return {
            "recordId": record_id,
            "lineItemId": line_item_id,
            "field": field_name,
            "oldValue": old_value,
            "newValue": new_value,
            "status": RecordStatus.RECOMMENDATION_PENDING.value,
            "requiresReevaluation": True,
        }

    def _get_record(self, record_id):
        record = self.billing_record_provider.get_by_id(record_id)

        if record is None:
            raise ValueError("Billing record not found.")

        return record

    def _validate_correctable_status(self, record):
        current_status = record.get("status")

        if current_status not in self.CORRECTABLE_STATUSES:
            raise ValueError(
                f"Billing record cannot be corrected while in "
                f"{current_status} status."
            )

    def _validate_record_field(self, field_name):
        if field_name not in self.EDITABLE_RECORD_FIELDS:
            raise ValueError(
                f"Field '{field_name}' is not editable."
            )

    def _validate_line_item_field(self, field_name):
        if field_name not in self.EDITABLE_LINE_ITEM_FIELDS:
            raise ValueError(
                f"Line-item field '{field_name}' is not editable."
            )

    def _validate_value(self, field_name, value):
        if value is None:
            raise ValueError("Corrected value cannot be null.")

        if isinstance(value, str) and not value.strip():
            raise ValueError("Corrected value cannot be empty.")

        if field_name in {"grossGallons", "netGallons"}:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{field_name} must be numeric."
                )

            if numeric_value < 0:
                raise ValueError(
                    f"{field_name} cannot be negative."
                )

    def _get_record_field_value(
        self,
        record,
        field_name,
    ):
        field = record.get("fields", {}).get(field_name)

        if field is None:
            return None

        if isinstance(field, dict):
            return field.get("normalizedValue")

        return field

    def _find_line_item(
        self,
        record,
        line_item_id,
    ):
        for line_item in record.get("lineItems", []):
            if str(line_item.get("lineItemId")) == str(line_item_id):
                return line_item

        raise ValueError("Line item not found.")

    def _get_line_item_field_value(
        self,
        line_item,
        field_name,
    ):
        field = line_item.get(field_name)

        if field is None:
            return None

        if isinstance(field, dict):
            return field.get("normalizedValue")

        return field

    def _mark_recommendation_pending(
        self,
        record_id,
        current_status,
    ):
        if self.workflow_service is not None:
            self.workflow_service.validate_transition(
                current_status,
                RecordStatus.RECOMMENDATION_PENDING.value,
            )

        if self.billing_record_repository is not None:
            self.billing_record_repository.update_status(
                record_id,
                RecordStatus.RECOMMENDATION_PENDING.value,
            )
