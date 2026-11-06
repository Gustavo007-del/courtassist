# Court Assist — through Phase 6

Court Assist is a private legal-practice application for individual advocates in India, initially focused on Kerala. It includes authentication and advocate workspace features (Phases 1–2), client management and a court directory (Phase 3), case management (Phase 4), hearing management with a court calendar and local reminders (Phase 5), and a private case diary with unified timeline filtering (Phase 6). Document storage, OCR, tasks, finance, AI, and offline synchronization remain future modules.

## Phase 6: private case diary

Run `alembic upgrade head` from `court-assist-backend` against the configured PostgreSQL database to apply migration `0006_case_diary`. It adds `case_diary_entries`, indexes for owner/case/date and hearing lookup, and a unique owner/request identifier for retry-safe creation. Existing case and hearing rows are unchanged.

Diary entries belong to one advocate and one of that advocate's cases; an optional linked hearing must belong to the same case. Only the authenticated owner can read or change them. Diary text is never copied into formal court records, client-facing content, or activity-log descriptions. Delete removes the entry but leaves a minimal `diary_deleted` case activity event without private note content. The case activity history remains intact.

The `/api/v1/diary` collection supports `GET` and `POST`; `/api/v1/diary/{id}` supports `GET`, `PATCH`, and `DELETE`. Pin and important actions use `POST` or `DELETE` on `/diary/{id}/pin` and `/diary/{id}/important`. Case and hearing collections use `GET` and `POST` on `/cases/{id}/diary` and `/hearings/{id}/diary`. List filters include search, case, hearing, category, date range, important, pinned, sort order, limit, and offset. `GET /cases/{id}/timeline` filters existing case, status, hearing, and diary activity events by category and date range. The mobile case Diary tab and hearing detail actions open the private diary screens.

## Stack and layout

- `court-assist-mobile/`: Expo SDK 58, React Native 0.88, Expo Router, TypeScript, TanStack Query, React Hook Form, Zod, Zustand, and English/Malayalam i18next resources.
- `court-assist-backend/`: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL, Redis, and private local image storage.
- `docs/architecture.md`: trust boundaries, ownership rules, and model notes.

## Start the backend

```powershell
cd court-assist-backend
Copy-Item .env.example .env
# Set strong, unique POSTGRES_PASSWORD and JWT_SECRET_KEY values.
docker compose up --build
```

Compose starts PostgreSQL and Redis, applies `alembic upgrade head`, and exposes the API at `http://localhost:8000`. Swagger is at `/docs`, OpenAPI JSON at `/openapi.json`, and health at `/api/v1/health`.

For an existing PostgreSQL installation:

```powershell
cd court-assist-backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Configure DATABASE_URL and JWT_SECRET_KEY in .env.
alembic upgrade head
uvicorn app.main:app --reload
```

Use `alembic current`, `alembic history`, and `alembic upgrade head` to inspect and apply migrations. Deployed environments must use Alembic rather than `Base.metadata.create_all()`.

## Start the mobile app

```powershell
cd court-assist-mobile
Copy-Item .env.example .env
# Set EXPO_PUBLIC_API_URL to an address reachable from the device.
npm ci
npx expo start
```

Android Emulator can reach the host at `http://10.0.2.2:8000`; a physical device needs the computer’s LAN address. `COURT_ASSIST_ALLOW_HTTP_DEV=1` permits cleartext only in local development builds when the API address uses HTTP. Release builds should use HTTPS and set this switch to `0`.

## Database models and migrations

- `0001_initial`: advocates, rotating refresh sessions, and password-reset tokens.
- `0002_workspace`: advocate profile fields, preferences, activity history, and private image-upload metadata.
- `0003_clients_courts`: clients, client notes, client interactions, courts, and advocate court favorites, including ownership/status/location indexes and a unique favorite constraint.
- `0004_cases`: cases, multiple case parties, advocate representation, status history, and case activity. It adds owner/status/date indexes and foreign keys to existing clients and courts.

Every client, note, and interaction stores the authenticated advocate as owner. A client delete is a deliberate soft delete (`deleted_at` plus archived status). Court records with no `user_id` are shared references; records with a `user_id` are private to their creator. No fabricated court records are seeded. Shared records may be added through a separately controlled, verified data process while retaining their source.

## Client workflow

Open Profile → Settings → Practice Directory → Client Management, or use Add Client on the dashboard. The client list supports owner-scoped search, individual/organization filters, active/archived views, alphabetical/recent sorting, pull-to-refresh, and incremental loading. Client profiles provide native user-initiated phone/email actions, phone copy, editing, archive/restore, private notes, consultation history, and associated case counts and links.

## Case workflow

Open the Cases tab or use Add Case on the dashboard. The creation form records basic information, optional court and client references, multiple linked or external parties, opposing advocates, priority, confidentiality, and initial status. The logged-in advocate is added as the primary advocate automatically. The case list searches title, number, CNR, client and court, with category, status, district and priority filters, sorting, pagination and a separate archive view.

Case details provide overview, parties/representation editing, explicit status transitions with reason and effective date, status history, and an activity timeline that can be sorted newest or oldest first. Archiving preserves all case records. Hearings, diary, documents, tasks, fees and notes are visible as future-module placeholders. Case number and CNR duplicate checks apply within an advocate and selected court; they are not globally unique. Cases without a court remain valid.

## Court directory workflow

Open Profile → Settings → Practice Directory → Court Directory. Search by name and filter by type, state, or any Kerala district. Advocates can create, edit, and deactivate their own private court records, favorite visible shared or private courts, and open available phone, email, or official-website links. Shared references are read-only; another advocate’s private court is returned as not found.

## API endpoints

All routes are under `/api/v1` and authenticated except registration, login, password recovery, and health.

| Area | Endpoints |
| --- | --- |
| System/auth | `GET /health`; `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password` |
| Advocate workspace | `GET/PATCH /users/me`; `GET/PATCH /users/me/preferences`; `POST /users/me/change-password`; `GET /users/me/session-info`; `POST /users/me/images/{purpose}`; `GET /users/me/images/{purpose}/{key}`; `GET /dashboard`; `GET /activities` |
| Clients | `GET/POST /clients`; `GET/PATCH/DELETE /clients/{client_id}`; `POST /clients/{client_id}/archive`; `POST /clients/{client_id}/restore` |
| Client notes | `GET/POST /clients/{client_id}/notes`; `PATCH/DELETE /clients/{client_id}/notes/{note_id}` |
| Interactions | `GET/POST /clients/{client_id}/interactions`; `PATCH/DELETE /clients/{client_id}/interactions/{interaction_id}` |
| Courts | `GET/POST /courts`; `GET/PATCH/DELETE /courts/{court_id}`; `GET /courts/favorites`; `POST/DELETE /courts/{court_id}/favorite` |
| Cases | `GET/POST /cases`; `GET/PATCH /cases/{case_id}`; `POST /cases/{case_id}/archive`, `/restore`, `/status`; `GET /cases/{case_id}/status-history`, `/activities`, `/timeline` |
| Case parties | `GET/POST /cases/{case_id}/parties`; `PATCH/DELETE /cases/{case_id}/parties/{party_id}` |
| Case advocates | `GET/POST /cases/{case_id}/advocates`; `PATCH/DELETE /cases/{case_id}/advocates/{advocate_id}` |

Client listing accepts `limit`, `offset`, `q`, `client_type`, `archived`, and `sort`. Court listing accepts `limit`, `offset`, `q`, `court_type`, `district`, and `state`. Case listing accepts `limit`, `offset`, `q`, `category`, `status`, `district`, `priority`, `archived`, `sort`, and `client_id`. No new environment variables are required for Phase 4.

## Environment

Backend settings are documented in `court-assist-backend/.env.example`. Required for normal startup: `DATABASE_URL`, a random `JWT_SECRET_KEY` of at least 32 characters, and `POSTGRES_PASSWORD` when using Compose. `PRIVATE_STORAGE_DIR` controls the non-public directory used for sanitized profile/signature uploads. Redis settings support rate limiting. SMTP and `RESET_URL_BASE` are required only for email password-reset delivery.

Mobile uses `EXPO_PUBLIC_API_URL` and `COURT_ASSIST_ALLOW_HTTP_DEV`. Never store secrets in `EXPO_PUBLIC_` variables.

## Verification

```powershell
cd court-assist-backend
.venv\Scripts\python.exe -m pytest -q
alembic upgrade head

cd ..\court-assist-mobile
npm run typecheck
npm run lint
npx expo-doctor
```

Backend tests exercise authentication/workspace regressions and cross-advocate IDOR protection for clients, notes, interactions, private courts, and favorites. Before production, configure HTTPS, a trusted mail provider, backups, monitoring, and an operational process for verified shared-court imports.
# Phase 5: Hearings, calendar, and reminders

Migration `0005_hearings` adds `hearings` and `hearing_reminders` with UUID keys, ownership foreign keys, date and nullable time fields, timezone-aware audit and reminder timestamps, and a unique hearing/type/channel reminder constraint. Historical hearings are retained when proceedings create a follow-up or a hearing is postponed. Hearing times remain null until confirmed. The backend stores reminder instants in UTC and calculates relative reminders in the advocate's configured timezone; the mobile calendar uses device-local dates.

Hearing APIs under `/api/v1` are `GET/POST /hearings`, `GET/PATCH/DELETE /hearings/{id}`, `GET /cases/{id}/hearings`, `GET /cases/{id}/hearings/history`, `POST /hearings/{id}/complete`, `/adjourn`, and `/reschedule`, `GET /calendar/hearings`, `/day`, `/day/conflicts`, `/week`, and `/month`, `GET /hearings/conflicts`, `POST /hearings/check-conflicts`, and `GET/POST/PATCH/DELETE /hearings/{id}/reminders[/{reminder_id}]`. The existing `GET /dashboard/overview` includes actual hearing counts and schedules. List APIs accept date range, court, status, case category, pagination, and ordering where applicable.

Conflict checks classify overlaps as confirmed only when both hearing end times are known. Otherwise a one-hour default duration produces an estimated warning; date-only hearings produce an unknown-time warning. Warnings do not block saving. Change `DEFAULT_DURATION_MINUTES` in `app/services/hearing_service.py` to alter the estimate.

Local reminders use `expo-notifications` on Android and iOS. The app requests notification permission when a reminder is scheduled and uses a stable device notification identifier to avoid duplicates. Lock-screen content is generic in English or Malayalam. Server `pending` means a reminder record exists; it does not mean delivery was confirmed. Existing notification settings can disable hearing reminders. Push delivery, FCM token registration, a background worker, confirmed delivery receipts, and retry execution require deployment infrastructure and are not active; push reminder creation returns 503. Do not treat local OS scheduling as a confirmed delivery receipt.

## Phase 7: Scanner and local PDF tools

The Scanner tab supports the native document scanner on devices that provide it (iOS VisionKit or Android ML Kit through Expo Camera), a camera fallback, and gallery import. Native scanning supplies automatic page detection and perspective correction where supported. The fallback offers capture, retake, rotation, and rectangular crop. Multi-page drafts persist in app-controlled storage so they can be resumed after interruption. Draft source images remain until the advocate explicitly discards them; generating a PDF does not remove them.

Review generates A4 PDFs with portrait or landscape pages according to each image, plus high, balanced, and small size presets. The tools merge, extract, rotate, and reorder PDF pages locally. Annotation creates a separate PDF copy and supports area highlighting, lines, shapes, freehand strokes, text, and an image-based handwritten signature. This is not a cryptographic digital signature. Generated documents have local-only metadata, optional case association validated against the authenticated case API, and export, share, viewer, and print actions. No document is uploaded automatically. Local files are stored under the app document directory, scoped by user ID; document metadata uses the local SQLite database. Removing a document deletes its local PDF.

The mobile dependencies are `expo-camera`, `expo-image-manipulator`, `expo-document-picker`, `expo-sharing`, `expo-print`, `react-native-view-shot`, and `pdf-lib`. Camera permission text is configured in `court-assist-mobile/app.json`. To test camera and native scanner behavior on Android, run `npx expo run:android` from `court-assist-mobile` with a device connected, or create an EAS development build. Rebuild after changing native plugins. The native scanner is device-dependent; the camera fallback remains available. A real-device validation pass is still required for permission prompts, scan quality, and OS export/print flows.

Current limitations: the camera fallback does not provide adjustable four-corner perspective correction; image enhancement, grayscale, black-and-white, brightness, and contrast modes are not available yet. PDF pages open in the operating system viewer, while annotation uses page coordinates and a drawing guide rather than an in-app rendered PDF page. Malayalam text annotation is limited by the built-in PDF font. Large PDF operations use `pdf-lib` in JavaScript and may exceed memory on mid-range phones. These capabilities need completion before treating Phase 7 as fully delivered.

## Phase 8: Private document vault

Migration `0007_documents` adds `documents`, `document_versions`, `document_ocr`, and `document_access_logs`. Phase 7 local PDFs and SQLite metadata are untouched. The mobile vault displays those scans separately from cloud records; the advocate chooses when to upload a local scan.

Configure a private S3-compatible bucket and set `DOCUMENT_S3_BUCKET`, `DOCUMENT_S3_REGION`, `DOCUMENT_S3_ACCESS_KEY`, and `DOCUMENT_S3_SECRET_KEY` in the backend environment. Set `DOCUMENT_S3_ENDPOINT` for R2 or another compatible service; leave it empty for AWS S3. Never put these credentials in `EXPO_PUBLIC_` settings. Deny anonymous bucket reads, writes, and listing; configure bucket CORS for the mobile app's direct PUT with `Content-Type`. Configure a short lifecycle expiration for orphaned `documents/staging/` objects, while retaining `documents/stored/` objects under the practice's retention policy. Set `DOCUMENT_MAX_BYTES` (default 25 MiB) and `DOCUMENT_URL_SECONDS` (default 300, maximum 900) as needed. The backend creates randomized private staging keys, verifies size, SHA-256 and file signature, then copies and re-verifies the object at a new key before marking a version stored. It issues short-lived signed GET URLs only after ownership checks and writes upload/download authorization audit records. A new version leaves the previous one available.

Run `alembic upgrade head` before starting the API. The Compose configuration includes `ocr_worker` and Redis. Set `OCR_PROVIDER=pypdf` for embedded PDF text extraction or `OCR_PROVIDER=tesseract` for that plus image OCR and scanned PDF page OCR. The container installs English and Malayalam Tesseract language packages; language detection and confidence are not yet available. OCR results are stored per document version and page. OCR text may be inaccurate, especially on Malayalam legal records, so the app labels it for review. The extraction service currently suggests CNR, case number, and document date from matched source text; review choices are stored separately and do not change case records. Set `OCR_PROVIDER=disabled` to leave OCR off.

The API exposes document CRUD, upload URL and confirmation, signed downloads, version history and downloads, OCR status/retry/results, metadata suggestions/review, search, and case/client/hearing document lists under `/api/v1`. Search filters cloud records by owner and uses PostgreSQL full-text matching on OCR text with a GIN index; title, filename, description, category, case number, CNR, and client name use case-insensitive matching. Search results include an OCR snippet and page reference when an exact text match is found. Structured suggestions use conservative text patterns for CNR, case number, dates, court, party names, advocate names, and document type; they are not authoritative. Mobile screens are under `court-assist-mobile/src/app/documents`; they provide a vault, upload, detail, offline download/preview, versions, OCR, metadata review, search, and archive view.

Before production, verify real private-bucket upload/download with your S3 provider, review bucket CORS and encryption settings, test OCR quality against representative English and Malayalam legal scans, and validate signed URL expiration on devices. This workspace has no configured bucket or Docker runtime, so those integration checks have not run. Current vault limits include basic search filters on mobile, no upload byte-progress meter, and no malware scanner. Archive is a soft delete; object retention and permanent deletion need an explicit policy. The Phase 7 image-processing limitations above also remain.

## Phase 9: Tasks, appointments, and unified calendar

Run `alembic upgrade head` to apply migration `0008_planning`, which creates owner-scoped tasks, appointments, and planning reminders. Task records support priority, category, status, due date and optional time, links to cases/clients/hearings/documents, recurrence, and soft archive. Recurrence generates bounded future instances in a 60-day window; each occurrence is independent and can be completed separately. Appointments support case/client links, meeting details, rescheduling, cancellation, archive, and conflict warnings against other appointments and hearings. A warning does not prevent saving.

Authenticated `/api/v1` routes include `GET/POST /tasks`, `GET/PATCH/DELETE /tasks/{id}`, task completion/reopen/archive, overdue/upcoming lists, `GET/POST /appointments`, `GET/PATCH/DELETE /appointments/{id}`, appointment cancellation/archive, conflict checks, and `GET /calendar/agenda`. The dashboard includes task and appointment counts. Mobile task and appointment screens provide creation, editing, details, lists, and local reminders; the calendar shows hearings, tasks, and appointments together. English and Malayalam UI strings are included.

The mobile app schedules generic local notifications from `GET /planning/reminders/upcoming` when authenticated and on foreground refresh. It cancels stale device notifications after completion, cancellation, archive, or preference changes. Server reminder status is scheduling metadata, not proof that the operating system delivered a notification. Notification permission and device settings control actual delivery. Remote push is not configured. A device build should be used to verify OS permission and reminder delivery. The backend tests use SQLite; this workspace has no configured PostgreSQL runtime, so the migration still needs validation on the deployment database. Category choices are currently built in, and mobile task filters expose only a subset of the API filters.

## Phase 10 and Phase 11: Drafting and finance

Drafting now has native formatted editing, autosave with revision checks, template/clause screens, version restoration, and private DOCX/PDF exports. Finance includes audited payment/expense corrections, invoice/receipt PDFs, transaction forms, detailed reports, and CSV/PDF export. English/Malayalam interface strings and case/client/dashboard navigation are connected.

Update backend requirements, apply `alembic upgrade head` (head `0016_finance_metadata`), configure the existing private S3 settings, and rebuild the mobile development client for `react-native-webview`. Actual Malayalam PDF samples render with embedded Noto Serif Malayalam. Deployment PostgreSQL/S3 and real-device behavior still need checks in your environment. See [the handover](docs/phase10-11-handover.md), [drafting documentation](docs/phase10-status.md), and [financial calculation rules](docs/phase11-finance.md) for file inventory, APIs, setup and verified limits.

## Phase 12: Private legal research library

Research now includes structured reference records, source/citation provenance, search and filters, private tags and notes, favorites/archive, case links, validated CSV preview/import, and document metadata review. PDF/DOCX/UTF-8 TXT research files reuse the private vault and the existing asynchronous OCR worker. Extracted fields remain suggestions until explicitly reviewed; there is no official/live legal database or external scraping integration.

Apply `alembic upgrade head` to revision `0017_research_library` and restart the API and OCR worker. Existing S3, Redis and OCR provider settings are reused; no new secrets or mobile native dependencies are required. See [Phase 12 architecture, API inventory, migration and verification](docs/phase12-research.md) and the [CSV sample](docs/research-import-sample.csv).

### Phase 13 — notifications and reminders

The centralized private notification center, preferences, device registration, database-backed Celery scheduling, local alarms, FCM adapter and optional SMTP adapter are implemented. Firebase provisioning and physical Android delivery checks require deployment configuration. See [Phase 13 implementation and setup](docs/phase13-notifications.md) for migration, channel setup, tests, limits and the file inventory.

### Phase 14 · Optional AI workspace

The AI workspace supports selected-source conversations, document summaries and date extraction, chronology review, and draft and diary suggestions. Server configuration and advocate consent are required before processing. See the [Phase 14 setup and implementation report](docs/phase14-ai.md).

### Phase 15 · Offline storage and synchronization

Enable offline storage in **Settings → Offline and sync** after signing in on Android. Cases, diary entries, hearings, tasks, appointments and drafts support queued changes, and selected vault files can be kept offline. The server checks revisions and preserves conflicting edits for review. Offline payment entries remain pending until confirmed online.

Apply Alembic revision `0020_offline_sync` with `alembic upgrade head` and rebuild the mobile development client for Expo BackgroundTask and TaskManager. See the [Phase 15 handover](docs/phase15-offline.md) for supported workflows, setup, the sync API and verification results.

### Phase 16 · Security and release preparation

Phase 16 adds immediate session revocation, request controls, optional vault malware scanning, account erasure, payment replay protection, and production runtime and Android release profiles. Apply migration `0021_release_controls` before starting the hardened services. See the [readiness report](docs/phase16-readiness.md), [deployment and recovery runbook](docs/phase16-deployment.md), and [privacy and legal drafts](docs/phase16-privacy.md).
