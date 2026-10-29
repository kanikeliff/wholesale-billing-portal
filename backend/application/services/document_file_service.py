import hashlib
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from apps.billing.models import BillingRecord
from apps.persistence.models import Document


class DocumentFileService:

    def store_uploaded_document(
        self,
        *,
        record_id,
        document_id,
        original_filename,
        file_bytes,
        mime_type=None,
    ):
        try:
            billing_record = BillingRecord.objects.get(
                record_id=record_id
            )
        except (BillingRecord.DoesNotExist, ValueError):
            raise ValueError("Billing record not found.")

        extension = Path(original_filename).suffix.lower()

        storage_path = (
            f"bols/{document_id}{extension}"
        )

        saved_path = default_storage.save(
            storage_path,
            ContentFile(file_bytes),
        )

        checksum_sha256 = hashlib.sha256(
            file_bytes
        ).hexdigest()

        try:
            with transaction.atomic():
                document = Document.objects.create(
                    document_id=uuid.UUID(str(document_id)),
                    billing_record=billing_record,
                    original_filename=original_filename,
                    storage_path=saved_path,
                    mime_type=mime_type,
                    file_size_bytes=len(file_bytes),
                    checksum_sha256=checksum_sha256,
                )

                serialized = self.serialize(document)
        except Exception:
            default_storage.delete(saved_path)
            raise

        return serialized

    def get_latest_for_record(self, record_id):
        return (
            Document.objects
            .filter(billing_record_id=record_id)
            .order_by("-created_at")
            .first()
        )

    def serialize(self, document):
        document_url = None

        if document.storage_path:
            document_url = default_storage.url(
                document.storage_path
            )

        return {
            "documentId": str(document.document_id),
            "recordId": str(document.billing_record_id),
            "originalFilename": document.original_filename,
            "mimeType": document.mime_type,
            "fileSizeBytes": document.file_size_bytes,
            "checksumSha256": document.checksum_sha256,
            "storagePath": document.storage_path,
            "documentUrl": document_url,
            "createdAt": (
                document.created_at.isoformat()
                if document.created_at
                else None
            ),
        }
