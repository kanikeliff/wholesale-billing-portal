from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from application.services.billing_record_service import BillingRecordService
from application.services.billing_validation_service import BillingValidationService
from application.validators.billing_record_validator import BillingRecordValidator
from infrastructure.mock.mock_billing_record_provider import (
    MockBillingRecordProvider,
)


billing_record_provider = MockBillingRecordProvider()

billing_record_service = BillingRecordService(
    billing_record_provider=billing_record_provider
)

billing_validation_service = BillingValidationService(
    billing_record_provider=billing_record_provider,
    validator=BillingRecordValidator(),
)


class BillingRecordDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, record_id):
        try:
            record = billing_record_service.get_record(record_id)

            return Response(
                record,
                status=status.HTTP_200_OK,
            )

        except ValueError as error:
            return Response(
                {
                    "code": "BILLING_RECORD_NOT_FOUND",
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )


class BillingRecordValidationView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, record_id):
        try:
            result = billing_validation_service.validate_record(record_id)

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except ValueError as error:
            return Response(
                {
                    "code": "BILLING_RECORD_NOT_FOUND",
                    "message": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
