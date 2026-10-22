from datetime import date
from decimal import Decimal, InvalidOperation


class BillingRecordValidator:
    REVIEW_QUALITIES = {
        "LOW_CONFIDENCE",
        "MISSING",
        "UNREADABLE",
    }

    def validate(self, record):
        blocking_issues = []
        review_flags = []

        record_id = record.get("recordId")

        fields = record.get("fields")

        if not isinstance(fields, dict):
            blocking_issues.append(
                {
                    "code": "MALFORMED_FIELDS",
                    "severity": "ERROR",
                    "message": "Billing record fields must be an object.",
                }
            )
            fields = {}

        for field_name, field_data in fields.items():
            self._validate_field_quality(
                field_name=field_name,
                field_data=field_data,
                review_flags=review_flags,
            )

        self._validate_transaction_date(
            fields=fields,
            blocking_issues=blocking_issues,
        )

        line_items = record.get("lineItems")

        if not isinstance(line_items, list) or len(line_items) == 0:
            blocking_issues.append(
                {
                    "code": "INVALID_LINE_ITEMS",
                    "severity": "ERROR",
                    "message": "Billing record must contain at least one line item.",
                }
            )
        else:
            for line_item in line_items:
                self._validate_line_item(
                    line_item=line_item,
                    blocking_issues=blocking_issues,
                    review_flags=review_flags,
                )

        if blocking_issues:
            next_status = "EXCEPTION"
        elif review_flags:
            next_status = "NEEDS_REVIEW"
        else:
            next_status = "RECOMMENDATION_PENDING"

        return {
            "recordId": record_id,
            "valid": len(blocking_issues) == 0,
            "blockingIssues": blocking_issues,
            "reviewFlags": review_flags,
            "nextStatus": next_status,
        }

    def _validate_field_quality(
        self,
        field_name,
        field_data,
        review_flags,
        line_item_id=None,
    ):
        if not isinstance(field_data, dict):
            return

        quality = field_data.get("quality")

        if quality not in self.REVIEW_QUALITIES:
            return

        if quality == "LOW_CONFIDENCE":
            code = "LOW_CONFIDENCE"
            message = f"{field_name} has low OCR confidence."

        elif quality == "MISSING":
            code = "MISSING_FIELD"
            message = f"{field_name} is missing."

        else:
            code = "UNREADABLE_FIELD"
            message = f"{field_name} could not be read reliably."

        flag = {
            "code": code,
            "severity": "WARNING",
            "field": field_name,
            "message": message,
        }

        if line_item_id is not None:
            flag["lineItemId"] = line_item_id

        review_flags.append(flag)

    def _validate_transaction_date(
        self,
        fields,
        blocking_issues,
    ):
        transaction_date = fields.get("transactionDate")

        if not isinstance(transaction_date, dict):
            return

        value = transaction_date.get("normalizedValue")

        if value in (None, ""):
            return

        if isinstance(value, date):
            return

        try:
            date.fromisoformat(str(value))
        except (TypeError, ValueError):
            blocking_issues.append(
                {
                    "code": "INVALID_DATE",
                    "severity": "ERROR",
                    "field": "transactionDate",
                    "message": (
                        "transactionDate must use ISO format YYYY-MM-DD."
                    ),
                }
            )

    def _validate_line_item(
        self,
        line_item,
        blocking_issues,
        review_flags,
    ):
        if not isinstance(line_item, dict):
            blocking_issues.append(
                {
                    "code": "MALFORMED_LINE_ITEM",
                    "severity": "ERROR",
                    "message": "Each line item must be an object.",
                }
            )
            return

        line_item_id = line_item.get("lineItemId")

        for field_name in (
            "product",
            "grossGallons",
            "netGallons",
            "e3StockId",
        ):
            self._validate_field_quality(
                field_name=field_name,
                field_data=line_item.get(field_name),
                review_flags=review_flags,
                line_item_id=line_item_id,
            )

        self._validate_gallons(
            field_name="grossGallons",
            field_data=line_item.get("grossGallons"),
            line_item_id=line_item_id,
            blocking_issues=blocking_issues,
        )

        self._validate_gallons(
            field_name="netGallons",
            field_data=line_item.get("netGallons"),
            line_item_id=line_item_id,
            blocking_issues=blocking_issues,
        )

    def _validate_gallons(
        self,
        field_name,
        field_data,
        line_item_id,
        blocking_issues,
    ):
        if not isinstance(field_data, dict):
            blocking_issues.append(
                {
                    "code": "INVALID_FIELD_STRUCTURE",
                    "severity": "ERROR",
                    "field": field_name,
                    "lineItemId": line_item_id,
                    "message": f"{field_name} must be a field object.",
                }
            )
            return

        value = field_data.get("normalizedValue")

        if value in (None, ""):
            return

        try:
            numeric_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            blocking_issues.append(
                {
                    "code": "INVALID_NUMERIC_VALUE",
                    "severity": "ERROR",
                    "field": field_name,
                    "lineItemId": line_item_id,
                    "message": f"{field_name} must be numeric.",
                }
            )
            return

        if numeric_value < 0:
            blocking_issues.append(
                {
                    "code": "NEGATIVE_GALLONS",
                    "severity": "ERROR",
                    "field": field_name,
                    "lineItemId": line_item_id,
                    "message": f"{field_name} cannot be negative.",
                }
            )
