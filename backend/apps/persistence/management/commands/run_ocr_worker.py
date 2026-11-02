
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from application.services.ocr_job_worker import OCRJobWorker


class Command(BaseCommand):
    help = "Process pending OCR jobs using saved, SHA-256-matched sample extractions."

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

        from infrastructure.ocr.sample_package_ocr_client import SamplePackageOCRClient

        worker = OCRJobWorker(extractor=SamplePackageOCRClient().submit_document)

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
