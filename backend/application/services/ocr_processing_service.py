class OCRProcessingService:

    def __init__(
        self,
        *,
        adapter,
        billing_record_repository,
    ):
        self.adapter = adapter
        self.billing_record_repository = billing_record_repository

    def persist_extraction(self, extraction):
        canonical = self.adapter.adapt(extraction)

        fields = canonical["fields"]
        line_items = canonical["lineItems"]

        def value(field_name):
            return fields[field_name]["normalizedValue"]

        record_data = {
            "bol_number": value("bolNumber"),
            "contract_lifting": value("contractLifting"),
            "origin": value("origin"),
            "supplier": value("supplier"),
            "carrier": value("carrier"),
            "transaction_date": value("transactionDate"),
            "destination": value("destination"),
            "status": self._determine_status(canonical),
            "line_items": [
                {
                    "line_number": item["lineNumber"],
                    "product": item["product"]["normalizedValue"],
                    "net_gallons": item["netGallons"]["normalizedValue"],
                    "gross_gallons": item["grossGallons"]["normalizedValue"],
                    "e3_stock_id": item["e3StockId"]["normalizedValue"],
                    "standard_name": None,
                }
                for item in line_items
            ],
        }

        record = self.billing_record_repository.create_billing_record(
            record_data
        )

        return {
            "recordId": str(record.record_id),
            "status": record.status,
            "canonical": canonical,
        }


    def rollback_persisted_record(self, record_id):
        return self.billing_record_repository.delete_billing_record(
            record_id
        )

    def _determine_status(self, canonical):
        required_fields = (
            "bolNumber",
            "origin",
            "transactionDate",
        )

        fields = canonical["fields"]

        for field_name in required_fields:
            if fields[field_name]["unresolved"]:
                return "NEEDS_REVIEW"

        if not canonical["lineItems"]:
            return "NEEDS_REVIEW"

        for item in canonical["lineItems"]:
            if item["product"]["unresolved"]:
                return "NEEDS_REVIEW"

            if item["grossGallons"]["unresolved"]:
                return "NEEDS_REVIEW"

            if item["netGallons"]["unresolved"]:
                return "NEEDS_REVIEW"

        return "OCR_COMPLETE"
