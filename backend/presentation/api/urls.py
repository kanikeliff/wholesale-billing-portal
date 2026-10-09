from django.urls import path

from presentation.api.health_views import health_view
from presentation.api.billing_views import BillingRecordDetailView


urlpatterns = [
    path(
        "health/",
        health_view,
        name="health"
    ),

    path(
        "billing-records/<str:record_id>/",
        BillingRecordDetailView.as_view(),
        name="billing-record-detail"
    ),
]
