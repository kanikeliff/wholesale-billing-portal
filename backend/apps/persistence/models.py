import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class Document(models.Model):
    document_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    billing_record = models.ForeignKey(
        "billing.BillingRecord",
        on_delete=models.CASCADE,
        related_name="persistence_documents",
    )

    original_filename = models.CharField(
        max_length=255,
    )

    storage_path = models.TextField(
        null=True,
        blank=True,
    )

    mime_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
    )

    checksum_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return f"{self.document_id} - {self.original_filename}"


class ExtractedField(models.Model):
    class Quality(models.TextChoices):
        OK = "OK", "OK"
        LOW_CONFIDENCE = "LOW_CONFIDENCE", "Low Confidence"
        MISSING = "MISSING", "Missing"
        UNREADABLE = "UNREADABLE", "Unreadable"
        INVALID = "INVALID", "Invalid"

    extracted_field_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    billing_record = models.ForeignKey(
        "billing.BillingRecord",
        on_delete=models.CASCADE,
        related_name="extracted_fields",
    )

    line_item = models.ForeignKey(
        "billing.LineItem",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="extracted_fields",
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="extracted_fields",
    )

    field_name = models.CharField(
        max_length=100,
    )

    raw_value = models.TextField(
        null=True,
        blank=True,
    )

    normalized_value = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
    )

    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
    )

    quality = models.CharField(
        max_length=30,
        choices=Quality.choices,
        default=Quality.OK,
    )

    source_page = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    bounding_box = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
    )

    metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["billing_record", "field_name"],
                name="p_ext_rec_field_idx",
            ),
            models.Index(
                fields=["line_item", "field_name"],
                name="p_ext_line_field_idx",
            ),
            models.Index(
                fields=["quality"],
                name="p_ext_quality_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(confidence__isnull=True)
                    | (
                        models.Q(confidence__gte=0)
                        & models.Q(confidence__lte=1)
                    )
                ),
                name="p_ext_conf_0_1",
            )
        ]


class Recommendation(models.Model):
    recommendation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    billing_record = models.ForeignKey(
        "billing.BillingRecord",
        on_delete=models.CASCADE,
        related_name="persisted_recommendations",
    )

    revision = models.PositiveIntegerField()

    recommendation = models.CharField(
        max_length=100,
    )

    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
    )

    model_version = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    matched_terminal_log_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    rationale = models.TextField(
        null=True,
        blank=True,
    )

    mapped_entities = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
    )

    exception_indicators = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        blank=True,
    )

    raw_response = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
    )

    is_current = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["billing_record_id", "revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["billing_record", "revision"],
                name="p_rec_unique_revision",
            ),
            models.UniqueConstraint(
                fields=["billing_record"],
                condition=models.Q(is_current=True),
                name="p_rec_one_current",
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=1),
                name="p_rec_revision_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(confidence__isnull=True)
                    | (
                        models.Q(confidence__gte=0)
                        & models.Q(confidence__lte=1)
                    )
                ),
                name="p_rec_conf_0_1",
            ),
        ]


class AuditEvent(models.Model):
    audit_event_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    billing_record = models.ForeignKey(
        "billing.BillingRecord",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )

    line_item = models.ForeignKey(
        "billing.LineItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    event_type = models.CharField(
        max_length=100,
        default="FIELD_CORRECTION",
    )

    field_name = models.CharField(
        max_length=100,
    )

    old_value = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
    )

    new_value = models.JSONField(
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
    )

    actor_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["billing_record", "created_at"],
                name="p_audit_rec_time_idx",
            ),
        ]


class HumanDecision(models.Model):
    class FeedbackStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    human_decision_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    billing_record = models.ForeignKey(
        "billing.BillingRecord",
        on_delete=models.CASCADE,
        related_name="human_decisions",
    )

    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="human_decisions",
    )

    decision = models.CharField(
        max_length=30,
    )

    previous_status = models.CharField(
        max_length=50,
    )

    resulting_status = models.CharField(
        max_length=50,
    )

    decided_by = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    reason = models.TextField(
        null=True,
        blank=True,
    )

    feedback_status = models.CharField(
        max_length=20,
        choices=FeedbackStatus.choices,
        default=FeedbackStatus.PENDING,
    )

    feedback_metadata = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=dict,
        blank=True,
    )

    feedback_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["billing_record", "created_at"],
                name="p_dec_rec_time_idx",
            ),
            models.Index(
                fields=["feedback_status"],
                name="p_dec_feedback_idx",
            ),
        ]
