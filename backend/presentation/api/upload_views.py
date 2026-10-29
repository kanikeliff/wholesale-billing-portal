from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from application.services.bol_upload_service import (
    BOLUploadError,
    EmptyFileError,
    OCRProcessingError,
    OCRTimeoutError,
    UnsupportedFileTypeError,
)


class BillingRecordUploadView(APIView):
    authentication_classes = []
    permission_classes = []

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    upload_service = None

    def post(self, request):
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

        if self.upload_service is None:
            return Response(
                {
                    "code": "OCR_SERVICE_NOT_CONFIGURED",
                    "message": (
                        "The OCR upload service is not configured."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            result = self.upload_service.upload(
                uploaded_file
            )

            return Response(
                result,
                status=status.HTTP_201_CREATED,
            )

        except (
            UnsupportedFileTypeError,
            EmptyFileError,
        ) as error:
            return Response(
                {
                    "code": "INVALID_UPLOAD",
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except OCRTimeoutError as error:
            return Response(
                {
                    "code": "OCR_TIMEOUT",
                    "message": str(error),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except OCRProcessingError as error:
            return Response(
                {
                    "code": "OCR_PROCESSING_FAILED",
                    "message": str(error),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        except BOLUploadError as error:
            return Response(
                {
                    "code": "UPLOAD_FAILED",
                    "message": str(error),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )