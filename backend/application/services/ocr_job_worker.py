
from datetime import timedelta

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.billing.models import BillingRecord
from apps.persistence.models import OCRJob

from application.services.ocr_processing_service import (
    OCRProcessingService,
)
from application.services.ocr_field_persistence_service import (
    OCRFieldPersistenceService,
)
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter


class OCRJobWorker:

    def __init__(self, extractor, *, provider=None):
        self.extractor = extractor
        self.provider = provider

        self.processing_service = OCRProcessingService(
            adapter=BolLabAdapter(),
            billing_record_repository=DjangoBillingRecordRepository(),
        )

        self.field_persistence_service = OCRFieldPersistenceService()

    def recover_stale_jobs(self, timeout_minutes=10):
        cutoff = timezone.now() - timedelta(
            minutes=timeout_minutes
        )

        recovered = 0

        with transaction.atomic():
            stale_jobs = (
                OCRJob.objects
                .select_for_update(skip_locked=True)
                .filter(
                    status=OCRJob.Status.PROCESSING,
                    started_at__lt=cutoff,
                )
            )

            for job in stale_jobs:
                job.error_code = "WORKER_TIMEOUT"
                job.error_message = (
                    "OCR worker did not finish within "
                    "the allowed time."
                )

                if job.attempt_count >= job.max_attempts:
                    job.status = OCRJob.Status.FAILED
                    job.next_retry_at = None

                    record = job.document.billing_record

                    if record.status == "OCR_PROCESSING":
                        record.status = "EXCEPTION"
                        record.save(
                            update_fields=[
                                "status",
                                "updated_at",
                            ]
                        )

                else:
                    job.status = OCRJob.Status.RETRY_PENDING
                    job.next_retry_at = timezone.now()

                job.save()
                recovered += 1

        return recovered

    def claim_next_job(self, job_id=None):
        with transaction.atomic():
            now = timezone.now()

            ready_jobs = (
                Q(status=OCRJob.Status.PENDING)
                | Q(
                    status=OCRJob.Status.RETRY_PENDING,
                    next_retry_at__lte=now,
                )
            )

            queryset = (
                OCRJob.objects
                .select_for_update(skip_locked=True)
                .filter(ready_jobs)
                .filter(attempt_count__lt=F("max_attempts"))
            )

            if job_id is not None:
                queryset = queryset.filter(job_id=job_id)

            if self.provider == "live":
                queryset = queryset.filter(raw_result__requestedProvider="live")
            elif self.provider == "sample":
                queryset = queryset.filter(
                    Q(raw_result__requestedProvider="sample") | ~Q(raw_result__has_key="requestedProvider")
                )

            job = queryset.order_by("created_at").first()

            if job is None:
                return None

            record = job.document.billing_record

            if record.status not in (
                "UPLOADED",
                "OCR_PROCESSING",
            ):
                raise ValueError(
                    "OCR job cannot start from status "
                    f"{record.status}."
                )

            job.status = OCRJob.Status.PROCESSING
            job.started_at = now
            job.attempt_count += 1
            job.next_retry_at = None
            job.save()

            record.status = "OCR_PROCESSING"
            record.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return job.job_id

    def process_next_job(self, job_id=None):
        job_id = self.claim_next_job(job_id=job_id)

        if job_id is None:
            return None

        job = (
            OCRJob.objects
            .select_related("document__billing_record")
            .get(job_id=job_id)
        )

        # Identify the attempt that currently owns this job.
        attempt_token = job.attempt_count

        try:
            # Read the original uploaded document.
            with default_storage.open(
                job.document.storage_path,
                "rb",
            ) as stored_file:
                file_bytes = stored_file.read()

            # Execute OCR extraction.
            result = self.extractor(
                document_id=str(job.document_id),
                file_bytes=file_bytes,
                filename=job.document.original_filename,
            )

            # Support full OCR results and simple test results.
            extraction = result.get(
                "extraction",
                result,
            )

            # Extract human-review indicators.
            review_flags = (
                result.get("ocrReviewFlags") or []
            )

            verification = (
                result.get("verification") or {}
            )

            requires_review = (
                bool(review_flags)
                or verification.get("reviewRequired") is True
            )

            # Persist the result only if this attempt still owns it.
            with transaction.atomic():
                current_job = (
                    OCRJob.objects
                    .select_for_update()
                    .get(job_id=job_id)
                )

                if (
                    current_job.status != OCRJob.Status.PROCESSING
                    or current_job.attempt_count != attempt_token
                ):
                    return None

                # Update the existing BillingRecord and LineItems.
                persisted = (
                    self.processing_service
                    .persist_extraction_for_record(
                        current_job.document.billing_record_id,
                        extraction,
                        review_flags=review_flags,
                        confidence_source=result if isinstance(result.get("fieldConfidence"), dict) else None,
                    )
                )

                # Save extracted fields and an OCR audit event.
                                
                self.field_persistence_service.persist(
                    record_id=persisted["recordId"],
                    document_id=current_job.document_id,
                    canonical=persisted["canonical"],
                    source=("ocr_live" if result.get("metadata", {}).get("liveOCR") else "ocr_pipeline"),
                )


                # Require human review if verification flags exist.
                if (
                    requires_review
                    and persisted["status"] == "OCR_COMPLETE"
                ):
                    updated = (
                        BillingRecord.objects
                        .filter(
                            record_id=persisted["recordId"],
                            status="OCR_COMPLETE",
                        )
                        .update(status="NEEDS_REVIEW")
                    )

                    if updated != 1:
                        raise RuntimeError(
                            "Failed to update OCR review status."
                        )

                    persisted["status"] = "NEEDS_REVIEW"

                # Complete the OCR job and preserve its full result.
                current_job.status = OCRJob.Status.COMPLETED
                current_job.raw_result = result
                current_job.completed_at = timezone.now()
                current_job.error_code = None
                current_job.error_message = None
                current_job.next_retry_at = None

                current_job.save()

            return persisted

        except Exception as exc:
            with transaction.atomic():
                current_job = (
                    OCRJob.objects
                    .select_for_update()
                    .get(job_id=job_id)
                )

                # Ignore results from obsolete worker attempts.
                if (
                    current_job.status != OCRJob.Status.PROCESSING
                    or current_job.attempt_count != attempt_token
                ):
                    return None

                current_job.error_code = getattr(exc, "code", type(exc).__name__)
                current_job.error_message = str(exc)[:2000]

                # Stop retrying once the attempt limit is reached.
                if getattr(exc, "retryable", None) is False or current_job.attempt_count >= current_job.max_attempts:
                    current_job.status = OCRJob.Status.FAILED
                    current_job.next_retry_at = None

                    record = current_job.document.billing_record

                    if record.status == "OCR_PROCESSING":
                        record.status = "EXCEPTION"
                        record.save(
                            update_fields=[
                                "status",
                                "updated_at",
                            ]
                        )

                else:
                    # Retry using exponential backoff.
                    current_job.status = OCRJob.Status.RETRY_PENDING

                    retry_delay = 2 ** current_job.attempt_count

                    current_job.next_retry_at = (
                        timezone.now()
                        + timedelta(seconds=retry_delay)
                    )

                current_job.save()

            raise
