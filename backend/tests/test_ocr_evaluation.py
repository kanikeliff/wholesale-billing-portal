import copy
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.utils import timezone
from apps.billing.models import BillingRecord
from apps.persistence.models import Document, ExtractedField, OCRJob
from application.services.ocr_evaluation import score_manifest


class OCREvaluationTests(TestCase):
    def setUp(self):
        self.record = BillingRecord.objects.create(bol_number="HUMAN-CORRECTED", carrier="corrected")
        self.document = Document.objects.create(billing_record=self.record, original_filename="unit.pdf", checksum_sha256="a" * 64)
        OCRJob.objects.create(document=self.document, status="COMPLETED", started_at=timezone.now() - timedelta(seconds=10), completed_at=timezone.now())
        self.evidence = ExtractedField.objects.create(document=self.document, billing_record=self.record,
            field_name="bolNumber", normalized_value="00123", confidence="0.99")
        ExtractedField.objects.create(document=self.document, billing_record=self.record, field_name="contractLifting", normalized_value=None)
        self.manifest = {"schemaVersion": 1, "split": "unseen", "documents": [{"documentId": str(self.document.pk),
            "sourceSHA256": "a" * 64, "expected": {"fields": {"bolNumber": "00123", "contractLifting": None}}}]}

    def test_immutable_ocr_not_corrected_record_is_scored(self):
        result = score_manifest(self.manifest)
        self.assertEqual(result["fieldAccuracy"], 1)
        self.assertEqual(result["labeledFields"], 2)
        self.assertEqual(result["certainty"]["scoredFields"], 1)
        self.assertFalse(result["certainty"]["calibrated"])
        self.assertAlmostEqual(result["certainty"]["brierScore"], 0.0001)
        self.assertGreater(result["latency"]["medianProcessingSeconds"], 9)
        self.assertIn("not independently verified", result["holdoutCheck"])
        self.record.refresh_from_db(); self.assertEqual(self.record.bol_number, "HUMAN-CORRECTED")

    def test_baseline_comparison_preserves_sources_and_labels(self):
        baseline = score_manifest(self.manifest)
        self.evidence.normalized_value = "wrong"; self.evidence.save()
        final = score_manifest(self.manifest, baseline=baseline)
        self.assertEqual(final["comparison"]["accuracyDeltaPercentagePoints"], -50)
        changed = copy.deepcopy(self.manifest)
        changed["documents"][0]["expected"]["fields"]["bolNumber"] = "different labels"
        with self.assertRaisesRegex(ValueError, "identical"):
            score_manifest(changed, baseline=baseline)

    def test_duplicate_and_tuning_overlap_are_rejected(self):
        duplicated = copy.deepcopy(self.manifest); duplicated["documents"] *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            score_manifest(duplicated)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            score_manifest(self.manifest, tuning_manifest=self.manifest)

    def test_wrong_source_and_uncompleted_ocr_are_rejected(self):
        changed = copy.deepcopy(self.manifest); changed["documents"][0]["sourceSHA256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "checksum"):
            score_manifest(changed)
        OCRJob.objects.all().update(status="FAILED")
        with self.assertRaisesRegex(ValueError, "completed"):
            score_manifest(self.manifest)

    def test_leading_zeros_and_empty_labels_are_not_silently_changed(self):
        changed = copy.deepcopy(self.manifest)
        changed["documents"][0]["expected"]["fields"]["bolNumber"] = "123"
        self.assertEqual(score_manifest(changed)["fieldAccuracy"], .5)
        changed["documents"][0]["expected"] = {}
        with self.assertRaisesRegex(ValueError, "no labeled"):
            score_manifest(changed)

    def test_command_preserves_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, report = Path(directory) / "labels.json", Path(directory) / "report.json"
            manifest.write_text(json.dumps(self.manifest))
            call_command("score_ocr", manifest=str(manifest), output=str(report), stdout=StringIO())
            original = report.read_text()
            with self.assertRaises(CommandError):
                call_command("score_ocr", manifest=str(manifest), output=str(report))
            self.assertEqual(report.read_text(), original)
            self.assertEqual(report.stat().st_mode & 0o077, 0)

    def test_latest_failed_run_cannot_be_reported_as_a_completed_old_run(self):
        OCRJob.objects.create(document=self.document, status="FAILED")
        with self.assertRaisesRegex(ValueError, "not completed"):
            score_manifest(self.manifest)

    def test_numeric_line_labels_use_exact_decimal_comparison(self):
        from apps.billing.models import LineItem
        line = LineItem.objects.create(billing_record=self.record, line_number=1, net_gallons=999)
        field = ExtractedField.objects.create(document=self.document, billing_record=self.record, line_item=line,
                                               field_name="netGallons", normalized_value="100.00")
        labeled = copy.deepcopy(self.manifest)
        labeled["documents"][0]["expected"]["lineItems"] = [{"lineNumber": 1, "netGallons": 100}]
        self.assertEqual(score_manifest(labeled)["fieldAccuracy"], 1)
        field.normalized_value = "NaN"; field.save()
        with self.assertRaisesRegex(ValueError, "finite"):
            score_manifest(labeled)
