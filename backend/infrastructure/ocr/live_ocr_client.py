"""Pinned three-stage OCR with reservation tracking and an optional dollar cap."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
import threading
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import requests


SOURCE_COMMIT = "fd02fdd3420142e21a9270c9679f137c50e7f6b1"
SOURCE_ARCHIVE_SHA256 = "10fe42b1aa87e8e515a52a7062fdc2055b08462ded460357a5e9e33d1e46a8b1"
_transport_lock = threading.Lock()


class LiveOCRError(RuntimeError):
    retryable = False

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def count_input_tokens(payload, *, api_key, timeout):
    """Count the actual multimodal request before allowing generation."""
    count_payload = {key: payload[key] for key in ("model", "input", "text") if key in payload}
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses/input_tokens",
            json=count_payload, headers={"Authorization": "Bearer " + api_key},
            timeout=min(timeout, 60), allow_redirects=False,
        )
        if response.status_code != 200:
            raise LiveOCRError("OCR_BUDGET_PREFLIGHT_FAILED", f"Token-count preflight returned HTTP {response.status_code}; no generation sent.")
        count = response.json().get("input_tokens")
    except (requests.RequestException, ValueError, AttributeError):
        raise LiveOCRError("OCR_BUDGET_PREFLIGHT_FAILED", "Token-count preflight failed; no generation sent.") from None
    if type(count) is not int or count < 0:
        raise LiveOCRError("OCR_BUDGET_PREFLIGHT_FAILED", "Token-count response is invalid; no generation sent.")
    return count


class InferenceBudget:
    # Conservative reservation rates above standard pricing, including long
    # context/cache writes. Recheck https://developers.openai.com/api/docs/models/gpt-6.1-sol
    # before expanding this bounded integration test to another model/tier.
    INPUT_USD_PER_MILLION = Decimal("20")
    OUTPUT_USD_PER_MILLION = Decimal("15")

    def __init__(self, usd="4", max_calls=3, ledger_path=None, *, enforce_limit=True):
        if type(enforce_limit) is not bool:
            raise ValueError("Budget enforcement must be a boolean.")
        self.enforce_limit = enforce_limit
        self.limit = Decimal(str(usd))
        if not self.limit.is_finite() or self.limit <= 0 or type(max_calls) is not int or not 1 <= max_calls <= 3:
            raise ValueError("Live OCR requires a positive budget threshold and at most three generation requests.")
        self.max_calls = max_calls
        self.reserved = Decimal("0")
        self.calls = []
        self.ledger_path = Path(ledger_path) if ledger_path else None
        if self.ledger_path:
            with self._locked_state() as state:
                self.reserved = Decimal(state["reservedUSD"])

    @contextmanager
    def _locked_state(self):
        import fcntl
        lock = self.ledger_path.with_suffix(".lock")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, "r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            state = json.loads(self.ledger_path.read_text()) if self.ledger_path.exists() else {
                "limitUSD": str(self.limit), "reservedUSD": "0", "calls": [],
            }
            if self.enforce_limit and Decimal(state["limitUSD"]) != self.limit:
                raise LiveOCRError("OCR_BUDGET_LIMIT", "Shared OCR budget limits cannot be reset by restarting a worker.")
            yield state
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", dir=self.ledger_path.parent, delete=False) as output:
                    temporary = Path(output.name)
                    os.chmod(temporary, 0o600)
                    json.dump(state, output)
                os.replace(temporary, self.ledger_path)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()

    def remaining(self):
        if self.ledger_path:
            with self._locked_state() as state:
                self.reserved = Decimal(state["reservedUSD"])
        return self.limit - self.reserved

    def finish(self, call):
        if self.ledger_path:
            with self._locked_state() as state:
                for index, previous in enumerate(state["calls"]):
                    if previous.get("reservationId") == call["reservationId"]:
                        state["calls"][index] = dict(call)
                        break

    def reserve(self, payload, input_tokens):
        output = payload.get("max_output_tokens")
        if (payload.get("model") != "gpt-6.1-sol" or payload.get("tools")
                or payload.get("service_tier") not in (None, "default")
                or type(output) is not int or not 1 <= output <= 8192):
            raise LiveOCRError("OCR_BUDGET_LIMIT", "Request is outside approved model, tier, tools or output limits.")
        if len(self.calls) >= self.max_calls:
            raise LiveOCRError("OCR_BUDGET_LIMIT", "Generation request limit reached.")
        reservation = (Decimal(input_tokens + 4096) * self.INPUT_USD_PER_MILLION
                       + Decimal(output) * self.OUTPUT_USD_PER_MILLION) / 1_000_000
        call = {"stage": payload.get("text", {}).get("format", {}).get("name"),
                "countedInputTokens": input_tokens, "reservedUSD": str(reservation), "status": "STARTED",
                "reservationId": str(uuid4())}
        if self.ledger_path:
            with self._locked_state() as state:
                self.reserved = Decimal(state["reservedUSD"])
                if self.enforce_limit and self.reserved + reservation > self.limit:
                    raise LiveOCRError("OCR_BUDGET_LIMIT", "Request reservation would exceed the approved dollar budget.")
                self.reserved += reservation
                state["reservedUSD"] = str(self.reserved)
                state["calls"].append(dict(call))
        else:
            if self.enforce_limit and self.reserved + reservation > self.limit:
                raise LiveOCRError("OCR_BUDGET_LIMIT", "Request reservation would exceed the approved dollar budget.")
            self.reserved += reservation
        self.calls.append(call)
        return call


class LiveOCRClient:
    def __init__(self):
        import mirabito_ocr
        from mirabito_ocr.config import Settings
        if importlib.metadata.version("mirabito-ocr") != "0.2.0":
            raise LiveOCRError("OCR_PACKAGE_MISMATCH", "Install the verified OCR handoff version.")
        manifest = json.loads(Path(__file__).with_name("live_package_manifest.json").read_text())
        package_root = Path(mirabito_ocr.__file__).parent
        for name, checksum in manifest.items():
            path = package_root / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                raise LiveOCRError("OCR_PACKAGE_MISMATCH", "Installed OCR source does not match the pinned handoff.")
        from .runtime_configuration import read_runtime_config, read_private_key, is_budget_enforced
        config = read_runtime_config()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key and config.get("keyFile"):
            api_key = read_private_key(config["keyFile"])
        self.settings = Settings(
            api_key=api_key or "", model=os.getenv("OCR_OPENAI_MODEL", "gpt-6.1-sol"),
            max_output_tokens=int(os.getenv("OCR_MAX_OUTPUT_TOKENS", "8192")),
            timeout_seconds=float(os.getenv("OCR_API_TIMEOUT_SECONDS", "240")),
            max_pages=int(os.getenv("OCR_MAX_PAGES", "1")),
        )
        if self.settings.model != "gpt-6.1-sol" or self.settings.max_output_tokens > 8192:
            raise LiveOCRError("OCR_BUDGET_LIMIT", "Use the approved gpt-6.1-sol model and at most 8192 output tokens.")
        self.budget = InferenceBudget(
            os.getenv("OCR_MAX_COST_USD", "4"), int(os.getenv("OCR_MAX_API_CALLS", "3")),
            ledger_path=os.getenv("OCR_BUDGET_LEDGER") or config.get("budgetLedger"),
            enforce_limit=is_budget_enforced(),
        )

    def submit_document(self, *, document_id, file_bytes, filename):
        from mirabito_ocr import client, verification
        from mirabito_ocr.pipeline import GPTBolPipeline
        from mirabito_ocr.transport import post_response
        from mirabito_ocr.errors import ExtractionError
        run_id = str(uuid4())
        checkpoint_parent = Path(tempfile.mkdtemp(prefix="mirabito-ocr-private-"))
        os.chmod(checkpoint_parent, 0o700)

        def guarded(payload, *, api_key, timeout):
            # Explicit standard tier avoids account-level priority defaults.
            payload = {**payload, "service_tier": "default"}
            if len(self.budget.calls) >= self.budget.max_calls:
                raise LiveOCRError("OCR_BUDGET_LIMIT", "Generation request limit reached.")
            try:
                tokens = count_input_tokens(payload, api_key=api_key, timeout=timeout)
                call = self.budget.reserve(payload, tokens)
            except LiveOCRError as error:
                raise ExtractionError(error.code, str(error), retryable=False) from None
            try:
                response, request_id = post_response(payload, api_key=api_key, timeout=timeout)
                call.update(status="RECEIVED", responseId=response.get("id"), requestId=request_id, usage=response.get("usage"))
                return response, request_id
            except Exception:
                call["status"] = "FAILED"
                raise
            finally:
                self.budget.finish(call)

        with _transport_lock, patch.object(client, "post_response", guarded), patch.object(verification, "post_response", guarded):
            self.budget.calls = []  # Three requests per document; dollars remain shared.
            result = GPTBolPipeline(self.settings).extract_bytes(
                file_bytes, filename=filename, document_id=document_id,
                checkpoint_dir=checkpoint_parent / "stages",
            )
        result.setdefault("metadata", {})["liveOCR"] = {
            "provider": "live", "sourceCommit": SOURCE_COMMIT,
            "sourceArchiveSha256": SOURCE_ARCHIVE_SHA256, "runId": run_id,
            "applicationCacheUsed": False,
            "budgetEnforced": self.budget.enforce_limit,
            "budgetUSD": str(self.budget.limit) if self.budget.enforce_limit else None,
            "reservedUSD": str(self.budget.reserved), "requests": self.budget.calls,
            "attemptReservedUSD": str(sum((Decimal(call["reservedUSD"]) for call in self.budget.calls), Decimal("0"))),
        }
        return result
