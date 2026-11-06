import json
import os
from pathlib import Path
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from application.services.ocr_evaluation import score_manifest


class Command(BaseCommand):
    help = "Score immutable OCR fields against independent labels; no inference or training."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--baseline")
        parser.add_argument("--tuning-manifest")

    def handle(self, *args, **options):
        try:
            load = lambda name: json.loads(Path(options[name]).read_text()) if options[name] else None
            with transaction.atomic():
                report = score_manifest(load("manifest"), tuning_manifest=load("tuning_manifest"), baseline=load("baseline"))
            report["generatedAt"] = timezone.now().isoformat()
            output = Path(options["output"])
            if output.exists():
                raise ValueError("Output already exists; choose a new report path to preserve history.")
            with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                json.dump(report, stream, indent=2)
        except (ValueError, OSError, KeyError, TypeError, ObjectDoesNotExist, ValidationError) as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"Scored {report['labeledFields']} fields: {report['correctFields']} correct. Report: {output}")
