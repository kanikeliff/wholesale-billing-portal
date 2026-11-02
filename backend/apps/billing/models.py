import uuid

from django.db import models


class BillingRecord(models.Model):
    record_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    bol_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    contract_lifting = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    origin = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    supplier = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    carrier = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    transaction_date = models.DateField(
        null=True,
        blank=True,
    )

    destination = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=50,
        default="UPLOADED",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["bol_number"],
                name="b_rec_bol_idx",
            ),
            models.Index(
                fields=["status", "-created_at"],
                name="b_rec_status_time_idx",
            ),
            models.Index(
                fields=["transaction_date"],
                name="b_rec_tx_date_idx",
            ),
            models.Index(
                fields=["-created_at"],
                name="b_rec_created_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "UPLOADED",
                        "OCR_PROCESSING",
                        "OCR_COMPLETE",
                        "NEEDS_REVIEW",
                        "RECOMMENDATION_PENDING",
                        "RECOMMENDATION_READY",
                        "APPROVED",
                        "REJECTED",
                        "EXCEPTION",
                    ]
                ),
                name="b_rec_valid_status",
            ),
        ]

    def __str__(self):
        return f"{self.record_id} - {self.bol_number or 'No BOL'}"


class LineItem(models.Model):
    line_item_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    billing_record = models.ForeignKey(
        BillingRecord,
        on_delete=models.CASCADE,
        related_name="line_items",
    )

    line_number = models.PositiveIntegerField()

    product = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    e3_stock_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    standard_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    net_gallons = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    gross_gallons = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["billing_record", "line_number"],
                name="unique_line_number_per_record",
            )
        ]

    def __str__(self):
        return f"{self.billing_record_id} - Line {self.line_number}"
