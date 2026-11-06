import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, OperationalError, InterfaceError
from application.services.feedback_delivery_service import FeedbackDeliveryService


class Command(BaseCommand):
    help = "Deliver queued reviewer feedback to Team A and retry temporary failures."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--interval", type=float, default=3)
        parser.add_argument("--decision-id")
        parser.add_argument("--retry-rejected", action="store_true",
                            help="Retry one rejected delivery after fixing its configuration.")

    def handle(self, *args, **options):
        if options["interval"] <= 0:
            raise CommandError("--interval must be positive.")
        if options["decision_id"] and not options["once"]:
            raise CommandError("--decision-id requires --once.")
        if options["retry_rejected"] and not (options["once"] and options["decision_id"]):
            raise CommandError("--retry-rejected requires --once --decision-id.")
        service = FeedbackDeliveryService()
        # Fail startup clearly for missing/mock configuration rather than falsely
        # reporting mock acknowledgments as delivered feedback.
        try:
            service.client = service._client()
        except RuntimeError as error:
            raise CommandError(str(error)) from None
        if options["retry_rejected"]:
            from django.db import transaction
            from apps.persistence.models import HumanDecision
            with transaction.atomic():
                decision = HumanDecision.objects.select_for_update().filter(
                    pk=options["decision_id"], feedback_status="FAILED",
                    feedback_metadata__has_key="payload",
                ).first()
                if decision is None:
                    raise CommandError("No failed queued delivery found for that decision.")
                metadata = dict(decision.feedback_metadata)
                metadata.update({"retryable": True, "nextAttemptAt": 0})
                decision.feedback_metadata = metadata
                decision.save(update_fields=["feedback_metadata"])
        self.stdout.write("Feedback worker started.")
        while True:
            try:
                close_old_connections()
                result = service.process_next(options["decision_id"])
            except (OperationalError, InterfaceError):
                # Delivery may already have reached Team A. Leave the lease and
                # immutable payload intact; recovery will safely resend it.
                if options["once"]:
                    raise CommandError("Feedback database temporarily unavailable.") from None
                self.stderr.write("Feedback database temporarily unavailable; retrying.")
                close_old_connections()
                time.sleep(options["interval"])
                continue
            except KeyboardInterrupt:
                return
            if result:
                self.stdout.write(f"Feedback {result['humanDecisionId']}: {result['status']}")
            if options["once"]:
                return
            if result is None:
                time.sleep(options["interval"])
