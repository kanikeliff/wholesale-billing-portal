from django.urls import path

from presentation.api.health_views import health_view
from presentation.api.billing_views import (
    BillingRecordDetailView,
    BillingRecordValidationView,
    BillingRecordRecommendationView,
    BillingRecordFieldCorrectionView,
    BillingRecordLineItemCorrectionView,
    BillingRecordDecisionView,
    BillingRecordListView,
)


from presentation.api.upload_views import (
    BillingRecordUploadView,
)

urlpatterns = [
    path(
        "billing-records/upload/",
        BillingRecordUploadView.as_view(),
        name="billing-record-upload",
    ),

    path(
    "billing-records/",
    BillingRecordListView.as_view(),
    name="billing-record-list",
    ),
    path(
    "billing-records/<str:record_id>/decision/",
    BillingRecordDecisionView.as_view(),
    name="billing-record-decision",
    ),
    path(
    "billing-records/<str:record_id>/fields/<str:field_name>/",
    BillingRecordFieldCorrectionView.as_view(),
    name="billing-record-field-correction",
    ),

    path(
    "billing-records/<str:record_id>/line-items/<str:line_item_id>/<str:field_name>/",
    BillingRecordLineItemCorrectionView.as_view(),
    name="billing-record-line-item-correction",
    ),

    path(
        "health/",
        health_view,
        name="health",
    ),

    path(
        "billing-records/<str:record_id>/",
        BillingRecordDetailView.as_view(),
        name="billing-record-detail",
    ),

    path(
        "billing-records/<str:record_id>/validate/",
        BillingRecordValidationView.as_view(),
        name="billing-record-validation",
    ),

    path(
        "billing-records/<str:record_id>/evaluate/",
        BillingRecordRecommendationView.as_view(),
        name="billing-record-evaluate",
    ),
]
