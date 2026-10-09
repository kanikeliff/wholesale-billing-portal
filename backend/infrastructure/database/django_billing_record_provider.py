from apps.billing.models import BillingRecord
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)


class DjangoBillingRecordProvider:

    def __init__(self):
        self.repository = DjangoBillingRecordRepository()

    def get_by_id(self, record_id):
        try:
            record = self.repository.get_billing_record(record_id)
        except (BillingRecord.DoesNotExist, ValueError):
            return None

        return {
            "recordId": str(record.record_id),
            "status": record.status,
            "bolNumber": record.bol_number,
            "contractLifting": record.contract_lifting,
            "origin": record.origin,
            "supplier": record.supplier,
            "carrier": record.carrier,
            "transactionDate": (
                record.transaction_date.isoformat()
                if record.transaction_date
                else None
            ),
            "destination": record.destination,
            "lineItems": [
                {
                    "lineItemId": str(item.line_item_id),
                    "lineNumber": item.line_number,
                    "product": item.product,
                    "e3StockId": item.e3_stock_id,
                    "standardName": item.standard_name,
                    "netGallons": (
                        str(item.net_gallons)
                        if item.net_gallons is not None
                        else None
                    ),
                    "grossGallons": (
                        str(item.gross_gallons)
                        if item.gross_gallons is not None
                        else None
                    ),
                }
                for item in record.line_items.all()
            ],
        }
