"""Secret-free operational checks; never migrate, infer, train or send feedback."""
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count
from apps.persistence.models import HumanDecision, OCRJob
from infrastructure.ocr.runtime_configuration import get_ocr_provider, ensure_live_worker_ready, read_runtime_config


class Command(BaseCommand):
    help = "Report backend dependencies, migrations and queues without external requests."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--require-live-ocr", action="store_true")
        parser.add_argument("--check-ocr-package", action="store_true")

    def handle(self, *args, **options):
        report = {"schemaVersion": 1, "database": {"ready": False}, "ocr": {}, "feedback": {}}
        try:
            connection.ensure_connection()
            executor = MigrationExecutor(connection)
            missing = len(executor.migration_plan(executor.loader.graph.leaf_nodes()))
            report["database"] = {"ready": missing == 0, "unappliedMigrations": missing}
            if missing == 0:
                report["ocr"]["jobsByStatus"] = dict(OCRJob.objects.order_by().values_list("status").annotate(total=Count("pk")))
                report["feedback"]["decisionsByStatus"] = dict(HumanDecision.objects.order_by().values_list("feedback_status").annotate(total=Count("pk")))
                queued = HumanDecision.objects.filter(feedback_metadata__has_key="payload")
                report["feedback"]["outboxByStatus"] = dict(queued.order_by().values_list("feedback_status").annotate(total=Count("pk")))
                report["feedback"]["historicalWithoutPayload"] = HumanDecision.objects.exclude(feedback_metadata__has_key="payload").count()
        except Exception:
            report["database"]["errorCode"] = "DATABASE_OR_MIGRATIONS_UNAVAILABLE"
        try:
            provider = get_ocr_provider()
            report["ocr"]["provider"] = provider
            ready = provider == "sample"
            if provider == "live":
                ensure_live_worker_ready()
                state = json.loads(Path(read_runtime_config()["workerState"]).read_text())
                report["ocr"]["includeConfidence"] = state.get("includeConfidence", False)
                report["ocr"]["budgetEnforced"] = state.get("budgetEnforced", True)
                ready = True
            if options["require_live_ocr"] and provider != "live":
                ready = False
                report["ocr"]["errorCode"] = "LIVE_OCR_REQUIRED"
            if options["check_ocr_package"]:
                from infrastructure.ocr.live_ocr_client import LiveOCRClient
                LiveOCRClient()  # validates installed 0.3.0 runtime and config; no generation
                report["ocr"]["packageVerified"] = True
            report["ocr"]["ready"] = ready
        except Exception:
            report["ocr"].update(ready=False, errorCode="OCR_RUNTIME_UNAVAILABLE")
        configured = (os.getenv("USE_MOCK_TEAM_A", "true").lower() == "false"
                      and bool(os.getenv("TEAM_A_BASE_URL")) and bool(os.getenv("TEAM_A_API_KEY")))
        report["feedback"].update(configured=configured, workerLiveness="not checked", remoteReceipt="not checked")
        report["sourceStorage"] = {"backend": settings.STORAGES.get("default", {}).get("BACKEND", "unknown"),
                                   "note": "Storage persistence and cross-process access require deployment verification."}
        report["ready"] = report["database"]["ready"] and report["ocr"].get("ready", False) and configured
        self.stdout.write(json.dumps(report, indent=2))
        if options["strict"] and not report["ready"]:
            raise CommandError("Backend preflight failed; inspect the reported check categories.")
