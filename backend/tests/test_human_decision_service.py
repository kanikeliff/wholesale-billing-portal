from django.test import SimpleTestCase

from application.services.human_decision_service import (
    HumanDecisionService,
)
from application.services.workflow_service import WorkflowService


class FakeBillingRecordProvider:

    def __init__(self, record):
        self.record = record

    def get_by_id(self, record_id):
        return self.record


class FakeBillingRecordRepository:

    def __init__(self):
        self.status_updates = []

    def update_status(self, record_id, status):
        self.status_updates.append(
            {
                "recordId": record_id,
                "status": status,
            }
        )


class FakeDecisionRepository:

    def __init__(self):
        self.decisions = []

    def store_decision(self, **kwargs):
        self.decisions.append(kwargs)



class FakeAtomicDecisionRepository:

    def __init__(self):
        self.atomic_calls = []

    def store_decision_and_update_status(self, **kwargs):
        self.atomic_calls.append(kwargs)


def build_record(status="RECOMMENDATION_READY"):
    return {
        "recordId": "rec_001",
        "status": status,
    }


class HumanDecisionServiceTests(SimpleTestCase):

    def build_service(
        self,
        record,
        billing_repository=None,
        decision_repository=None,
    ):
        return HumanDecisionService(
            billing_record_provider=FakeBillingRecordProvider(
                record
            ),
            workflow_service=WorkflowService(),
            billing_record_repository=billing_repository,
            decision_repository=decision_repository,
        )

    def test_approve_ready_record(self):
        service = self.build_service(build_record())

        result = service.submit_decision(
            "rec_001",
            "APPROVE",
            decided_by="user_001",
        )

        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["decision"], "APPROVE")

    def test_reject_ready_record(self):
        service = self.build_service(build_record())

        result = service.submit_decision(
            "rec_001",
            "REJECT",
        )

        self.assertEqual(result["status"], "REJECTED")

    def test_exception_ready_record(self):
        service = self.build_service(build_record())

        result = service.submit_decision(
            "rec_001",
            "EXCEPTION",
        )

        self.assertEqual(result["status"], "EXCEPTION")

    def test_invalid_decision_is_rejected(self):
        service = self.build_service(build_record())

        with self.assertRaisesRegex(
            ValueError,
            "Decision must be",
        ):
            service.submit_decision(
                "rec_001",
                "DELETE",
            )

    def test_invalid_workflow_is_rejected(self):
        service = self.build_service(
            build_record(status="UPLOADED")
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid workflow transition",
        ):
            service.submit_decision(
                "rec_001",
                "APPROVE",
            )

    def test_unknown_record_is_rejected(self):
        service = self.build_service(None)

        with self.assertRaisesMessage(
            ValueError,
            "Billing record not found.",
        ):
            service.submit_decision(
                "missing",
                "APPROVE",
            )

    def test_decision_is_persisted(self):
        decision_repository = FakeDecisionRepository()
        billing_repository = FakeBillingRecordRepository()

        service = self.build_service(
            build_record(),
            billing_repository=billing_repository,
            decision_repository=decision_repository,
        )

        service.submit_decision(
            "rec_001",
            "APPROVE",
            decided_by="user_001",
            reason="Reviewed and verified.",
        )

        self.assertEqual(
            len(decision_repository.decisions),
            1,
        )

        self.assertEqual(
            billing_repository.status_updates[0]["status"],
            "APPROVED",
        )


    def test_decision_uses_atomic_persistence_when_available(self):
        decision_repository = FakeAtomicDecisionRepository()
        billing_repository = FakeBillingRecordRepository()

        service = self.build_service(
            build_record(),
            billing_repository=billing_repository,
            decision_repository=decision_repository,
        )

        service.submit_decision(
            "rec_001",
            "APPROVE",
            decided_by="user_001",
            reason="Reviewed and verified.",
        )

        self.assertEqual(
            len(decision_repository.atomic_calls),
            1,
        )

        self.assertEqual(
            decision_repository.atomic_calls[0]["resulting_status"],
            "APPROVED",
        )

        self.assertEqual(
            billing_repository.status_updates,
            [],
        )
