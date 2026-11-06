# Final milestones — backend implementation and evidence

Source: BU Wholesale Billing Final Milestones, November 6–December 11, 2026.
This is a backend scope/evidence map, not a claim that future weekly evaluation
or independent acceptance has already taken place.

| Date / milestone | Backend deliverable | Evidence / remaining dependency |
| --- | --- | --- |
| Nov 6: initial demonstration | Upload, OCR job, extraction evidence, Team A recommendation, review, final decision and automatic feedback | Fresh local BOL flow completed; record `6583823f-b7a2-4382-849f-9b76bda3b665` reached REJECTED and Team A confirmed feedbackReceived. |
| Nov 13: deployment and baseline | Local backend/worker runbook, dependency preflight, reproducible field-scoring command | Implementation ready. Real baseline scores require independently labeled BOLs and the agreed evaluation split. |
| Nov 20: error resolution | CSRF origins, immutable OCR evidence, missing-field handling, finite numeric validation, stale-evaluation and concurrent-correction protection | Backend regression tests cover these paths. OCR model or UI changes belong to their owners. |
| Nov 27: expanded/difficult BOL testing | Repeatable upload/review/feedback regression and read-only independent evaluation | Failure/retry and diesel/unleaded mismatch cases tested. Real unseen/difficult documents must be supplied/approved and evaluated without tuning on them. |
| Dec 4: stability and documentation | Queue recovery, bounded SQL query counts, startup/preflight instructions, preserved baseline/final reports | Backend tooling implemented. Shared deployment and real final-vs-baseline measurement remain environment/data-dependent. |
| Dec 11: demonstration/contributions | Traceable backend tests, measurable SQL improvement, live-flow evidence and known-limitations register | This document and linked runbooks provide the handoff. Presentation approval is separate. |

## Run and inspect the local backend

Use the verified Python environment for each process; no machine-specific venv
name is assumed. PostgreSQL must be configured. Run web, OCR and feedback workers
as separately supervised processes, from the repository root:

```sh
python backend/manage.py runserver --settings=config.settings_database
OCR_ENFORCE_BUDGET=false OCR_INCLUDE_CONFIDENCE=true python backend/manage.py run_ocr_worker --settings=config.settings_database --interval 1
python backend/manage.py run_feedback_worker --settings=config.settings_database --interval 3
```

The dollar test cap is explicitly disabled with `OCR_ENFORCE_BUDGET=false`; the
existing ledger is preserved. Normal OCR inference is paid. This setting disables
the dollar gate, not the extractor's model/output and three-generation-call protocol.
Use the same budget setting in web and worker environments.

The OCR command must use the environment containing approved `mirabito-ocr` 0.3.0.
Web and workers share database/source storage and compatible provider, readiness
and budget settings. Do not silently switch to sample OCR to hide live failures.

Check dependencies without running inference, training or feedback delivery:

```sh
python backend/manage.py backend_preflight --settings=config.settings_database
python backend/manage.py backend_preflight --settings=config.settings_database --strict --require-live-ocr
```

From the OCR worker's Python environment, add `--check-ocr-package` to verify
installed pinned runtime hashes and its configuration. The JSON report covers
DB/migration readiness, queue counts, local OCR readiness, numeric certainty
registration and whether Team A credentials are configured; credential values
are never printed. Strict mode exits nonzero when prerequisites fail.

Feedback worker liveness, remote receipt and persistent storage access across
hosts are explicitly not asserted by preflight. Validate them using the actual
worker process logs and an approved end-to-end record. It is not a replacement
for deployment acceptance or a background supervisor.

## Reliability guarantees added for final evaluation

- An evaluation starts with the current record version checked under a row lock.
  Network requests run outside the transaction. A late success cannot overwrite
  newer corrections, another evaluation or a final decision. A stale response
  returns the existing HTTP 409 conflict path and requests reload/re-evaluation.
- A late temporary error cannot falsely report a finalized record as pending.
- Corrections recheck final status and the old field value under locks. A stale
  editor cannot reopen finalized records or overwrite a competing edit unnoticed.
- NaN and infinity are rejected as gallon corrections; valid existing negative
  number validation retains its established error message.
- Recommendation revisions, original OCR evidence, audit actor/history and the
  immutable feedback snapshot remain separate records.

## Measure baseline and final OCR performance

Start from [the label manifest template](../evaluation/ocr-labels.example.json).
The all-zero IDs/hashes and example values are placeholders and must be replaced;
they are not scored project data. An independent reviewer provides `expected`
labels, document IDs and the stored source checksum. Use `split=baseline` or
`split=unseen`. Preserve BOL leading zeros and use ISO dates. Only labeled fields
contribute to accuracy; omitted labels are not assumed correct. Blank and null
labels are equivalent, text uses NFKC/casefold/collapsed whitespace and gallon
values use exact decimal comparison without an undeclared tolerance.

```sh
python backend/manage.py score_ocr --settings=config.settings_database \
  --manifest /private/path/baseline-labels.json --output /private/path/baseline-report.json
python backend/manage.py score_ocr --settings=config.settings_database \
  --manifest /private/path/final-labels.json --output /private/path/final-report.json \
  --baseline /private/path/baseline-report.json \
  --tuning-manifest /private/path/tuning-sources.json
```

The tuning manifest contains `documents` with `sourceSHA256` for every known
training/tuning source. Source overlap and duplicate source documents are rejected.
Without it the report states that unseen status is declared and not verified.
A same-dataset baseline comparison requires identical source hashes and labels;
a changed source set or label revision must have a separately identified report.

The scorer reads `ExtractedField.normalized_value`, never corrected billing
values. It requires a completed OCR job and stored source hash. It reports labeled
field accuracy, per-field counts/accuracy, measured OCR job latency and the Brier
score for fields that have numeric model certainty, marked calibrated=false.
The report does not equate high certainty with correctness or validate calibration.
Existing reports are not overwritten; output files are owner-only. There are no
model calls, training actions or business-record writes in this command.

Comparative accuracy on arbitrary new holdouts can be reported as independent
cohorts, but is not presented as a paired improvement on the same dataset. Keep
label manifests and reports containing business data outside version control.

## Backend evidence already available

- Query count for a nonempty record list: 222 → 5 on the same 55-record local set.
  One elapsed-time observation was 240.17 → 47.27 ms; this is not a production SLA.
- Feedback success, retry, remote restart, lost acknowledgment, local ack-write
  failure, leases and deduplication tested with actual local Team A service code.
- Both diesel/unleaded E3 mismatch directions and reviewer correction tested.
- See [performance](backend-performance.md), [feedback](automatic-feedback-delivery.md),
  [live OCR](live-ocr-integration.md) and [Alpha acceptance](alpha-acceptance.md).

## Owner decisions/data still needed

1. OCR/evaluation owners: independently verified labels, permission to use the
   difficult/unseen BOL set, and the complete training/tuning source hash list.
   Without these, no real accuracy baseline, improvement percentage or unseen-data
   claim is published.
2. Team A: baseline/final matching/validation/recommendation metrics and evidence
   that feedback is consumed by their intended training/regression jobs. API
   receipt alone is insufficient. No Team A model/rule change is made here.
3. Deployment owner: execute the shared-environment acceptance checklist on its
   exact revision and topology. Railway setup remains with Berkay.
4. Frontend owner: verify the review/error presentation in the intended browser
   environment. This milestone changes backend behavior and tooling only.

The PDF is a planning source; it does not authorize sending files to others,
changing model training policies or marking external acceptance complete.

## Verification on November 6, 2026

- Full local PostgreSQL backend suite: 233 passed, 8 optional OCR runtime/package
  cases skipped (241 total), including actual local Team A roundtrip tests.
- Operational preflight passed from the verified OCR environment: migrations
  current, pinned package verified, live worker ready, numeric certainty enabled,
  and dollar budget enforcement disabled by explicit user approval.
- Source and report schema checks are deterministic; example/test labels are
  synthetic. No accuracy number for a real independent holdout is claimed.
- No frontend or Team A implementation was changed in this milestone. No schema
  migration is introduced. Graph tooling and private reports remain local.
