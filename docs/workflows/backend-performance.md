# Backend read and queue performance

Verified November 6, 2026. These changes affect only backend query execution;
frontend behavior, response fields and OCR/external model settings are unchanged.

## Billing record reads

The former listing path prefetched line items but queried OCR evidence,
corrections, the latest OCR job and the latest decision separately for each
record. Its query count was `2 + 4 * record_count`.

The repository now uses a shared read queryset:

- One record query includes a correlated latest-job summary containing only job
  ID, status and public error fields, not the large OCR `raw_result` JSON.
- Four batched prefetch queries load line items, only the extracted fields needed
  by the response, correction markers and the latest decision per record.
- Latest-decision prefetch uses a per-record limit rather than loading its entire
  decision history. The list and detail serializers use these prefetched rows.
- Ordering includes the primary key to resolve equal timestamps consistently.
- No cache is introduced: requests still read current database state. Corrected
  billing values remain separate from immutable OCR evidence and recommendations.

For a nonempty result set this is five queries, independent of record count.
The detail repository path also uses five queries. Document and recommendation
queries at the HTTP detail layer remain separate from this count.

Read-only measurements on the same 55-record local PostgreSQL dataset:

| Metric | Before | After |
| --- | --- | --- |
| SQL queries for repository list | 222 | 5 |
| One local elapsed-time observation | 240.17 ms | 47.27 ms |

These are local observations, not a production latency guarantee. Timing depends
on hardware, connection startup and cache state; the tested query-count bound is
more reproducible. The current listing still returns the full requested dataset,
so serialization/response size scales with the number of records. Pagination
would be a separate API/frontend change.

## Feedback job selection

Eligibility is filtered in SQL: payload present, retry allowed, lease expired or
absent, and next-attempt time due or absent. `SELECT FOR UPDATE SKIP LOCKED` with
`LIMIT 1` claims one ready decision. Future retries and active leases are no
longer fetched into Python and locked in a broad iterator on every poll.

The existing feedback-status index remains applicable; no migration is needed.
This bounds fetched/locked jobs per claim, not all database work for arbitrarily
large JSON-backed retry backlogs. A future high-volume queue could use typed,
indexed schedule columns after measuring the Alpha workload.

Lease tokens, crash recovery, at-least-once delivery and Team A's idempotency
contract are unchanged. Network calls remain outside database transactions.
Legacy snapshots without scheduling keys are still eligible.

## Regression coverage

`tests.test_backend_query_performance` checks:

- One and twenty rich records both serialize in exactly five queries.
- Batched output matches the non-prefetched serializer, including raw OCR values,
  certainty, correction markers, latest job/decision IDs and empty states.
- OCR raw results and bounding boxes are absent from read SQL.
- A backlog of future retries, leased jobs and permanent rejections does not
  displace a due job; the claim SELECT is SQL-filtered and limited to one row.
- Legacy scheduling metadata and targeted decision selection remain supported.

These checks pass on PostgreSQL and SQLite. Existing real Team A roundtrip,
review/correction and feedback recovery tests exercise the optimized paths.
External OCR/model latency is unaffected by these database changes.
