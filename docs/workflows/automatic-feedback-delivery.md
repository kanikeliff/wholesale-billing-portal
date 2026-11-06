# Automatic reviewer feedback delivery

Every new persisted reviewer decision creates a feedback snapshot in the existing
`HumanDecision.feedback_metadata` alongside the decision transaction. It includes
the final decision/status, the linked recommendation/model version/terminal-log
ID and the record's correction audit entries, including exact line-item IDs.
Reviewer identities and decision reasons are not sent. No migration is required.

The feedback worker sends this snapshot to Team A after the transaction commits.
It uses the same server-side `TEAM_A_BASE_URL` and `TEAM_A_API_KEY` configuration
as recommendations. The browser never receives those credentials.

Run this as a separately supervised process alongside Django and the OCR worker,
from the repository root using the backend Python environment:

```sh
.venv/bin/python backend/manage.py run_feedback_worker \
  --settings=config.settings_database --interval 3
```

Deploy the code to both web and worker services and restart the web service.
The worker refuses to start with `USE_MOCK_TEAM_A=true` or missing credentials.
Keep secrets in the existing environment configuration; do not place them in
commands or source files. The worker is required for automatic delivery. It logs startup and recovers
from temporary database connection errors without discarding leases or payloads.

## Delivery guarantees and status

- Decision/status/audit and the immutable payload commit together. Rollback
  leaves no delivery to process. Team A calls never hold DB transactions open.
- `PENDING`: saved and waiting for the worker. `FAILED`: the last delivery failed.
  `SENT`: a valid acknowledgment matching `recordId` was received, with boolean
  `stored` and positive integer `entryId`. `stored=false` is an acknowledged
  idempotent redelivery and counts as delivered.
- Timeouts, network errors, 408/429/5xx, and malformed acknowledgments retry after
  30 seconds, doubling up to one hour. Attempts and scheduling survive restarts.
  There is no retry-count limit for temporary failures.
- Other HTTP rejections remain failed for operator attention. Correct the server
  configuration before explicitly retrying a rejected delivery.
- Row locks and a two-minute lease coordinate workers. If a process dies after
  sending but before saving its acknowledgment, the lease expires and the exact
  same payload is resent. Team A's documented payload idempotency provides
  deduplication. This is at-least-once delivery, not an exactly-once network call.
- Earlier decisions without a saved payload are not automatically backfilled;
  reconstructing historical accepted values would need separate review.

Retry one rejected delivery after correcting its configuration:

```sh
.venv/bin/python backend/manage.py run_feedback_worker \
  --settings=config.settings_database --once --decision-id HUMAN_DECISION_UUID \
  --retry-rejected
```

For a single normally scheduled attempt, omit `--retry-rejected`. A future-due
retry or unexpired lease is left alone. Explicit retry preserves the saved
payload; it does not fabricate corrections or rewrite the reviewer decision.

Record detail includes `feedback`: decision ID, status, attempt count, retryable,
queued, sentAt and a controlled error code. The review page displays the delivery
state, automatically polls queued/retryable deliveries, and offers a manual refresh button.
Polling stops on acknowledgment or nonretryable rejection; late responses cannot
replace a different review record or its draft. Internal payloads, API headers and remote
error messages are not exposed through this field.

## Verification and remaining Alpha checks

`tests.test_feedback_delivery` tests the persisted decision → worker → feedback
chain with a mocked Team A transport, record and line corrections, immutable
snapshots, acknowledgments, timeout/retry, rejection, lease recovery, rollback,
and duplicate suppression. The tests make no live Team A calls.

On the intended Alpha deployment, run the supervised worker, correct a test BOL,
request its recommendation and submit a decision. Confirm `feedback.status=SENT`
and match the acknowledgment with Team A. Confirm their downstream regression /
training consumption separately; API receipt does not prove that processing.

## Local cross-repository Alpha regression

The optional `tests.test_feedback_roundtrip` suite loads the actual Team A FastAPI
application from an explicitly selected checkout. The test uses Django's isolated
PostgreSQL test DB and a separate temporary SQLite store for Team A. HTTP requests
use an in-process ASGI transport that refuses other destinations. OCR replays a
saved PDF fixture; this is not new paid inference or a Railway deployment test.

Use a separate test environment so FastAPI/test dependencies do not change the
portal or OCR worker environments. From the portal repository root:

```sh
export TEAM_A_SOURCE_PATH=/absolute/path/to/ai-recommendation-engine/team_a_service
python3 -m venv /tmp/billing-feedback-regression
/tmp/billing-feedback-regression/bin/python -m pip install \
  -r requirements.txt -r "$TEAM_A_SOURCE_PATH/requirements.txt"
TEAM_A_SOURCE_PATH="$TEAM_A_SOURCE_PATH" \
  USE_MOCK_TEAM_A=true USE_MOCK_BILLING_PROVIDER=false OCR_PROVIDER=sample \
  /tmp/billing-feedback-regression/bin/python backend/manage.py test \
  tests.test_feedback_roundtrip tests.test_feedback_delivery \
  tests.test_feedback_worker_command --settings=config.settings_database --noinput
```

The normal development PostgreSQL test credentials must be available. Running
these tests creates/destroys Django's test database, not the application database.
Without `TEAM_A_SOURCE_PATH`, the optional cross-repository cases are skipped;
the regular portal suite does not require Team A dependencies or a sibling clone.

Coverage includes:

- New PDF upload, OCR completion, header/line corrections and re-evaluation.
- Recommendation revisions and stable record/line IDs through final feedback.
- APPROVE, REJECT and EXCEPTION, with immutable OCR evidence and correction audit.
- Explicit diesel product + unleaded E3 code (UX instead of UD) and unleaded
  product + diesel code (UD instead of UX): line-specific PRODUCT_MISMATCH,
  REVIEW_REQUIRED, unchanged accepted billing value, followed by a human E3
  correction, re-evaluation and feedback with teamAOutputCorrections evidence.
- Team A SQL receipt containing the final decision, corrections and evaluation
  sequence/confidence, not merely an HTTP success stub.
- 503 outage, persisted delayed retry, 401 rejection and explicit operator retry.
- A lost acknowledgment and Team A restart, preserving one stored feedback entry.
- A failed local acknowledgment write, lease expiry and safe idempotent redelivery.

The frontend suite checks automatic PENDING → FAILED → SENT status updates,
no overlapping polls and navigation protection. The command suite checks recovery
from database outages. None of these tests triggers model training. The Team A
feedback endpoint stores evaluation/correction evidence; training or downstream
regression-job execution remains a separate Team A acceptance check.

### Local verification — November 6, 2026

Portal baseline: `7c5f5e8` plus the feedback regression refinements in this working
tree. Team A source: `0d105b3` (`feature/team-a-http-integration`), fast-forwarded
from Bitbucket before testing. Portal `main` was already an ancestor of the
current portal branch; no portal changes were missing after fetch.

- PostgreSQL backend suite including all nine cross-repository scenarios:
  207 passed, 8 optional OCR runtime/package tests skipped (215 total).
- Updated Team A service suite: 101 passed.
- Frontend component/API suite: 29 passed; TypeScript and production build passed.

These results establish local upload/review/feedback and failure-recovery
regression against the actual Team A implementation with isolated SQL stores.
They do not establish a new live OCR accuracy result, Railway deployment health,
or automatic retraining. Deployment remains a separate Alpha acceptance step.
