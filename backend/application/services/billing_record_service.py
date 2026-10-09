class BillingRecordService:

    def __init__(self, billing_record_provider):
        self.billing_record_provider = billing_record_provider

    def get_record(self, record_id):
        record = self.billing_record_provider.get_by_id(record_id)

        if record is None:
            raise ValueError("Billing record not found.")

        return record
