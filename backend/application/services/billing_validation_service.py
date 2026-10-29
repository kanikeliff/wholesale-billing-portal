class BillingValidationService:

    def __init__(self, billing_record_provider, validator):
        self.billing_record_provider = billing_record_provider
        self.validator = validator

    def validate_record(self, record_id):
        record = self.billing_record_provider.get_by_id(record_id)

        if record is None:
            raise ValueError("Billing record not found.")

        return self.validator.validate(record)
