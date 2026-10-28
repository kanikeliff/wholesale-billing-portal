from application.services.document_file_service import DocumentFileService
from application.services.bol_upload_service import BOLUploadService
from application.services.ocr_processing_service import OCRProcessingService
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter
from infrastructure.ocr.mock_ocr_client import MockOCRClient

from application.services.correction_service import CorrectionService
from application.services.human_decision_service import HumanDecisionService
from application.services.recommendation_service import RecommendationService
from application.services.workflow_service import WorkflowService

from infrastructure.database.django_audit_correction_repository import (
    DjangoAuditCorrectionRepository,
)
from infrastructure.database.django_persistence_human_decision_repository import (
    DjangoPersistenceHumanDecisionRepository,
)
from infrastructure.database.django_persistence_recommendation_repository import (
    DjangoPersistenceRecommendationRepository,
)


def wire_database_persistence():
    import presentation.api.billing_views as billing_views

    billing_record_provider = billing_views.billing_record_provider
    billing_record_repository = billing_views.billing_record_repository

    # If the backend is intentionally running with a mock billing provider,
    # leave the existing mock runtime composition untouched.
    if billing_record_repository is None:
        return


    # Development upload pipeline:
    # Browser -> Django -> Mock OCR -> normalization -> PostgreSQL
    import presentation.api.upload_views as upload_views

    upload_views.BillingRecordUploadView.upload_service = BOLUploadService(
        ocr_client=MockOCRClient(),
        ocr_processing_service=OCRProcessingService(
            adapter=BolLabAdapter(),
            billing_record_repository=billing_record_repository,
        ),
        document_file_service=DocumentFileService(),
    )

    recommendation_provider = (
        billing_views.recommendation_service.recommendation_provider
    )

    billing_views.recommendation_service = RecommendationService(
        recommendation_provider=recommendation_provider,
        billing_record_provider=billing_record_provider,
        billing_record_repository=billing_record_repository,
        workflow_service=WorkflowService(),
        recommendation_repository=(
            DjangoPersistenceRecommendationRepository()
        ),
    )

    billing_views.correction_service = CorrectionService(
        billing_record_provider=billing_record_provider,
        correction_repository=DjangoAuditCorrectionRepository(),
        billing_record_repository=billing_record_repository,
        workflow_service=WorkflowService(),
    )

    billing_views.human_decision_service = HumanDecisionService(
        billing_record_provider=billing_record_provider,
        billing_record_repository=billing_record_repository,
        workflow_service=WorkflowService(),
        decision_repository=(
            DjangoPersistenceHumanDecisionRepository()
        ),
    )
