# Court Assist — through Phase 5

Court Assist is a private legal-practice application for individual advocates in India, initially focused on Kerala. It includes authentication and advocate workspace features (Phases 1–2), client management and a court directory (Phase 3), case management (Phase 4), and hearing management with a court calendar and local reminders (Phase 5). Document storage, OCR, tasks, finance, AI, and offline synchronization remain future modules.

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
