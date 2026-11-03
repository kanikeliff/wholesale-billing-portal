
import uuid

from django.core.files.storage import default_storage
from django.db import transaction

from apps.billing.models import BillingRecord
from apps.persistence.models import OCRJob
from infrastructure.ocr.runtime_configuration import get_ocr_provider, ensure_live_worker_ready

from application.services.bol_upload_service import (
    BOLUploadService,
    EmptyFileError,
)


class DurableBOLUploadService:
    def __init__(self, document_file_service):
        self.document_file_service = document_file_service

    def upload(self, uploaded_file):
        validator = BOLUploadService(
            ocr_client=None,
            ocr_processing_service=None,
        )

        validator._validate_file(uploaded_file)

        file_bytes = uploaded_file.read()

        if not file_bytes:
            raise EmptyFileError("Uploaded file is empty.")

        validator._validate_signature(
            filename=uploaded_file.name,
            file_bytes=file_bytes,
        )

        provider = get_ocr_provider()
        if provider == "live":
            ensure_live_worker_ready()

        document_id = str(uuid.uuid4())
        stored_path = None

        try:
            with transaction.atomic():
                record = BillingRecord.objects.create(
                    status="UPLOADED"
                )

                document = (
                    self.document_file_service.store_uploaded_document(
                        record_id=record.record_id,
                        document_id=document_id,
                        original_filename=uploaded_file.name,
                        file_bytes=file_bytes,
                        mime_type=getattr(
                            uploaded_file,
                            "content_type",
                            None,
                        ),
                    )
                )

                stored_path = document["storagePath"]

                job = OCRJob.objects.create(
                    document_id=document_id,
                    status=OCRJob.Status.PENDING,
                    max_attempts=1 if provider == "live" else 3,
                    raw_result={"requestedProvider": provider},
                )

            return {
                "recordId": str(record.record_id),
                "documentId": document["documentId"],
                "jobId": str(job.job_id),
                "status": record.status,
                "ocrStatus": job.status,
                "ocrProvider": provider,
                "documentUrl": document["documentUrl"],
            }

        except Exception:
            if stored_path:
                default_storage.delete(stored_path)
            raise
