from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.billing.models import BillingRecord, LineItem
from apps.persistence.models import (
    AuditEvent,
    ExtractedField,
    HumanDecision,
    Recommendation,
)
from application.services.correction_service import CorrectionService
from application.services.human_decision_service import HumanDecisionService
from application.services.workflow_service import WorkflowService
from infrastructure.database.django_audit_correction_repository import (
    DjangoAuditCorrectionRepository,
)
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)
from infrastructure.database.django_persistence_human_decision_repository import (
    DjangoPersistenceHumanDecisionRepository,
)
from infrastructure.database.django_persistence_recommendation_repository import (
    DjangoPersistenceRecommendationRepository,
)


class DatabasePersistenceTests(TestCase):

    def setUp(self):
        self.billing_repository = DjangoBillingRecordRepository()
        self.recommendation_repository = (
            DjangoPersistenceRecommendationRepository()
        )
        self.correction_repository = DjangoAuditCorrectionRepository()
        self.decision_repository = (
            DjangoPersistenceHumanDecisionRepository()
        )
        self.workflow_service = WorkflowService()


    def test_billing_record_compensation_delete_cascades_line_items(self):
        record = BillingRecord.objects.create(
            bol_number="UPLOAD-COMPENSATION-TEST",
            status="OCR_COMPLETE",
        )

        line_item = LineItem.objects.create(
            billing_record=record,
            line_number=1,
            product="87 Gas",
            gross_gallons=Decimal("7000.00"),
            net_gallons=Decimal("6965.00"),
        )

        deleted = self.billing_repository.delete_billing_record(
            record.record_id
        )

        self.assertTrue(deleted)

        self.assertFalse(
            BillingRecord.objects.filter(
                record_id=record.record_id,
            ).exists()
        )

        self.assertFalse(
            LineItem.objects.filter(
                line_item_id=line_item.line_item_id,
            ).exists()
        )

    def test_recommendation_revisions_keep_one_current_revision(self):
        record = BillingRecord.objects.create(
            bol_number="REC-TEST",
            status="RECOMMENDATION_PENDING",
        )

        first = self.recommendation_repository.store_revision(
            record.record_id,
            {
                "recordId": str(record.record_id),
                "recommendation": "REVIEW_REQUIRED",
                "confidence": 0.68,
                "modelVersion": "test-v1",
                "rationale": "First test revision.",
                "mappedEntities": {},
                "exceptionIndicators": [],
            },
        )

        second = (
            self.recommendation_repository
            .store_revision_and_mark_ready(
                record.record_id,
                {
                    "recordId": str(record.record_id),
                    "recommendation": "APPROVE_RECOMMENDED",
                    "confidence": 0.92,
                    "modelVersion": "test-v2",
                    "rationale": "Second test revision.",
                    "mappedEntities": {},
                    "exceptionIndicators": [],
                },
            )
        )

        record.refresh_from_db()
        first.refresh_from_db()

        current = self.recommendation_repository.get_current(
            record.record_id
        )

        self.assertEqual(first.revision, 1)
        self.assertFalse(first.is_current)

        self.assertEqual(second.revision, 2)
        self.assertTrue(second.is_current)

        self.assertEqual(current.recommendation_id, second.recommendation_id)
        self.assertEqual(record.status, "RECOMMENDATION_READY")

        self.assertEqual(
            Recommendation.objects.filter(
                billing_record=record,
                is_current=True,
            ).count(),
            1,
        )


    def test_recommendation_persistence_rolls_back_when_status_update_fails(self):
        record = BillingRecord.objects.create(
            bol_number="REC-ROLLBACK-TEST",
            status="RECOMMENDATION_PENDING",
        )

        first = self.recommendation_repository.store_revision(
            record.record_id,
            {
                "recordId": str(record.record_id),
                "recommendation": "REVIEW_REQUIRED",
                "confidence": 0.70,
                "modelVersion": "rollback-v1",
                "rationale": "Initial recommendation.",
                "mappedEntities": {},
                "exceptionIndicators": [],
            },
        )

        with patch(
            "infrastructure.database."
            "django_persistence_recommendation_repository."
            "BillingRecord.save",
            side_effect=RuntimeError("status write failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "status write failed",
            ):
                self.recommendation_repository.store_revision_and_mark_ready(
                    record.record_id,
                    {
                        "recordId": str(record.record_id),
                        "recommendation": "APPROVE_RECOMMENDED",
                        "confidence": 0.95,
                        "modelVersion": "rollback-v2",
                        "rationale": "This revision must roll back.",
                        "mappedEntities": {},
                        "exceptionIndicators": [],
                    },
                )

        record.refresh_from_db()
        first.refresh_from_db()

        self.assertEqual(
            record.status,
            "RECOMMENDATION_PENDING",
        )
        self.assertTrue(first.is_current)

        self.assertEqual(
            Recommendation.objects.filter(
                billing_record=record,
            ).count(),
            1,
        )

        current = self.recommendation_repository.get_current(
            record.record_id
        )

        self.assertEqual(
            current.recommendation_id,
            first.recommendation_id,
        )
        self.assertEqual(first.revision, 1)

    def test_correction_service_updates_canonical_value_and_writes_audit(self):
        record = BillingRecord.objects.create(
            bol_number="CORRECTION-TEST",
            status="RECOMMENDATION_READY",
        )

        line_item = LineItem.objects.create(
            billing_record=record,
            line_number=1,
            product="87 Gas",
            gross_gallons=Decimal("7000.00"),
            net_gallons=Decimal("6965.00"),
        )

        extracted = ExtractedField.objects.create(
            billing_record=record,
            line_item=line_item,
            field_name="grossGallons",
            raw_value="7000",
            normalized_value=7000,
            confidence=Decimal("0.9400"),
            quality="OK",
        )

        service = CorrectionService(
            billing_record_provider=self.billing_repository,
            correction_repository=self.correction_repository,
            billing_record_repository=self.billing_repository,
            workflow_service=self.workflow_service,
        )

        result = service.correct_line_item_field(
            record_id=record.record_id,
            line_item_id=line_item.line_item_id,
            field_name="grossGallons",
            new_value=6995,
            reviewed_by="test-user",
        )

        record.refresh_from_db()
        line_item.refresh_from_db()
        extracted.refresh_from_db()

        audit = AuditEvent.objects.get(
            billing_record=record,
            line_item=line_item,
            field_name="grossGallons",
        )

        self.assertEqual(
            line_item.gross_gallons,
            Decimal("6995.00"),
        )
        self.assertEqual(
            record.status,
            "RECOMMENDATION_PENDING",
        )

        self.assertEqual(audit.old_value, 7000.0)
        self.assertEqual(audit.new_value, 6995)
        self.assertEqual(audit.actor_id, "test-user")

        self.assertEqual(extracted.raw_value, "7000")
        self.assertEqual(extracted.normalized_value, 7000)

        self.assertTrue(result["requiresReevaluation"])


    def test_record_correction_updates_value_status_and_writes_audit(self):
        record = BillingRecord.objects.create(
            bol_number="RECORD-CORRECTION-TEST",
            origin="Albany",
            status="RECOMMENDATION_READY",
        )

        audit = self.correction_repository.apply_record_field_correction(
            record_id=record.record_id,
            field_name="origin",
            old_value="Albany",
            new_value="Syracuse",
            reviewed_by="test-user",
        )

        record.refresh_from_db()

        self.assertEqual(record.origin, "Syracuse")
        self.assertEqual(
            record.status,
            "RECOMMENDATION_PENDING",
        )

        self.assertEqual(
            audit.billing_record_id,
            record.record_id,
        )
        self.assertEqual(audit.field_name, "origin")
        self.assertEqual(audit.old_value, "Albany")
        self.assertEqual(audit.new_value, "Syracuse")
        self.assertEqual(audit.actor_id, "test-user")
        self.assertEqual(
            audit.metadata,
            {"scope": "record"},
        )

    def test_line_item_correction_rolls_back_when_audit_write_fails(self):
        record = BillingRecord.objects.create(
            bol_number="ROLLBACK-TEST",
            status="RECOMMENDATION_READY",
        )

        line_item = LineItem.objects.create(
            billing_record=record,
            line_number=1,
            product="87 Gas",
            gross_gallons=Decimal("7000.00"),
            net_gallons=Decimal("6965.00"),
        )

        with patch(
            "infrastructure.database."
            "django_audit_correction_repository."
            "AuditEvent.objects.create",
            side_effect=RuntimeError("audit write failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "audit write failed",
            ):
                self.correction_repository.apply_line_item_correction(
                    record_id=record.record_id,
                    line_item_id=line_item.line_item_id,
                    field_name="grossGallons",
                    old_value=7000.0,
                    new_value=6995,
                    reviewed_by="test-user",
                )

        record.refresh_from_db()
        line_item.refresh_from_db()

        self.assertEqual(
            line_item.gross_gallons,
            Decimal("7000.00"),
        )
        self.assertEqual(
            record.status,
            "RECOMMENDATION_READY",
        )

        self.assertFalse(
            AuditEvent.objects.filter(
                billing_record=record,
                line_item=line_item,
                field_name="grossGallons",
            ).exists()
        )


    def test_human_decision_rolls_back_when_status_update_fails(self):
        record = BillingRecord.objects.create(
            bol_number="DECISION-ROLLBACK-TEST",
            status="RECOMMENDATION_READY",
        )

        with patch(
            "infrastructure.database."
            "django_persistence_human_decision_repository."
            "BillingRecord.save",
            side_effect=RuntimeError("status write failed"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "status write failed",
            ):
                self.decision_repository.store_decision_and_update_status(
                    record_id=record.record_id,
                    decision="APPROVE",
                    previous_status="RECOMMENDATION_READY",
                    resulting_status="APPROVED",
                    decided_by="test-user",
                    reason="Rollback test.",
                )

        record.refresh_from_db()

        self.assertEqual(
            record.status,
            "RECOMMENDATION_READY",
        )

        self.assertFalse(
            HumanDecision.objects.filter(
                billing_record=record,
            ).exists()
        )

    def test_human_decision_links_current_recommendation_and_updates_status(
        self,
    ):
        record = BillingRecord.objects.create(
            bol_number="DECISION-TEST",
            status="RECOMMENDATION_PENDING",
        )

        recommendation = (
            self.recommendation_repository
            .store_revision_and_mark_ready(
                record.record_id,
                {
                    "recordId": str(record.record_id),
                    "recommendation": "APPROVE_RECOMMENDED",
                    "confidence": 0.93,
                    "modelVersion": "test-v1",
                    "rationale": "Human decision test.",
                    "mappedEntities": {},
                    "exceptionIndicators": [],
                },
            )
        )

        service = HumanDecisionService(
            billing_record_provider=self.billing_repository,
            workflow_service=self.workflow_service,
            billing_record_repository=self.billing_repository,
            decision_repository=self.decision_repository,
        )

        result = service.submit_decision(
            record_id=record.record_id,
            decision="APPROVE",
            decided_by="test-user",
            reason="Reviewed and accepted.",
        )

        record.refresh_from_db()

        decision = HumanDecision.objects.get(
            billing_record=record
        )

        self.assertEqual(record.status, "APPROVED")
        self.assertEqual(decision.decision, "APPROVE")
        self.assertEqual(
            decision.previous_status,
            "RECOMMENDATION_READY",
        )
        self.assertEqual(
            decision.resulting_status,
            "APPROVED",
        )
        self.assertEqual(decision.decided_by, "test-user")
        self.assertEqual(decision.feedback_status, "PENDING")

        self.assertEqual(
            decision.recommendation_id,
            recommendation.recommendation_id,
        )

        self.assertEqual(result["status"], "APPROVED")
