"""Configure local live OCR without writing credentials into the repository."""
import argparse
import getpass
import json
import os
from decimal import Decimal
from pathlib import Path
import sys


def private_write(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(content)


def configure(key_file=None, seed_report=None):
    root = Path(f"/private/tmp/mirabito-ocr-runtime-{os.getuid()}")
    if root.is_symlink():
        raise SystemExit("Refusing a symlink as the OCR runtime directory.")
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    if key_file:
        source = Path(key_file)
        if source.stat().st_mode & 0o077:
            raise SystemExit("The input key file must be private.")
        key = source.read_text().strip()
    else:
        if not sys.stdin.isatty():
            raise SystemExit("Enter the OCR key in your own terminal.")
        key = getpass.getpass("OpenAI OCR key (hidden): ").strip()
    if not key or any(character.isspace() for character in key):
        raise SystemExit("Invalid key format; configuration was not activated.")
    ledger = root / "budget.json"
    if not ledger.exists():
        previous = json.loads(Path(seed_report).read_text()) if seed_report else {}
        used = Decimal(str(previous.get("reservedUSD", "0")))
        if not used.is_finite() or used < 0:
            raise SystemExit("Invalid previous budget reservation.")
        private_write(ledger, json.dumps({"limitUSD": "4", "reservedUSD": str(used),
            "calls": previous.get("generationRequests", []), "seedRecordId": previous.get("recordId")}))
    state = json.loads(ledger.read_text())
    if Decimal(state["limitUSD"]) != 4:
        raise SystemExit("Refusing to change an existing approved OCR budget.")
    private_write(root / "api-key", key)
    config = {"provider": "live", "keyFile": str(root / "api-key"),
              "budgetLedger": str(ledger), "workerState": str(root / "worker.json")}
    private_write(root / "config.json", json.dumps(config))
    if key_file and Path(key_file) != root / "api-key":
        Path(key_file).unlink()
    print("Live OCR configured outside the repository; credentials were not displayed.")
    print("Tracked reservations so far: $" + state["reservedUSD"])
    print("The $4 test cap is disabled by default. Set OCR_ENFORCE_BUDGET=true in both web and worker environments to enforce it.")
    print("Start the normal run_ocr_worker command; new uploads will use live OCR.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-file")
    parser.add_argument("--seed-report")
    arguments = parser.parse_args()
    configure(arguments.key_file, arguments.seed_report)
