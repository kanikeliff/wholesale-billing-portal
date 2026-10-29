#!/bin/bash
set -e

echo "=========================================="
echo " CLEAN RESET - Wholesale Billing Portal"
echo "=========================================="

rm -rf backend frontend contracts docs
rm -f requirements.txt docker-compose.yml .env.example

# ROOT FILES
touch requirements.txt
touch docker-compose.yml
touch .env.example

# =========================================================
# BACKEND
# =========================================================

mkdir -p backend/config

mkdir -p backend/apps/documents
mkdir -p backend/apps/billing
mkdir -p backend/apps/review
mkdir -p backend/apps/workflow/states

mkdir -p backend/core/enums
mkdir -p backend/core/exceptions
mkdir -p backend/core/responses
mkdir -p backend/core/events
mkdir -p backend/core/utils

mkdir -p backend/domain/entities
mkdir -p backend/domain/repositories
mkdir -p backend/domain/services

mkdir -p backend/application/services
mkdir -p backend/application/commands
mkdir -p backend/application/facades
mkdir -p backend/application/validators

mkdir -p backend/infrastructure/database
mkdir -p backend/infrastructure/ocr
mkdir -p backend/infrastructure/team_a
mkdir -p backend/infrastructure/storage
mkdir -p backend/infrastructure/http

mkdir -p backend/presentation/api
mkdir -p backend/presentation/serializers
mkdir -p backend/presentation/permissions

mkdir -p backend/tests

# DJANGO CONFIG
touch backend/manage.py
touch backend/config/__init__.py
touch backend/config/settings.py
touch backend/config/urls.py
touch backend/config/asgi.py
touch backend/config/wsgi.py

# APPS
touch backend/apps/__init__.py

for app in documents billing review; do
  touch backend/apps/$app/__init__.py
  touch backend/apps/$app/apps.py
  touch backend/apps/$app/urls.py
  touch backend/apps/$app/views.py
  touch backend/apps/$app/serializers.py
  touch backend/apps/$app/services.py
  touch backend/apps/$app/validators.py
  touch backend/apps/$app/tests.py
done

touch backend/apps/workflow/__init__.py
touch backend/apps/workflow/apps.py
touch backend/apps/workflow/services.py
touch backend/apps/workflow/state_factory.py
touch backend/apps/workflow/tests.py

touch backend/apps/workflow/states/__init__.py
touch backend/apps/workflow/states/base_state.py
touch backend/apps/workflow/states/uploaded_state.py
touch backend/apps/workflow/states/ocr_processing_state.py
touch backend/apps/workflow/states/ocr_complete_state.py
touch backend/apps/workflow/states/needs_review_state.py
touch backend/apps/workflow/states/recommendation_pending_state.py
touch backend/apps/workflow/states/recommendation_ready_state.py
touch backend/apps/workflow/states/approved_state.py
touch backend/apps/workflow/states/rejected_state.py
touch backend/apps/workflow/states/exception_state.py

# CORE
touch backend/core/__init__.py

touch backend/core/enums/__init__.py
touch backend/core/enums/record_status.py
touch backend/core/enums/recommendation_status.py
touch backend/core/enums/field_quality.py
touch backend/core/enums/exception_severity.py
touch backend/core/enums/user_action.py

touch backend/core/exceptions/__init__.py
touch backend/core/exceptions/base_exception.py
touch backend/core/exceptions/workflow_exception.py
touch backend/core/exceptions/validation_exception.py
touch backend/core/exceptions/integration_exception.py
touch backend/core/exceptions/not_found_exception.py

touch backend/core/responses/__init__.py
touch backend/core/responses/api_response.py
touch backend/core/responses/error_response.py

touch backend/core/events/__init__.py
touch backend/core/events/base_event.py
touch backend/core/events/document_events.py
touch backend/core/events/workflow_events.py
touch backend/core/events/recommendation_events.py

touch backend/core/utils/__init__.py
touch backend/core/utils/datetime_utils.py
touch backend/core/utils/file_utils.py
touch backend/core/utils/id_utils.py

# DOMAIN
touch backend/domain/__init__.py

touch backend/domain/entities/__init__.py
touch backend/domain/entities/document.py
touch backend/domain/entities/billing_record.py
touch backend/domain/entities/line_item.py
touch backend/domain/entities/extracted_field.py
touch backend/domain/entities/recommendation.py
touch backend/domain/entities/human_decision.py
touch backend/domain/entities/exception_indicator.py

touch backend/domain/repositories/__init__.py
touch backend/domain/repositories/document_repository.py
touch backend/domain/repositories/billing_record_repository.py
touch backend/domain/repositories/recommendation_repository.py

touch backend/domain/services/__init__.py
touch backend/domain/services/normalization_service.py
touch backend/domain/services/validation_service.py

# APPLICATION
touch backend/application/__init__.py

touch backend/application/services/__init__.py
touch backend/application/services/document_service.py
touch backend/application/services/billing_record_service.py
touch backend/application/services/workflow_service.py
touch backend/application/services/review_service.py
touch backend/application/services/recommendation_service.py

touch backend/application/commands/__init__.py
touch backend/application/commands/upload_document_command.py
touch backend/application/commands/update_field_command.py
touch backend/application/commands/submit_recommendation_command.py
touch backend/application/commands/approve_record_command.py
touch backend/application/commands/reject_record_command.py
touch backend/application/commands/mark_exception_command.py

touch backend/application/facades/__init__.py
touch backend/application/facades/billing_workflow_facade.py

touch backend/application/validators/__init__.py
touch backend/application/validators/document_validator.py
touch backend/application/validators/billing_record_validator.py
touch backend/application/validators/workflow_validator.py
touch backend/application/validators/recommendation_validator.py

# INFRASTRUCTURE
touch backend/infrastructure/__init__.py

touch backend/infrastructure/database/__init__.py
touch backend/infrastructure/database/mongo_client.py
touch backend/infrastructure/database/mongo_document_repository.py
touch backend/infrastructure/database/mongo_billing_record_repository.py
touch backend/infrastructure/database/mongo_recommendation_repository.py

touch backend/infrastructure/ocr/__init__.py
touch backend/infrastructure/ocr/ocr_provider.py
touch backend/infrastructure/ocr/paddle_ocr_adapter.py
touch backend/infrastructure/ocr/mock_ocr_adapter.py
touch backend/infrastructure/ocr/ocr_factory.py

touch backend/infrastructure/team_a/__init__.py
touch backend/infrastructure/team_a/recommendation_provider.py
touch backend/infrastructure/team_a/team_a_client.py
touch backend/infrastructure/team_a/team_a_adapter.py
touch backend/infrastructure/team_a/team_a_mapper.py
touch backend/infrastructure/team_a/team_a_dto.py
touch backend/infrastructure/team_a/mock_team_a_adapter.py

touch backend/infrastructure/storage/__init__.py
touch backend/infrastructure/storage/document_storage.py
touch backend/infrastructure/storage/local_document_storage.py

touch backend/infrastructure/http/__init__.py
touch backend/infrastructure/http/http_client.py

# PRESENTATION
touch backend/presentation/__init__.py

touch backend/presentation/api/__init__.py
touch backend/presentation/api/urls.py
touch backend/presentation/api/document_views.py
touch backend/presentation/api/billing_record_views.py
touch backend/presentation/api/review_views.py
touch backend/presentation/api/recommendation_views.py

touch backend/presentation/serializers/__init__.py
touch backend/presentation/serializers/document_serializer.py
touch backend/presentation/serializers/billing_record_serializer.py
touch backend/presentation/serializers/line_item_serializer.py
touch backend/presentation/serializers/review_serializer.py
touch backend/presentation/serializers/recommendation_serializer.py

touch backend/presentation/permissions/__init__.py
touch backend/presentation/permissions/record_permissions.py

# TESTS
touch backend/tests/__init__.py
touch backend/tests/test_document_service.py
touch backend/tests/test_billing_record_service.py
touch backend/tests/test_workflow_service.py
touch backend/tests/test_review_service.py
touch backend/tests/test_team_a_adapter.py
touch backend/tests/test_ocr_adapter.py
touch backend/tests/test_api_endpoints.py

# =========================================================
# FRONTEND
# =========================================================

mkdir -p frontend/src/api
mkdir -p frontend/src/components
mkdir -p frontend/src/pages
mkdir -p frontend/src/hooks
mkdir -p frontend/src/services
mkdir -p frontend/src/adapters
mkdir -p frontend/src/types

touch frontend/package.json
touch frontend/tsconfig.json
touch frontend/vite.config.ts
touch frontend/index.html

touch frontend/src/main.tsx
touch frontend/src/App.tsx

touch frontend/src/api/apiClient.ts
touch frontend/src/api/documentApi.ts
touch frontend/src/api/billingRecordApi.ts
touch frontend/src/api/reviewApi.ts
touch frontend/src/api/recommendationApi.ts

touch frontend/src/components/DocumentUploader.tsx
touch frontend/src/components/RecordStatusBadge.tsx
touch frontend/src/components/FieldEditor.tsx
touch frontend/src/components/ConfidenceIndicator.tsx
touch frontend/src/components/RecommendationCard.tsx
touch frontend/src/components/ExceptionList.tsx
touch frontend/src/components/ReviewActions.tsx

touch frontend/src/pages/UploadPage.tsx
touch frontend/src/pages/DashboardPage.tsx
touch frontend/src/pages/ReviewPage.tsx

touch frontend/src/hooks/useBillingRecord.ts
touch frontend/src/hooks/useWorkflowStatus.ts

touch frontend/src/services/billingService.ts
touch frontend/src/services/workflowService.ts

touch frontend/src/adapters/billingRecordAdapter.ts
touch frontend/src/adapters/recommendationAdapter.ts

touch frontend/src/types/document.ts
touch frontend/src/types/billingRecord.ts
touch frontend/src/types/lineItem.ts
touch frontend/src/types/recommendation.ts
touch frontend/src/types/workflow.ts

# =========================================================
# CONTRACTS
# =========================================================

mkdir -p contracts

touch contracts/normalized-bol.schema.json
touch contracts/team-a-request.schema.json
touch contracts/team-a-response.schema.json
touch contracts/team-a-feedback.schema.json
touch contracts/error-response.schema.json
touch contracts/record-status.schema.json

# =========================================================
# DOCS
# =========================================================

mkdir -p docs/architecture
mkdir -p docs/api
mkdir -p docs/workflows

touch docs/architecture/system-overview.md
touch docs/architecture/backend-architecture.md
touch docs/architecture/design-patterns.md

touch docs/api/backend-api.md
touch docs/api/team-a-api-contract.md

touch docs/workflows/document-processing-workflow.md
touch docs/workflows/recommendation-workflow.md
touch docs/workflows/human-review-workflow.md

echo ""
echo "=========================================="
echo " FINAL STRUCTURE CREATED SUCCESSFULLY"
echo "=========================================="
