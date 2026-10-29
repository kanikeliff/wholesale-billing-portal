from core.enums.record_status import RecordStatus


class HumanDecisionService:

    DECISION_STATUS_MAP = {
        "APPROVE": RecordStatus.APPROVED.value,
        "REJECT": RecordStatus.REJECTED.value,
        "EXCEPTION": RecordStatus.EXCEPTION.value,
    }

    def __init__(
        self,
        billing_record_provider,
        workflow_service,
        billing_record_repository=None,
        decision_repository=None,
    ):
        self.billing_record_provider = billing_record_provider
        self.workflow_service = workflow_service
        self.billing_record_repository = billing_record_repository
        self.decision_repository = decision_repository

    def submit_decision(
        self,
        record_id,
        decision,
        *,
        decided_by=None,
        reason=None,
    ):
        record = self.billing_record_provider.get_by_id(record_id)

        if record is None:
            raise ValueError("Billing record not found.")

        normalized_decision = str(decision).upper()

        if normalized_decision not in self.DECISION_STATUS_MAP:
            raise ValueError(
                "Decision must be APPROVE, REJECT, or EXCEPTION."
            )

        current_status = record.get("status")
        target_status = self.DECISION_STATUS_MAP[
            normalized_decision
        ]

        self.workflow_service.validate_transition(
            current_status,
            target_status,
        )

        persisted_atomically = False

        if self.decision_repository is not None:
            atomic_method = getattr(
                self.decision_repository,
                "store_decision_and_update_status",
                None,
            )

            if atomic_method is not None:
                atomic_method(
                    record_id=record_id,
                    decision=normalized_decision,
                    previous_status=current_status,
                    resulting_status=target_status,
                    decided_by=decided_by,
                    reason=reason,
                )
                persisted_atomically = True
            else:
                self.decision_repository.store_decision(
                    record_id=record_id,
                    decision=normalized_decision,
                    previous_status=current_status,
                    resulting_status=target_status,
                    decided_by=decided_by,
                    reason=reason,
                )

        if (
            not persisted_atomically
            and self.billing_record_repository is not None
        ):
            self.billing_record_repository.update_status(
                record_id,
                target_status,
            )

        return {
            "recordId": record_id,
            "decision": normalized_decision,
            "previousStatus": current_status,
            "status": target_status,
            "decidedBy": decided_by,
            "reason": reason,
        }
