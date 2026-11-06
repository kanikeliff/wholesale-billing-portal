from unittest.mock import Mock
from django.test import TestCase
from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import AuditEvent, Recommendation
from application.services.recommendation_service import RecommendationService
from application.services.workflow_service import WorkflowService
from infrastructure.database.django_billing_record_repository import DjangoBillingRecordRepository
from infrastructure.database.django_persistence_recommendation_repository import DjangoPersistenceRecommendationRepository
from infrastructure.database.django_audit_correction_repository import DjangoAuditCorrectionRepository
from application.services.correction_service import CorrectionService


class ConcurrentReviewTests(TestCase):
    def setUp(self):
        self.record = BillingRecord.objects.create(status="RECOMMENDATION_READY", carrier="original")
        self.line = LineItem.objects.create(billing_record=self.record, line_number=1, net_gallons=100)
        self.repo = DjangoBillingRecordRepository()
        self.audit = DjangoAuditCorrectionRepository()
        self.provider = Mock()
        self.service = RecommendationService(self.provider, self.repo, WorkflowService(), self.repo,
                                             DjangoPersistenceRecommendationRepository())
        self.advice = {"recommendation": "REVIEW_REQUIRED", "confidence": 0.5, "modelVersion": "test"}

    def test_correction_during_network_call_blocks_stale_recommendation(self):
        def evaluate(record):
            self.audit.apply_record_field_correction(record_id=self.record.pk, field_name="carrier",
                                                      old_value="original", new_value="corrected")
            return self.advice
        self.provider.evaluate.side_effect = evaluate
        with self.assertRaisesRegex(ValueError, "changed during evaluation"):
            self.service.evaluate_record_by_id(str(self.record.pk))
        self.record.refresh_from_db()
        self.assertEqual(self.record.carrier, "corrected")
        self.assertEqual(self.record.status, "RECOMMENDATION_PENDING")
        self.assertFalse(Recommendation.objects.exists())

    def test_final_decision_during_evaluation_is_never_reopened(self):
        def evaluate(record):
            self.record.refresh_from_db(); self.record.status = "EXCEPTION"
            self.record.save(update_fields=["status", "updated_at"])
            return self.advice
        self.provider.evaluate.side_effect = evaluate
        with self.assertRaises(ValueError):
            self.service.evaluate_record_by_id(str(self.record.pk))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, "EXCEPTION")
        self.assertFalse(Recommendation.objects.exists())

    def test_unchanged_evaluation_still_persists_success(self):
        self.provider.evaluate.return_value = self.advice
        result = self.service.evaluate_record_by_id(str(self.record.pk))
        self.assertEqual(result["status"], "RECOMMENDATION_READY")
        self.assertEqual(Recommendation.objects.count(), 1)

    def test_stale_start_is_rejected_before_external_request(self):
        old = self.repo.get_by_id(str(self.record.pk))["updatedAt"]
        self.record.carrier = "other edit"; self.record.save()
        with self.assertRaisesRegex(ValueError, "changed"):
            self.repo.start_recommendation(self.record.pk, old)

    def test_finalized_record_rejects_stale_header_and_line_correction(self):
        self.record.status = "REJECTED"; self.record.save()
        with self.assertRaisesRegex(ValueError, "cannot be corrected"):
            self.audit.apply_record_field_correction(record_id=self.record.pk, field_name="carrier", old_value="original", new_value="bad")
        with self.assertRaisesRegex(ValueError, "cannot be corrected"):
            self.audit.apply_line_item_correction(record_id=self.record.pk, line_item_id=self.line.pk,
                                                  field_name="netGallons", old_value=100, new_value=101)
        self.assertFalse(AuditEvent.objects.exists())

    def test_competing_correction_cannot_overwrite_a_new_value(self):
        self.audit.apply_record_field_correction(record_id=self.record.pk, field_name="carrier", old_value="original", new_value="first")
        with self.assertRaisesRegex(ValueError, "Field changed"):
            self.audit.apply_record_field_correction(record_id=self.record.pk, field_name="carrier", old_value="original", new_value="stale")
        self.record.refresh_from_db(); self.assertEqual(self.record.carrier, "first")
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_nonfinite_numeric_inputs_are_rejected(self):
        service = CorrectionService(self.repo)
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaisesRegex(ValueError, "finite"):
                service._validate_value("netGallons", value)
            with self.assertRaises(ValueError):
                self.audit.apply_line_item_correction(record_id=self.record.pk, line_item_id=self.line.pk,
                                                      field_name="netGallons", old_value=100, new_value=value)
        self.line.refresh_from_db(); self.assertEqual(self.line.net_gallons, 100)
        self.assertFalse(AuditEvent.objects.exists())

    def test_failed_old_evaluation_cannot_report_a_finalized_record_as_pending(self):
        from infrastructure.team_a.exceptions import TeamAUnavailableError
        def evaluate(record):
            self.record.refresh_from_db(); self.record.status = "EXCEPTION"; self.record.save()
            raise TeamAUnavailableError("temporary failure")
        self.provider.evaluate.side_effect = evaluate
        with self.assertRaisesRegex(ValueError, "changed during evaluation"):
            self.service.evaluate_record_by_id(str(self.record.pk))
        self.record.refresh_from_db(); self.assertEqual(self.record.status, "EXCEPTION")

    def test_http_api_reports_stale_evaluation_as_conflict(self):
        from unittest.mock import patch
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        api = APIClient(); api.force_authenticate(get_user_model().objects.create_user(username="race-test"))
        def evaluate(record):
            self.audit.apply_record_field_correction(record_id=self.record.pk, field_name="carrier", old_value="original", new_value="fresh")
            return self.advice
        self.provider.evaluate.side_effect = evaluate
        with patch("presentation.api.billing_views.recommendation_service", self.service):
            response = api.post(f"/api/v1/billing-records/{self.record.pk}/evaluate/", {}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Recommendation.objects.exists())
