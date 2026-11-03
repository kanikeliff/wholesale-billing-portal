import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from infrastructure.ocr.live_ocr_client import InferenceBudget, LiveOCRError, count_input_tokens
from infrastructure.ocr.ocr_factory import build_ocr_extractor
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter
from infrastructure.ocr.review_flags import apply_review_flags


class OCRProviderSelectionTests(SimpleTestCase):
    @patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={})
    @patch.dict(os.environ, {}, clear=True)
    def test_default_is_sample_without_model_key(self, config):
        extractor = build_ocr_extractor()
        self.assertEqual(type(extractor.__self__).__name__, "SamplePackageOCRClient")

    @patch.dict(os.environ, {"OCR_PROVIDER": "typo"}, clear=True)
    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "OCR_PROVIDER"):
            build_ocr_extractor()

    @patch.dict(os.environ, {"OCR_PROVIDER": "live"}, clear=True)
    @patch("infrastructure.ocr.runtime_configuration.read_runtime_config", return_value={})
    def test_live_requires_a_targeted_single_job(self, config):
        with self.assertRaisesRegex(CommandError, "--once --job-id"):
            call_command("run_ocr_worker")

    @patch.dict(os.environ, {"OCR_PROVIDER": "live"}, clear=True)
    @patch("infrastructure.ocr.live_ocr_client.LiveOCRClient", side_effect=LiveOCRError("OCR_PACKAGE_MISMATCH", "not ready"))
    def test_live_failure_never_falls_back_to_sample(self, client):
        with self.assertRaises(LiveOCRError):
            build_ocr_extractor()


class OCRBudgetTests(SimpleTestCase):
    def payload(self):
        return {"model": "gpt-6.1-sol", "max_output_tokens": 8192}

    def test_three_call_limit_is_cumulative(self):
        budget = InferenceBudget()
        for _ in range(3):
            budget.reserve(self.payload(), 1000)
        with self.assertRaisesRegex(LiveOCRError, "request limit"):
            budget.reserve(self.payload(), 1000)
        self.assertLessEqual(budget.reserved, 4)

    def test_dollar_limit_blocks_before_request(self):
        budget = InferenceBudget("0.20")
        with self.assertRaisesRegex(LiveOCRError, "dollar budget"):
            budget.reserve(self.payload(), 20000)
        self.assertEqual(budget.calls, [])
        self.assertEqual(budget.reserved, 0)

    def test_invalid_model_tier_and_budget_fail_closed(self):
        for payload in ({**self.payload(), "model": "other"},
                        {**self.payload(), "service_tier": "priority"},
                        {**self.payload(), "tools": [{"type": "web_search"}]}):
            with self.assertRaises(LiveOCRError):
                InferenceBudget().reserve(payload, 1000)
        for amount in ("-1", "NaN", "Infinity", "0"):
            with self.assertRaises(ValueError):
                InferenceBudget(amount)

    def test_an_explicit_budget_can_exceed_the_old_smoke_test_limit(self):
        self.assertEqual(InferenceBudget("10").limit, 10)

    def test_shared_budget_survives_new_worker_instances(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "budget.json"
            first = InferenceBudget("4", ledger_path=ledger)
            first.reserve(self.payload(), 1000)
            used = first.reserved
            second = InferenceBudget("4", ledger_path=ledger)
            self.assertEqual(second.reserved, used)
            second.reserve(self.payload(), 1000)
            self.assertEqual(first.remaining(), first.limit - 2 * used)

    def test_shared_budget_cannot_be_reset_or_overspent(self):
        from pathlib import Path
        import tempfile, json
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "budget.json"
            ledger.write_text(json.dumps({"limitUSD": "4", "reservedUSD": "3.90", "calls": []}))
            with self.assertRaises(LiveOCRError):
                InferenceBudget("4", ledger_path=ledger).reserve(self.payload(), 1000)
            self.assertEqual(json.loads(ledger.read_text())["reservedUSD"], "3.90")
            with self.assertRaises(LiveOCRError):
                InferenceBudget("3", ledger_path=ledger)

    def test_disabled_dollar_cap_preserves_history_and_generation_limit(self):
        from pathlib import Path
        import tempfile, json
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "budget.json"
            previous = {"reservationId": "prior-test", "reservedUSD": "4", "status": "RECEIVED"}
            ledger.write_text(json.dumps({"limitUSD": "4", "reservedUSD": "4", "calls": [previous]}))
            budget = InferenceBudget("4", ledger_path=ledger, enforce_limit=False)
            for _ in range(3):
                budget.reserve(self.payload(), 1000)
            with self.assertRaisesRegex(LiveOCRError, "request limit"):
                budget.reserve(self.payload(), 1000)
            stored = json.loads(ledger.read_text())
            self.assertGreater(budget.reserved, 4)
            self.assertEqual(stored["calls"][0], previous)
            self.assertEqual(len(stored["calls"]), 4)
            reloaded = InferenceBudget("4", ledger_path=ledger, enforce_limit=False)
            self.assertEqual(reloaded.reserved, budget.reserved)

    def test_disabled_cap_keeps_model_tier_and_output_restrictions(self):
        for payload in ({**self.payload(), "model": "other"},
                        {**self.payload(), "service_tier": "priority"},
                        {**self.payload(), "max_output_tokens": 8193}):
            with self.assertRaises(LiveOCRError):
                InferenceBudget(enforce_limit=False).reserve(payload, 1000)

    @patch("infrastructure.ocr.live_ocr_client.requests.post")
    def test_token_preflight_failure_does_not_echo_provider_body(self, post):
        post.return_value.status_code = 401
        with self.assertRaisesRegex(LiveOCRError, "HTTP 401"):
            count_input_tokens(self.payload(), api_key="unit-test-unused", timeout=30)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])


class OCRReviewEvidenceTests(SimpleTestCase):
    def test_review_flag_does_not_change_value_or_confidence(self):
        canonical = BolLabAdapter().adapt({"carrier": "printed carrier", "products": []})
        flags = [{"code": "LOW_CONFIDENCE", "field": "carrier"}]
        result = apply_review_flags(canonical, flags)
        carrier = result["fields"]["carrier"]
        self.assertEqual(carrier["rawValue"], "printed carrier")
        self.assertEqual(carrier["normalizedValue"], "printed carrier")
        self.assertIsNone(carrier["confidence"])
        self.assertEqual(carrier["quality"], "LOW_CONFIDENCE")
        self.assertEqual(carrier["reviewEvidence"], flags)

    def test_missing_state_and_other_lines_are_preserved(self):
        canonical = BolLabAdapter().adapt({"products": [{"product": "one"}, {"product": "two"}]})
        apply_review_flags(canonical, [
            {"code": "LOW_CONFIDENCE", "field": "e3StockId", "lineNumber": 1},
            {"code": "LOW_CONFIDENCE", "field": "product", "lineNumber": 2},
        ])
        self.assertTrue(canonical["lineItems"][0]["e3StockId"]["unresolved"])
        self.assertNotIn("quality", canonical["lineItems"][0]["product"])
        self.assertEqual(canonical["lineItems"][1]["product"]["quality"], "LOW_CONFIDENCE")
