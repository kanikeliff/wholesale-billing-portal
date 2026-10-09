from abc import ABC, abstractmethod


class BillingRecordRepository(ABC):

    @abstractmethod
    def create_billing_record(self, data):
        """
        Create a BillingRecord and its related LineItems.

        Args:
            data: Billing record data including optional line_items.

        Returns:
            The created billing record.
        """
        raise NotImplementedError

    @abstractmethod
    def get_billing_record(self, record_id):
        """
        Retrieve a BillingRecord by its stable record_id.

        Args:
            record_id: UUID of the billing record.

        Returns:
            The billing record with its related line items.
        """
        raise NotImplementedError
