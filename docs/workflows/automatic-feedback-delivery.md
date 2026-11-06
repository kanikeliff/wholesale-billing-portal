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
commands or source files. The worker is required for automatic delivery.

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
state and offers a refresh button. Internal payloads, API headers and remote
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
