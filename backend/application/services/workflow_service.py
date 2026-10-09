from core.enums.record_status import RecordStatus


class WorkflowService:

    ALLOWED_TRANSITIONS = {

        RecordStatus.UPLOADED: {
            RecordStatus.OCR_PROCESSING,
            RecordStatus.EXCEPTION,
        },

        RecordStatus.OCR_PROCESSING: {
            RecordStatus.OCR_COMPLETE,
            RecordStatus.NEEDS_REVIEW,
            RecordStatus.EXCEPTION,
        },

        RecordStatus.OCR_COMPLETE: {
            RecordStatus.NEEDS_REVIEW,
            RecordStatus.RECOMMENDATION_PENDING,
        },

        RecordStatus.NEEDS_REVIEW: {
            RecordStatus.RECOMMENDATION_PENDING,
            RecordStatus.REJECTED,
            RecordStatus.EXCEPTION,
        },

        RecordStatus.RECOMMENDATION_PENDING: {
            RecordStatus.RECOMMENDATION_READY,
            RecordStatus.EXCEPTION,
        },

        RecordStatus.RECOMMENDATION_READY: {
            RecordStatus.APPROVED,
            RecordStatus.REJECTED,
            RecordStatus.NEEDS_REVIEW,
            RecordStatus.EXCEPTION,
        },
    }

    def can_transition(self, current_status, new_status):

        current = RecordStatus(current_status)
        new = RecordStatus(new_status)

        allowed = self.ALLOWED_TRANSITIONS.get(
            current,
            set()
        )

        return new in allowed

    def validate_transition(
        self,
        current_status,
        new_status
    ):

        if not self.can_transition(
            current_status,
            new_status
        ):
            raise ValueError(
                f"Invalid workflow transition: "
                f"{current_status} -> {new_status}"
            )

        return True