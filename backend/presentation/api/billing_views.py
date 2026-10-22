from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from application.services.correction_service import CorrectionService
from application.services.billing_record_service import BillingRecordService
from application.services.billing_validation_service import BillingValidationService
from application.services.recommendation_service import RecommendationService
from application.services.workflow_service import WorkflowService
from application.validators.billing_record_validator import BillingRecordValidator
from core.exceptions.integration_exception import IntegrationException
from infrastructure.mock.mock_billing_record_provider import (
    MockBillingRecordProvider,
)
from infrastructure.team_a.mock_team_a_adapter import MockTeamAAdapter


billing_record_provider = MockBillingRecordProvider()

billing_record_service = BillingRecordService(
    billing_record_provider=billing_record_provider
)

billing_validation_service = BillingValidationService(
    billing_record_provider=billing_record_provider,
    validator=BillingRecordValidator(),
)

recommendation_service = RecommendationService(
    recommendation_provider=MockTeamAAdapter(),
    billing_record_provider=billing_record_provider,
    workflow_service=WorkflowService(),
)
correction_service = CorrectionService(
    billing_record_provider=billing_record_provider,
    workflow_service=WorkflowService(),
)
class BillingRecordFieldCorrectionView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, record_id, field_name):
        try:
            if "value" not in request.data:
                return Response(
                    {
                        "code": "CORRECTED_VALUE_REQUIRED",
                        "message": "Request body must include 'value'.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = correction_service.correct_record_field(
                record_id,
                field_name,
                request.data.get("value"),
                reviewed_by=request.data.get("reviewedBy"),
            )

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except ValueError as error:
            message = str(error)

            if message == "Billing record not found.":
                return Response(
                    {
                        "code": "BILLING_RECORD_NOT_FOUND",
                        "message": message,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if "cannot be corrected while in" in message:
                return Response(
                    {
                        "code": "INVALID_WORKFLOW_TRANSITION",
                        "message": message,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(
                {
                    "code": "INVALID_CORRECTION",
                    "message": message,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class BillingRecordLineItemCorrectionView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(
        self,
        request,
        record_id,
        line_item_id,
        field_name,
    ):
        try:
            if "value" not in request.data:
                return Response(
                    {
                        "code": "CORRECTED_VALUE_REQUIRED",
                        "message": "Request body must include 'value'.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = correction_service.correct_line_item_field(
                record_id,
                line_item_id,
                field_name,
                request.data.get("value"),
                reviewed_by=request.data.get("reviewedBy"),
            )

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except ValueError as error:
            message = str(error)

            if message == "Billing record not found.":
                return Response(
                    {
                        "code": "BILLING_RECORD_NOT_FOUND",
                        "message": message,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if message == "Line item not found.":
                return Response(
                    {
                        "code": "LINE_ITEM_NOT_FOUND",
                        "message": message,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if "cannot be corrected while in" in message:
                return Response(
                    {
                        "code": "INVALID_WORKFLOW_TRANSITION",
                        "message": message,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(
                {
                    "code": "INVALID_CORRECTION",
                    "message": message,
                },
                status=status.HTTP_400_BAD_REQUEST,
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


class BillingRecordRecommendationView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, record_id):
        try:
            result = recommendation_service.evaluate_record_by_id(
                record_id
            )

            if result.get("pending"):
                return Response(
                    result,
                    status=status.HTTP_202_ACCEPTED,
                )

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except ValueError as error:
            message = str(error)

            if message == "Billing record not found.":
                return Response(
                    {
                        "code": "BILLING_RECORD_NOT_FOUND",
                        "message": message,
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            return Response(
                {
                    "code": "INVALID_WORKFLOW_TRANSITION",
                    "message": message,
                },
                status=status.HTTP_409_CONFLICT,
            )

        except IntegrationException as error:
            return Response(
                error.to_dict(),
                status=status.HTTP_502_BAD_GATEWAY,
            )
