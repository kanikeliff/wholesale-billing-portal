import logging

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from application.services.bol_upload_service import (
    BOLUploadError,
    EmptyFileError,
    UnsupportedFileTypeError,
)
from application.services.document_file_service import (
    DocumentFileService,
)
from application.services.durable_bol_upload_service import (
    DurableBOLUploadService,
)


logger = logging.getLogger(__name__)


class BillingRecordUploadView(APIView):
    authentication_classes = []
    permission_classes = []

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    upload_service = DurableBOLUploadService(
        document_file_service=DocumentFileService()
    )

    def post(self, request):
        if self.upload_service is None:
            return Response(
                {
                    "code": "OCR_SERVICE_NOT_CONFIGURED",
                    "message": "Upload service is not configured.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        uploaded_file = request.FILES.get("file")

        if uploaded_file is None:
            return Response(
                {
                    "code": "FILE_REQUIRED",
                    "message": (
                        "multipart/form-data field 'file' is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = self.upload_service.upload(uploaded_file)

        except (UnsupportedFileTypeError, EmptyFileError) as error:
            return Response(
                {
                    "code": "INVALID_UPLOAD",
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except BOLUploadError as error:
            return Response(
                {
                    "code": "UPLOAD_FAILED",
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception("Durable BOL upload failed.")

            return Response(
                {
                    "code": "UPLOAD_FAILED",
                    "message": "Unable to store the uploaded document.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            result,
            status=status.HTTP_201_CREATED,
        )
