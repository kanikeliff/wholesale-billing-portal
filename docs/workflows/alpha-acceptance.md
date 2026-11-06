# Alpha workflow acceptance and deployment handoff

Updated November 6, 2026. This separates verified portal behavior from checks that
must run on the shared Alpha deployment. Railway setup belongs to Berkay and was
not changed during this work.

## Verified locally

| Requirement | Evidence |
| --- | --- |
| Upload → OCR → normalized record | A fresh Sample BOL 3 upload returned 201 and completed live OCR; source PDF returned 200 with its original checksum. |
| Review and Team A evaluation | Validation and evaluation returned 200. The missing Contract/Lifting value remained null; reviewer-directed REJECT returned 200 and persisted REJECTED. |
| Automatic feedback trigger | The saved decision automatically reached SENT through the normal worker. Team A's GET record endpoint returned feedbackReceived=true. |
| Existing incomplete-record review batch | 21 unfinished records were rejected at the reviewer's explicit request with their missing fields listed in the local reason; all 21 feedback deliveries reached SENT. Finalized records were excluded. |
| Retry and failure regression | Local cross-repository tests cover 503, 401/operator retry, lost acknowledgments, server restart, local acknowledgment-write failure and lease recovery without duplicate feedback. |
| Product/E3 category mismatch | Diesel + UX (unleaded) and gasoline + UD (diesel) produce line-specific PRODUCT_MISMATCH and REVIEW_REQUIRED. Suggestions do not overwrite billing values. A saved correction removes the E3 mismatch after re-evaluation and is retained in feedback. |
| Frontend behavior | Pending/retrying feedback refreshes automatically and stops on SENT or nonretryable rejection. Stale responses cannot update another record. Finalized records explain why editing is disabled. |
| Local request origins | Both localhost:5173 and 127.0.0.1:5173 pass session/CSRF-protected mutation checks. Untrusted origins remain rejected. |
| Frontend integration | The current portal branch includes the known frontend/can-integration and integration/frontend-alpha histories and the current upload, review and API changes. |

The fresh live flow's local record ID is `6583823f-b7a2-4382-849f-9b76bda3b665`.
That ID is evidence in the local development database, not a record expected to
exist on Railway. No fresh paid OCR is needed to run the automated regression.

Final automated results:

- Portal PostgreSQL suite: 207 passed, 8 optional OCR runtime/package cases skipped
  (215 total), including nine real Team A in-process integration scenarios.
- Updated Team A service suite: 101 passed, source revision `0d105b3`.
- Frontend suite: 29 passed. TypeScript and production build passed.

Repeat commands and the isolated cross-repository setup are in
[automatic-feedback-delivery.md](automatic-feedback-delivery.md).

## Shared Alpha deployment — Berkay's acceptance checklist

1. Select one exact portal commit from `backend/durable-ocr-integration` for both
   web and worker processes. Use the matching frontend build; do not combine
   unreviewed branch snapshots. Record the deployed commit and Team A model version.
2. Confirm the target PostgreSQL connection and persistent source-document storage.
   Use the deployment's configured Python environment to run:

   ```sh
   python backend/manage.py check --settings=config.settings_database
   python backend/manage.py showmigrations --settings=config.settings_database
   python backend/manage.py migrate --settings=config.settings_database
   ```

   Apply migrations to the intended Alpha database only. This milestone adds no
   migration, but existing billing/persistence migrations must already be applied.
3. Verify the approved `mirabito-ocr` 0.3.0 artifact in the actual OCR worker Python
   environment. The OCR branch is `ocr/ocr-lab`, source `f89b403`; runtime file
   hashes must match `backend/infrastructure/ocr/live_package_manifest.json`.
   Follow [live-ocr-integration.md](live-ocr-integration.md). The package is not
   assumed to be available from a public package registry.
4. Configure secrets server-side. Check `USE_MOCK_BILLING_PROVIDER=false`,
   `USE_MOCK_TEAM_A=false`, the intended `TEAM_A_BASE_URL`, `TEAM_A_API_KEY`,
   database configuration and OCR provider settings. Supply the OCR key privately.
   Set `OCR_INCLUDE_CONFIDENCE=true` when numeric certainty is required. Web and
   OCR workers must agree on provider/readiness and budget settings; keep the
   existing budget history. Do not assume laptop `/private/tmp` files exist on
   the deployment or that separately hosted processes share worker-state files.
5. Configure the public frontend origin, reverse proxy, allowed hosts, cookies and
   CSRF for the actual Alpha URL. Browser API/media URLs must reach the Alpha
   backend; localhost refers to the visitor's computer. Existing local Vite
   proxy settings are development settings, not a production reverse proxy.
6. Run separately supervised web, OCR worker and feedback worker services. OCR
   startup/routing must support the deployment's process/filesystem topology.
   The feedback process command is:

   ```sh
   python backend/manage.py run_feedback_worker --settings=config.settings_database --interval 3
   ```

   The OCR command is `python backend/manage.py run_ocr_worker
   --settings=config.settings_database --interval 1`. Run it from the verified
   OCR environment. Confirm worker startup, DB access and permissions in logs.
7. From the actual Alpha browser URL, upload one approved test BOL. Record upload
   receipt, OCR job/record IDs, observed statuses, source PDF accessibility,
   extraction evidence and model certainty. Save a header and line-item correction;
   reload and verify both values and audit history.
8. Request Team A evaluation. Verify stable line IDs, persisted recommendation and
   visible exception indicators. Repeat a diesel/unleaded mismatch case and its
   correction. Submit a final decision with a reason; verify it survives reload.
9. Confirm feedback transitions to SENT automatically. Match its acknowledgment
   entry ID with Team A and verify feedbackReceived=true. Stop/restart the worker
   on an approved test record to verify pending feedback survives. In a controlled
   test, verify temporary Team A failure and automatic retry without duplicates.
10. Use a dedicated test BOL for the demo. Existing REJECTED/APPROVED/EXCEPTION
    records are finalized and intentionally read-only; do not reset them merely
    to repeat the demonstration.

## Team A confirmation still required

The feedback endpoint persists decisions, corrections and the matching evaluation
snapshot. SENT/feedbackReceived confirms receipt. It does not prove that a model
was retrained or that a separate regression job was scheduled. Team A must confirm
its downstream consumption/job trigger and provide the corresponding result.

Shared Alpha deployment readiness and a browser end-to-end pass on that exact
deployment remain open until the checklist above is executed there. Local passes
must not be recorded as deployed acceptance.
