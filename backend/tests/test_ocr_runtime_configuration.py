import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import SimpleTestCase

from infrastructure.ocr.runtime_configuration import (
    OCRRuntimeUnavailable, ensure_live_worker_ready, get_ocr_provider, read_private_key,
)


class OCRRuntimeConfigurationTests(SimpleTestCase):
    @patch.dict(os.environ, {"OCR_PROVIDER": "sample"})
    @patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={"provider": "live"})
    def test_explicit_sample_mode_overrides_local_live_configuration(self, config):
        self.assertEqual(get_ocr_provider(), "sample")

    def test_worker_readiness_uses_persistent_remaining_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = Path(folder) / "worker.json"
            ledger = Path(folder) / "budget.json"
            worker.write_text(json.dumps({"pid": os.getpid(), "provider": "live"}))
            ledger.write_text(json.dumps({"limitUSD": "4", "reservedUSD": "1.689"}))
            with patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={
                "workerState": str(worker), "budgetLedger": str(ledger),
            }):
                ensure_live_worker_ready()
                ledger.write_text(json.dumps({"limitUSD": "4", "reservedUSD": "3.9"}))
                with self.assertRaises(OCRRuntimeUnavailable) as error:
                    ensure_live_worker_ready()
                self.assertEqual(error.exception.code, "OCR_BUDGET_EXHAUSTED")

    @patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={})
    def test_missing_worker_is_reported_before_upload(self, config):
        with self.assertRaises(OCRRuntimeUnavailable) as error:
            ensure_live_worker_ready()
        self.assertEqual(error.exception.code, "OCR_WORKER_UNAVAILABLE")

    def test_credential_file_must_be_private(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "key"
            path.write_text("unit-test-placeholder")
            path.chmod(0o644)
            with self.assertRaises(OCRRuntimeUnavailable):
                read_private_key(path)
            path.chmod(0o600)
            self.assertEqual(read_private_key(path), "unit-test-placeholder")
