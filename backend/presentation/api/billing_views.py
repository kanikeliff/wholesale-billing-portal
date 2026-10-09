from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from application.services.billing_record_service import BillingRecordService
from infrastructure.database.django_billing_record_provider import (
    DjangoBillingRecordProvider,
)


billing_record_service = BillingRecordService(
    billing_record_provider=DjangoBillingRecordProvider()
)


class BillingRecordDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, record_id):
        try:
            record = billing_record_service.get_record(record_id)

            return Response(
                record,
                status=status.HTTP_200_OK
            )

        except ValueError as error:
            return Response(
                {
                    "code": "BILLING_RECORD_NOT_FOUND",
                    "message": str(error)
                },
                status=status.HTTP_404_NOT_FOUND
            )
