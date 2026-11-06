# Phase 15 · Offline storage and synchronization

## Setup on Android

1. Back up the deployment database and run `alembic upgrade head` from the backend directory with the normal PostgreSQL connection configured. Revision `0020_offline_sync` adds the sync tables, installs change triggers and seeds the first feed from existing records. It takes write locks on tracked tables while seeding. Deploy the API and worker code together.
2. Use the Phase 8 private vault configuration for file synchronization. The backend needs its existing `S3_BUCKET`, credentials, private bucket policy, staging lifecycle and signed-URL settings. The mobile app uses the existing `EXPO_PUBLIC_API_URL`. Phase 15 adds no server credentials.
3. In the mobile directory, run `npm ci` and rebuild the Android development client with `npx expo run:android` or the project's native build pipeline. The new Expo SDK 58 BackgroundTask and TaskManager modules require a native rebuild. The root entry registers the task before Expo Router starts.
4. Sign in online. Open **Settings → Offline and sync**, enable offline storage, and run **Sync now** until the initial download finishes. Select **Keep offline** on any stored vault document you want available without a connection.

[Expo background tasks](https://docs.expo.dev/versions/v58.0.0/sdk/background-task/) · [Expo Router custom entry](https://docs.expo.dev/router/installation/#custom-entry-point-to-initialize-and-load-side-effects)

## Offline capabilities

| Area | Available after enabling and syncing | Changes queued offline |
| --- | --- | --- |
| Cases | Details, client links, parties, advocates, status history and timeline | Create, edit metadata and primary links, change status, archive, restore |
| Hearings and calendar | Hearing lists, history, schedules and unified agenda | Create, edit, cancel and reschedule hearings |
| Diary | Case and hearing notes, searchable text, flags and dates | Create, edit, delete, pin and mark important |
| Tasks and appointments | Due dates, statuses, linked records and cached reminders | Create, edit, complete, reopen or archive tasks. Create, edit, cancel or archive appointments |
| Clients and courts | Client details, notes, interactions and case associations. Private courts and a cached shared-directory page | Read only |
| Document vault | Metadata, categories, tags and selected verified versions | Queue new files from the scanner or device, edit metadata, archive |
| Drafting | Cached draft list, details and formatted content | Create, edit, archive and restore. The server continues to create draft history |
| Research | Cached items and notes, plus case-linked pages previously loaded online | Read only |
| Finance | Cached summaries, records and previously opened reports | Record a pending payment or edit permitted metadata. The server validates it and confirmation is a separate online action |

Offline requires a previously synced record or an exact cached response where there is no local projection. The shared court seed covers up to 100 directory records, with additional details available if previously opened. Legal templates, clauses, version and export workflows, cloud OCR, external research, invoice and receipt generation, payment confirmation, reversals, adjustments, live scheduling checks and AI processing require connectivity. The application does not submit AI requests from the offline queue. Existing generic notification wording is retained and unsynced records do not create remote notifications.

## Local database and account security

The scanner and sync layers share `court-assist.db`. The additive v1 migration in `src/features/sync/schema.ts` runs transactionally on first use, with SQLite WAL and secure deletion enabled. It preserves the scanner tables. All local operations use the owner and the same UUID that the server will accept. Related queued operations refer to stable UUIDs.

| Table | Contents |
| --- | --- |
| `sync_schema` | Applied local schema version |
| `sync_control` | Owner, device ID, cursor, enable and automatic sync settings, verification/expiry, encrypted profile, last successful sync |
| `sync_entities` | Record kind and UUID, server revision, local edit version, pending operation, tombstone, encrypted snapshot and sync timestamp |
| `sync_queue` | Ordered operations, retries and timing, upload reference, encrypted change and conflict data. Ready-state and record indexes support replay |
| `sync_http` | Encrypted responses for allow-listed read routes |
| `sync_files` | Encrypted per-document-version metadata and encrypted blob references |
| `sync_runs` | Recent run duration, result and applied count |

Expo Crypto encrypts cached business content, profiles, queue payloads, conflict snapshots and pinned or queued file bytes with AES-256-GCM. Keys are stored per owner in SecureStore. Auth tokens are kept in SecureStore or memory. Row-specific authenticated data binds ciphertext to its intended owner and record. SQLite schema and operational metadata such as UUIDs, status and timestamps remain visible within the app sandbox. SQLCipher is not enabled. The legacy scanner and vault retain their existing app-private filesystem storage. Android's app-private preview and upload scratch copies temporarily contain decrypted bytes.

A cached session can reopen only for the last authenticated account and expires at the earlier of 24 hours after online verification and refresh-token expiry. The existing biometric setting gates app access. Expired or rejected sessions require online sign-in and retain encrypted pending work for that same account. Explicit sign-out warns before deleting that account's SQLite cache, queued work, stored key, and local scan, vault and offline copies. Disabling offline storage is blocked while sync work needs attention. Web keeps the normal online path.

## Server models and wire protocol

`SyncDevice` records the last acknowledged cursor per advocate and installation. `SyncChange` records owner, record type, UUID, revision and tombstones. `SyncOperation` stores idempotency receipts, conflict snapshots and explicit resolution history. Existing tables remain the canonical business records. PostgreSQL deferred triggers journal changes from the normal APIs, workers and sync replay in the business transaction. Per-owner transaction locks serialize journal publication and pulls, so a later commit cannot be skipped because it received an earlier sequence value.

All routes below are authenticated under `/api/v1`.

| Route | Purpose |
| --- | --- |
| `POST /sync/pull` | Pass device ID, cursor and page limit. Returns changed snapshots or tombstones, next cursor and `has_more` |
| `POST /sync/push` | Pass device ID and up to 20 operations. Returns one result per operation |
| `GET /sync/status` | Latest owner revision, open conflict count and optional device cursor |
| `GET /sync/records/{kind}/{id}` | Read the current owner-scoped record snapshot for recovery |
| `GET /sync/conflicts` | List unresolved owner conflicts |
| `GET /sync/operations/{id}` | Read an operation receipt and any recorded resolution |
| `POST /sync/conflicts/{id}/resolve` | Submit the reviewed server revision, resolution UUID and an explicit strategy or edited fields |

A push operation includes the operation UUID, entity UUID, action, payload, local edit version, base server revision, optional form timestamp and dependencies. The server validates links using existing business services. A request digest binds each operation UUID to its original input. The business write, revision and receipt commit together. Replays return the original result without reapplying the mutation. The client keeps edits until acknowledgement, including across restart. Network retries use capped exponential backoff. Invalid and blocked items remain visible for review.

Pull pages are bounded by record count and an approximately 2 MiB response target. The mobile client persists the page and cursor together. Incoming versions cannot overwrite an optimistic edit. The server rejects a stale edit, deletion or relationship change and returns the competing record. The review screen displays changed fields and offers the server version, the local change where supported, or a reviewed merge. The server checks the revision again before committing a resolution and keeps an audit record. Payment conflicts require online review. After an earlier edit is discarded, dependent edits are left visible for review instead of being silently applied to a different base.

## Documents and background operation

Only explicitly pinned vault versions are downloaded to persistent offline storage. The app uses short-lived signed URLs and checks SHA-256 and file size before encrypting a copy. Removing a local copy leaves the cloud version intact. Failed downloads can be restarted. When uploading a queued file, the app first obtains the idempotent vault record, then requests a signed PUT and confirms the uploaded version. The queue remains pending until the server accepts the file. A lost response after confirmation is recovered by checking the stored version and checksum. Transfers retry at the file level. The app limits offline files to 25 MiB and the server also enforces its configured vault limits.

Foreground sync runs on reconnect, app resume, after online changes, periodically while active, and on demand. Android schedules optional background work through Expo and WorkManager with a 30-minute minimum interval. Android controls actual execution based on device state, network, battery and process lifecycle. The next foreground run resumes work after force-stop or when background work is deferred. The local history records duration, outcome and applied count without recording legal content. Large libraries are paged over the network. Local filtered lists decrypt records for the requested kind, so filtering very large collections can still be slower than server search.

## Verification and release checks

From the backend directory, run `python -m pytest -q` with the project environment. Set `COURT_ASSIST_MALAYALAM_TEST_PDF` to the optional Phase 14 sample if testing Malayalam PDF extraction. From the mobile directory, run `npm run typecheck`, `npm run lint`, `node --test tests/*.test.mjs` and `npx expo export --platform android --output-dir dist-check`.

A disposable PostgreSQL 18.6 instance through PGlite ran the full Alembic chain. The upgrade seeded a case created before migration and preserved prior data. Authenticated push updated the case and incremental pull returned the change. The backend passed 56 tests, including the optional Malayalam PDF fixture. Automated tests cover concurrent drafts and diary edits, delete/edit races, stale case forms, relationship ordering, task completion, appointment conflicts, hearing history, duplicate payments, and owner isolation. Mobile passed 12 tests, TypeScript, ESLint and Android bundle export. Mobile tests use a real local SQLite database, filesystem and authenticated encryption with mocked Expo interfaces and network. They cover app restart with pending records, private data isolation, token expiry, tombstones and interrupted uploads.

On a native Android device with a private test bucket, first verify a download and checksum. Enter airplane mode and create a case, add a linked diary entry, complete a task and stage a scan. Force-stop and reopen the app while still offline to check that all four changes persist. Restore connectivity and verify server IDs, vault confirmation and queue status. Repeat with a second authenticated device editing the same draft and diary entry. Try a pending payment, interrupt its response, and confirm one pending server record. Verify background behavior with the app suspended and confirm sign-out removes local files. These device and live vault checks were not run in this workspace. The migration also needs a deployment smoke check on the configured PostgreSQL instance.

## File inventory

- Backend additions `app/models/sync.py`, `app/schemas/sync.py`, `app/services/sync_feed.py`, `app/services/sync_operations.py`, `app/api/v1/sync.py`, `migrations/versions/0020_offline_sync.py`, and `tests/test_sync.py`.
- Backend integrations in the model and API registries, case, hearing and diary services, and the existing document, planning, drafting and finance routes.
- Mobile additions `src/features/sync/`, `src/app/sync/`, `src/components/SyncLifecycle.tsx`, `src/components/common/SyncIndicator.tsx`, `index.js` and `tests/offline-sync.test.mjs`.
- Mobile integrations in the root and settings screens, API transport, authentication store, case, hearing, diary and planning forms, drafting, vault upload/detail/preview, AI connectivity messaging, and English and Malayalam translations.
- Native package and plugin changes in `package.json`, `package-lock.json` and `app.json`.

