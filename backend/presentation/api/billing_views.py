import os
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from application.services.billing_record_service import BillingRecordService
from application.services.billing_validation_service import BillingValidationService
from application.services.correction_service import CorrectionService
from application.services.human_decision_service import HumanDecisionService
from application.services.recommendation_service import RecommendationService
from application.services.workflow_service import WorkflowService
from application.validators.billing_record_validator import BillingRecordValidator
from core.exceptions.integration_exception import IntegrationException
from infrastructure.mock.mock_billing_record_provider import (
    MockBillingRecordProvider,
)
from infrastructure.team_a.provider_factory import (
    build_recommendation_provider,
)
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)
from infrastructure.database.django_audit_correction_repository import (
    DjangoAuditCorrectionRepository,
)
from infrastructure.database.django_persistence_human_decision_repository import (
    DjangoPersistenceHumanDecisionRepository,
)
from application.services.document_file_service import DocumentFileService
# -------------------------------------------------------------------
# Service composition
# -------------------------------------------------------------------
document_file_service = DocumentFileService()
use_mock_provider = (
    os.getenv(
        "USE_MOCK_BILLING_PROVIDER",
        "true",
    ).lower()
    == "true"
)

if use_mock_provider:
    billing_record_provider = MockBillingRecordProvider()
    billing_record_repository = None
    correction_repository = None
    decision_repository = None
else:
    billing_record_provider = DjangoBillingRecordRepository()
    billing_record_repository = billing_record_provider
    correction_repository = DjangoAuditCorrectionRepository()
    decision_repository = DjangoPersistenceHumanDecisionRepository()

billing_record_service = BillingRecordService(
    billing_record_provider=billing_record_provider
)

billing_validation_service = BillingValidationService(
    billing_record_provider=billing_record_provider,
    validator=BillingRecordValidator(),
)

recommendation_service = RecommendationService(
    recommendation_provider=build_recommendation_provider(),
    billing_record_provider=billing_record_provider,
    billing_record_repository=billing_record_repository,
    workflow_service=WorkflowService(),
)

correction_service = CorrectionService(
    billing_record_provider=billing_record_provider,
    correction_repository=correction_repository,
    billing_record_repository=billing_record_repository,
    workflow_service=WorkflowService(),
)

human_decision_service = HumanDecisionService(
    billing_record_provider=billing_record_provider,
    billing_record_repository=billing_record_repository,
    decision_repository=decision_repository,
    workflow_service=WorkflowService(),
)




def _authenticated_actor(request):
    user = request.user

    if not user or not user.is_authenticated:
        raise ValueError("Authenticated user is required.")

    username = user.get_username()

    if username:
        return username

    return str(user.pk)


# -------------------------------------------------------------------
# Billing record list
# -------------------------------------------------------------------

class BillingRecordListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        records = billing_record_service.list_records()

        return Response(
            {
                "count": len(records),
                "records": records,
            },
            status=status.HTTP_200_OK,
        )


# -------------------------------------------------------------------
# Billing record detail
# -------------------------------------------------------------------

class BillingRecordDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, record_id):
        try:
            record = billing_record_service.get_record(record_id)

            document = document_file_service.get_latest_for_record(
                record_id
            )

            record["document"] = (
                document_file_service.serialize(document)
                if document
                else None
            )

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

# -------------------------------------------------------------------
# Billing validation
# -------------------------------------------------------------------

class BillingRecordValidationView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, record_id):
        try:
            result = billing_validation_service.validate_record(
                record_id
            )

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


# -------------------------------------------------------------------
# Team A recommendation
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# BOL-level field correction
# -------------------------------------------------------------------

class BillingRecordFieldCorrectionView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, record_id, field_name):
        try:
            if "value" not in request.data:
                return Response(
                    {
                        "code": "CORRECTED_VALUE_REQUIRED",
                        "message": (
                            "Request body must include 'value'."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = correction_service.correct_record_field(
                record_id,
                field_name,
                request.data.get("value"),
                reviewed_by=_authenticated_actor(request),
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


# -------------------------------------------------------------------
# Line-item correction
# -------------------------------------------------------------------

class BillingRecordLineItemCorrectionView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

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
                        "message": (
                            "Request body must include 'value'."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = correction_service.correct_line_item_field(
                record_id,
                line_item_id,
                field_name,
                request.data.get("value"),
                reviewed_by=_authenticated_actor(request),
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


# -------------------------------------------------------------------
# Human decision
# -------------------------------------------------------------------

class BillingRecordDecisionView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, record_id):
        try:
            decision = request.data.get("decision")

            if decision is None:
                return Response(
                    {
                        "code": "DECISION_REQUIRED",
                        "message": (
                            "Request body must include 'decision'."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = human_decision_service.submit_decision(
                record_id,
                decision,
                decided_by=_authenticated_actor(request),
                reason=request.data.get("reason"),
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

            if "Invalid workflow transition" in message:
                return Response(
                    {
                        "code": "INVALID_WORKFLOW_TRANSITION",
                        "message": message,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(
                {
                    "code": "INVALID_DECISION",
                    "message": message,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )