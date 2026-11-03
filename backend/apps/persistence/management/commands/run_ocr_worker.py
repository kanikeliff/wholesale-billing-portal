
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from application.services.ocr_job_worker import OCRJobWorker


class Command(BaseCommand):
    help = "Process OCR jobs with OCR_PROVIDER=sample (default) or live."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one OCR job and exit.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=3.0,
            help="Seconds between polls when no job is ready.",
        )

        parser.add_argument(
            "--job-id",
            type=str,
            default=None,
            help="Process only the specified OCR job.",
        )

    def handle(self, *args, **options):
        if options["interval"] <= 0:
            raise CommandError("--interval must be positive.")

        if options["job_id"] and not options["once"]:
            raise CommandError("--job-id requires --once.")

        from infrastructure.ocr.runtime_configuration import get_ocr_provider, read_runtime_config, write_worker_state
        provider = get_ocr_provider()
        if provider == "live" and not (options["once"] and options["job_id"]):
            if not read_runtime_config().get("budgetLedger"):
                raise CommandError("Live OCR requires a shared budget ledger or --once --job-id.")

        from infrastructure.ocr.ocr_factory import build_ocr_extractor
        worker = OCRJobWorker(extractor=build_ocr_extractor(), provider=provider)
        write_worker_state(provider)

        self.stdout.write("OCR worker started.")

        while True:
            close_old_connections()

            try:
                result = worker.process_next_job(
                    job_id=options["job_id"]
                )

                if result is not None:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"OCR completed for record {result['recordId']}"
                        )
                    )

            except Exception as exc:
                self.stderr.write(
                    f"OCR processing error: {type(exc).__name__}: {exc}"
                )

            finally:
                close_old_connections()

            if options["once"]:
                break

            time.sleep(options["interval"])
