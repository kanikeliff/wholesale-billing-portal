"""Non-secret local OCR service routing; credentials stay outside the repository."""
import json
import os
from decimal import Decimal
from pathlib import Path


class OCRRuntimeUnavailable(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def runtime_config_path():
    return Path(os.getenv("OCR_RUNTIME_CONFIG", f"/private/tmp/mirabito-ocr-runtime-{os.getuid()}/config.json"))


def read_runtime_config():
    path = runtime_config_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, OSError):
        raise OCRRuntimeUnavailable("OCR_CONFIGURATION_ERROR", "OCR service configuration is unavailable.") from None


def get_ocr_provider():
    provider = os.getenv("OCR_PROVIDER") or read_runtime_config().get("provider", "sample")
    provider = provider.strip().lower()
    if provider not in ("sample", "live"):
        raise ValueError("OCR_PROVIDER must be sample or live.")
    return provider


def read_private_key(path):
    path = Path(path)
    info = path.stat()
    if not path.is_file() or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise OCRRuntimeUnavailable("OCR_CONFIGURATION_ERROR", "OCR credentials must be private to the worker owner.")
    value = path.read_text().strip()
    if not value:
        raise OCRRuntimeUnavailable("OCR_CONFIGURATION_ERROR", "OCR credentials are missing.")
    return value


def ensure_live_worker_ready():
    config = read_runtime_config()
    try:
        state = json.loads(Path(config["workerState"]).read_text())
        os.kill(int(state["pid"]), 0)
        if state.get("provider") != "live":
            raise ValueError
        ledger = json.loads(Path(config["budgetLedger"]).read_text())
        remaining = Decimal(str(ledger["limitUSD"])) - Decimal(str(ledger["reservedUSD"]))
    except (KeyError, ValueError, OSError, TypeError):
        raise OCRRuntimeUnavailable("OCR_WORKER_UNAVAILABLE", "OCR is temporarily unavailable. Your file has not been uploaded; restart the OCR service and try again.") from None
    if remaining < Decimal("0.90"):
        raise OCRRuntimeUnavailable("OCR_BUDGET_EXHAUSTED", "The approved OCR test budget is too low for another document. No new inference was started.")


def write_worker_state(provider):
    config = read_runtime_config()
    if provider == "live" and config.get("workerState"):
        path = Path(config["workerState"])
        path.write_text(json.dumps({"pid": os.getpid(), "provider": provider}))
        os.chmod(path, 0o600)
