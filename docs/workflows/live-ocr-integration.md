# OCR provider selection

`OCR_PROVIDER=sample` is the default. It loads saved extraction JSON only for
manifest-matched PDFs and needs no model key or live OCR package.

`OCR_PROVIDER=live` uses the standalone handoff pinned to commit
`f89b403573e05b6ee8815dba81711dbd7677e416`, package `mirabito-ocr` 0.3.0.
The approved source TAR SHA-256 is
`42fc51fd015613594f38d91153f12c33a18ffda45d230bf9760b6f9bec9f2066`.
The supplied wheel SHA-256 is
`deb02a5c5bf6421888e6572d431352819c6bd10f782ce1bf25fd3be213715af1`.
Verify the artifact, stop an idle worker, then install the supplied wheel with
`python -m pip install --no-index --no-deps /path/to/mirabito_ocr-0.3.0-py3-none-any.whl`.
Install into the actual worker's Python environment;
the package is not assumed to be available from a public package registry.
Installed runtime file hashes must match `live_package_manifest.json`.

Supply `OPENAI_API_KEY` through the worker environment using hidden terminal
input or a secret manager. Do not put OCR credentials in repository files.
Team A's existing environment loader/configuration is independent and unchanged.

Worker variables (not read from the Team A `.env` loader):

| Variable | Default / allowed test setting |
| --- | --- |
| `OCR_PROVIDER` | `sample` or explicitly `live` |
| `OCR_INCLUDE_CONFIDENCE` | `false`; explicitly set `true` in the live worker environment for numeric certainty |
| `OCR_OPENAI_MODEL` | `gpt-6.1-sol` |
| `OCR_MAX_OUTPUT_TOKENS` | `8192`, cannot exceed 8192 in live mode |
| `OCR_API_TIMEOUT_SECONDS` | `240` per provider request |
| `OCR_MAX_PAGES` | `1` |
| `OCR_ENFORCE_BUDGET` | `false`; set `true` in both web and worker environments to re-enable the test cap |
| `OCR_MAX_COST_USD` | `4`, optional test cap when enforcement is enabled |
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
remaining budget (only with `OCR_ENFORCE_BUDGET=true`) returns HTTP 503 before creating a billing record; frontend
errors use the existing error styles. Failed records expose the public OCR error
instead of showing unexplained empty review fields.

The original $4 smoke-test cap is disabled by default for normal uploads. Paid
OCR usage continues without that dollar cap; the model, output-token limits,
one live job attempt and maximum three generation calls per document remain.
The ledger continues tracking conservative reservations and keeps all history.
For a bounded smoke test, set `OCR_ENFORCE_BUDGET=true` in both service environments.
Changing this setting requires restarting both services; restarting never resets
the ledger or creates a fresh budget.

With a configured shared ledger, the worker can remain running and process normal
uploads. Without a shared ledger, ad hoc live
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
disallowed. Reservations are tracked before sending requests, including
failed/ambiguous submissions. The generation-call limit always applies; the
cumulative dollar cap applies only with `OCR_ENFORCE_BUDGET=true`.
The configured shared ledger survives worker restarts and coordinates processes
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
original OCR values, and null numeric confidence in legacy/sample mode. Product-code evidence never
becomes an E3 ID. Provider public error codes/retryability are preserved; a
verification failure never becomes a successfully completed extraction.

## Opt-in numeric certainty

```sh
OCR_PROVIDER=live OCR_INCLUDE_CONFIDENCE=true python backend/manage.py run_ocr_worker \
  --settings=config.settings_database --interval 1
```

Restart the idle worker after changing the package or opt-in setting. A variable
exported in another terminal does not update an already-running worker. Worker
registration and successful job metadata report `includeConfidence` for audits.
Leave this variable unset or `false` to retain the unchanged legacy request.
The sample provider does not require the live package and continues returning
null confidence when the saved extraction has no numeric evidence.

Numeric mode requests model-reported Top-K alternatives in the extraction call.
It can change newly extracted values and output-token usage; grounding and blind
rereading still run, within the existing maximum three generation calls.
After adaptation, the pinned helper binds scores to the extraction hash, exact
raw candidates and product row order. Mismatches fail instead of silently
attaching scores. Existing review flags are applied afterwards and remain
authoritative, including when a flagged field has 99% certainty.

The existing confidence column stores each eligible score. Existing JSON field
metadata retains `confidenceMetadata`, including method, extraction hash and
`calibrated=false`. Missing/unreadable/invalid or normalization-unresolved values
keep null scores. Product-code scores remain separate from E3 IDs. No thresholds,
schema migrations, automatic approvals or backfills of old records are added.
Review displays **Model certainty (uncalibrated)**; null still shows Unavailable.
Team A recommendation confidence remains a separate existing field.

`tests/fixtures/ocr_samples/Sample_BOL_3_numeric_certainty.json` contains selected,
unchanged fields from the OCR team's recorded pilot, with artifact provenance.
Bridge tests replay this fixture against an isolated test database; they do not
constitute a new live app test or evidence of calibrated accuracy. A fresh paid
upload must be reported separately with its new record and inference provenance.

### Local app verification for this bridge

The approved fresh upload created record `212927cc-a7d4-41a4-b219-45f2211c87a4`
and job `0bd03282-2aa5-4584-884e-88be543361bd`. It used the real 0.3.0 pipeline,
three fresh generation responses, no application cache, and took 20.75 seconds.
Its $0.83604 conservative reservation was below the explicitly approved $1 test
cap; this is not an invoice or an exact billed amount.

Upload returned HTTP 201. Record detail, reload and the unchanged source PDF
returned HTTP 200. PostgreSQL retained 12 numeric scores and three null scores
(Contract/Lifting and both E3 IDs), with method metadata and an OCR audit event.
The record remained NEEDS_REVIEW with two product rows. BOL Number and Origin
each retained a LOW_CONFIDENCE warning alongside 99% model certainty. Snapshots
of all pre-existing business records and their associated data were unchanged.
The user confirmed the scores, missing-field warnings and label in the browser
after refreshing. The normal opt-in worker was restored after the bounded test.
No Team A evaluation was sent.

Automated verification: 51 extractor tests, 187 Django tests, 24 frontend tests,
and the frontend production build passed. The standalone extractor tests need
repository fixtures outside the source archive; those were supplied in staging
without modifying the pinned package runtime files.

Files changed for this bridge:

- `backend/infrastructure/ocr/live_ocr_client.py`
- `backend/infrastructure/ocr/live_package_manifest.json`
- `backend/infrastructure/ocr/runtime_configuration.py`
- `backend/application/services/ocr_job_worker.py`
- `backend/application/services/ocr_processing_service.py`
- `backend/application/services/ocr_field_persistence_service.py`
- `backend/tests/test_numeric_confidence_bridge.py`
- `backend/tests/fixtures/ocr_samples/Sample_BOL_3_numeric_certainty.json`
- `frontend/src/pages/ReviewPage.tsx`
- `frontend/tests/workflow.test.cjs`
- `docs/workflows/live-ocr-integration.md`
