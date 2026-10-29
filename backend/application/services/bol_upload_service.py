import time
import uuid
from pathlib import Path


class BOLUploadError(Exception):
    pass


class UnsupportedFileTypeError(BOLUploadError):
    pass


class EmptyFileError(BOLUploadError):
    pass


class OCRProcessingError(BOLUploadError):
    pass


class OCRTimeoutError(BOLUploadError):
    pass


class BOLUploadService:
    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
    }

    ALLOWED_CONTENT_TYPES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
    }

    def __init__(
        self,
        *,
        ocr_client,
        ocr_processing_service,
        document_file_service=None,
        max_file_size_bytes=20 * 1024 * 1024,
        poll_interval_seconds=1,
        poll_timeout_seconds=30,
    ):
        self.ocr_client = ocr_client
        self.ocr_processing_service = ocr_processing_service
        self.document_file_service = document_file_service
        self.max_file_size_bytes = max_file_size_bytes
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_timeout_seconds = poll_timeout_seconds

    def upload(self, uploaded_file):
        self._validate_file(uploaded_file)

        file_bytes = uploaded_file.read()

        if not file_bytes:
            raise EmptyFileError(
                "Uploaded file is empty."
            )

        self._validate_signature(
            filename=uploaded_file.name,
            file_bytes=file_bytes,
        )

        document_id = str(uuid.uuid4())

        try:
            ocr_result = self.ocr_client.submit_document(
                document_id=document_id,
                file_bytes=file_bytes,
                filename=uploaded_file.name,
            )
        except Exception as error:
            raise OCRProcessingError(
                "Unable to submit document to OCR service."
            ) from error

        extraction = self._resolve_extraction(
            ocr_result
        )

        persisted = (
            self.ocr_processing_service
            .persist_extraction(extraction)
        )

        document = None

        if self.document_file_service is not None:
            try:
                document = (
                    self.document_file_service
                    .store_uploaded_document(
                        record_id=persisted["recordId"],
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
            except Exception as storage_error:
                try:
                    (
                        self.ocr_processing_service
                        .rollback_persisted_record(
                            persisted["recordId"]
                        )
                    )
                except Exception as rollback_error:
                    if hasattr(storage_error, "add_note"):
                        storage_error.add_note(
                            "Billing-record rollback also failed: "
                            f"{rollback_error}"
                        )

                raise

        return {
            "recordId": persisted["recordId"],
            "status": persisted["status"],
            "documentId": (
                document["documentId"]
                if document
                else document_id
            ),
            "documentUrl": (
                document["documentUrl"]
                if document
                else None
            ),
            "filename": uploaded_file.name,
        }

    def _validate_file(self, uploaded_file):
        if uploaded_file is None:
            raise EmptyFileError(
                "A file is required."
            )

        filename = getattr(
            uploaded_file,
            "name",
            "",
        )

        extension = Path(
            filename
        ).suffix.lower()

        if extension not in self.ALLOWED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                "Supported file types are PDF, JPG, JPEG, and PNG."
            )

        content_type = getattr(
            uploaded_file,
            "content_type",
            None,
        )

        if (
            content_type
            and content_type
            not in self.ALLOWED_CONTENT_TYPES
        ):
            raise UnsupportedFileTypeError(
                "The uploaded file content type is not supported."
            )

        size = getattr(
            uploaded_file,
            "size",
            0,
        )

        if size == 0:
            raise EmptyFileError(
                "Uploaded file is empty."
            )

        if size > self.max_file_size_bytes:
            raise BOLUploadError(
                "Uploaded file exceeds the maximum allowed size."
            )

    def _validate_signature(
        self,
        *,
        filename,
        file_bytes,
    ):
        extension = Path(
            filename
        ).suffix.lower()

        if extension == ".pdf":
            valid = file_bytes.startswith(
                b"%PDF-"
            )

        elif extension in {
            ".jpg",
            ".jpeg",
        }:
            valid = file_bytes.startswith(
                b"\xff\xd8\xff"
            )

        elif extension == ".png":
            valid = file_bytes.startswith(
                b"\x89PNG\r\n\x1a\n"
            )

        else:
            valid = False

        if not valid:
            raise UnsupportedFileTypeError(
                "File content does not match its extension."
            )

    def _resolve_extraction(self, result):
        if not isinstance(result, dict):
            raise OCRProcessingError(
                "OCR service returned an invalid response."
            )

        extraction = result.get(
            "extraction"
        )

        if extraction is not None:
            return extraction

        if self._looks_like_extraction(
            result
        ):
            return result

        job_id = (
            result.get("jobId")
            or result.get("job_id")
        )

        if not job_id:
            raise OCRProcessingError(
                "OCR response contains neither extraction data nor a job ID."
            )

        return self._poll_job(job_id)

    def _poll_job(self, job_id):
        deadline = (
            time.monotonic()
            + self.poll_timeout_seconds
        )

        while time.monotonic() < deadline:
            try:
                result = (
                    self.ocr_client
                    .get_job(job_id)
                )
            except Exception as error:
                raise OCRProcessingError(
                    "Unable to retrieve OCR job."
                ) from error

            status = str(
                result.get(
                    "status",
                    "",
                )
            ).upper()

            if status in {
                "COMPLETED",
                "COMPLETE",
                "SUCCESS",
                "SUCCEEDED",
            }:
                extraction = (
                    result.get(
                        "extraction"
                    )
                )

                if extraction is None:
                    raise OCRProcessingError(
                        "OCR job completed without extraction data."
                    )

                return extraction

            if status in {
                "FAILED",
                "ERROR",
                "CANCELLED",
            }:
                raise OCRProcessingError(
                    result.get(
                        "message",
                        "OCR processing failed.",
                    )
                )

            time.sleep(
                self.poll_interval_seconds
            )

        raise OCRTimeoutError(
            "OCR processing timed out."
        )

    @staticmethod
    def _looks_like_extraction(data):
        extraction_keys = {
            "bol_number",
            "origin",
            "supplier",
            "carrier",
            "transaction_date",
            "products",
        }

        return bool(
            extraction_keys.intersection(
                data.keys()
            )
        )