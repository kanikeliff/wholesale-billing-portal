# OCR provider selection

`OCR_PROVIDER=sample` is the default. It loads saved extraction JSON only for
manifest-matched PDFs and needs no model key or live OCR package.

`OCR_PROVIDER=live` uses the standalone handoff pinned to commit
`fd02fdd3420142e21a9270c9679f137c50e7f6b1`, package `mirabito-ocr` 0.2.0.
The approved source TAR SHA-256 is
`10fe42b1aa87e8e515a52a7062fdc2055b08462ded460357a5e9e33d1e46a8b1`.
Install that verified source package into the worker's Python environment;
the package is not assumed to be available from a public package registry.
Installed runtime file hashes must match `live_package_manifest.json`.

Supply `OPENAI_API_KEY` through the worker environment using hidden terminal
input or a secret manager. Do not put OCR credentials in repository files.
Team A's existing environment loader/configuration is independent and unchanged.

Worker variables (not read from the Team A `.env` loader):

| Variable | Default / allowed test setting |
| --- | --- |
| `OCR_PROVIDER` | `sample` or explicitly `live` |
| `OCR_OPENAI_MODEL` | `gpt-6.1-sol` |
| `OCR_MAX_OUTPUT_TOKENS` | `8192`, cannot exceed 8192 in live mode |
| `OCR_API_TIMEOUT_SECONDS` | `240` per provider request |
| `OCR_MAX_PAGES` | `1` |
| `OCR_MAX_COST_USD` | `4`, positive and cannot exceed 4 |
| `OCR_MAX_API_CALLS` | `3`, integer from 1 to 3 |

For normal browser uploads, configure the local service once:

```sh
python backend/tools/configure_live_ocr.py --seed-report /absolute/path/to/prior-ocr-result.json
python backend/manage.py run_ocr_worker --settings=config.settings_database --interval 1
```

The configuration helper asks for the key with hidden input and keeps it in an
owner-only directory outside the repository. It also creates a persistent shared
budget ledger. When a previous test already consumed budget, supply its report;
existing ledgers are preserved and never reset on worker restart. The web upload
endpoint and worker read the same local configuration without changing Team A's
environment loader. Explicit `OCR_PROVIDER=sample` remains available for offline
regression tests.

Uploads record their requested provider in existing `OCRJob.raw_result` metadata.
Workers filter by provider before claiming jobs, preventing sample workers from
consuming live uploads. Live uploads get one attempt. A missing worker or low
remaining budget returns HTTP 503 before creating a billing record; frontend
errors use the existing error styles. Failed records expose the public OCR error
instead of showing unexplained empty review fields.

With a configured shared ledger, the worker can remain running and process normal
uploads within the same approved $4 total. Without a shared ledger, ad hoc live
execution still requires `--once --job-id`:

```sh
OCR_PROVIDER=live python backend/manage.py run_ocr_worker \
  --settings=config.settings_database --once --job-id RECORD_UPLOAD_JOB_UUID
```

Stop legacy workers loaded before provider-aware routing before enabling the
live service. Current provider-aware workers cannot claim another provider's
jobs. No schema change or automatic sample fallback occurs.

The live client invokes extraction, grounding and blind rereading. Before each
generation request it counts the multimodal input using the provider token-count
endpoint. It reserves `(input_tokens + 4096) * $20/M + max_output_tokens * $15/M`,
conservative rates above the standard model rates checked on 2026-11-02. Only
the standard tier and the approved model/output limits are allowed; tools are
disallowed. Cumulative reservations and a generation-call limit are enforced
before sending requests, including failed/ambiguous submissions. The configured shared budget survives worker restarts and coordinates processes
with a file lock. It includes seeded prior reservations, but does not cover
unrelated activity on the provider account.
Reservations are not invoices or exact billing totals. Recheck published pricing
before changing the supported model/settings.

The input-token preflight does not generate a model completion. If it cannot
return a valid count, generation is blocked. Timeouts do not release a reserved
amount and do not authorize replay. The socket timeout is not a whole-job deadline.

The successful job retains the full provider result, fresh response/request IDs,
usage, document source hash, pinned source identity, and budget ledger. Private
stage checkpoints are kept in an owner-only system temporary directory. They
contain business evidence, no API headers, and are not a result cache.

Normalization, stable database line-item IDs, source document storage and
frontend structure are unchanged. Existing field metadata stores applicable
review evidence and `LOW_CONFIDENCE` quality while preserving missing states,
original OCR values, and null numeric confidence. Product-code evidence never
becomes an E3 ID. Provider public error codes/retryability are preserved; a
verification failure never becomes a successfully completed extraction.
