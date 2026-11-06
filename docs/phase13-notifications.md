# Phase 13 — notifications, reminders and automation

## Implementation and scope

Phase 13 extends the modular monolith and existing Expo notification integration. It does not implement Phase 14, AI, offline synchronization, office management, client messaging, or WhatsApp delivery.

The notification center, preferences, follow-up creation/rescheduling, device management, database scheduler, local alarms, FCM adapter and optional SMTP adapter are implemented. Firebase is **not provisioned**: the project currently has no Android Firebase configuration, server service-account credentials, or test device. Live FCM/SMTP delivery is therefore not certified. The in-app center works without external providers. Local alarms require a native build, device permission, and synchronization with the API.

## Architecture and data

`notification_events.py` publishes durable, content-free events in the same database transaction as ORM changes to hearings, existing reminders, tasks, appointments, fee agreements, payments, invoices, documents and drafts. Preference changes also publish events. Ordinary business writes perform no provider requests. New integrations can use `publish_event` with a validated owner and entity UUID.

`notification_service.py` reconciles those events and the current business records into `Notification` rows. Existing `HearingReminder` and `PlanningReminder` records remain the per-item configuration; no parallel per-module reminder tables are introduced. Task/appointment configuration suppressed by an older category preference is reconstructed into its existing single reminder row after re-enabling. Completed/cancelled/archived sources cancel future reminders. A received payment reduces the actual agreement balance; a pending payment does not. Agreement-linked invoices do not produce a second automatic alert when their agreement already has a due-date reminder.

Migration `0018_notifications` follows `0017_research_library`. It adds notification fields to the existing `UserPreference` table and creates:

| Model | Purpose |
| --- | --- |
| `Notification` | Generic center content, source identity, nominal/effective schedule, category, priority, status, read/dismiss/cancellation and provider acceptance timestamps |
| `UserDevice` | Advocate-owned installations, platform, encrypted native token, token digest, last-seen and revocation timestamps |
| `NotificationDelivery` | One target per notification/channel/device (or user for email), retry deadline, persisted lease and local reservation |
| `NotificationDeliveryAttempt` | Numbered immutable attempt outcomes, sanitized errors and provider acceptance ID |
| `NotificationEvent` | Transactional source-change outbox and processing timestamp |

UUID primary keys, timezone-aware timestamps, deduplication/target/attempt uniqueness, due/owner/source indexes, and composite owner foreign keys protect notification/device/delivery ownership. Linked polymorphic business entities are checked against the authenticated owner. Existing tables and records are not dropped. The migration's downgrade intentionally retains user choices and delivery history; recovery uses a forward migration rather than destructive rollback.

## Scheduling, recovery and duplicates

Celery Beat enqueues one tick per minute through the existing Redis broker. Run one Beat instance. The tick handles bounded event/user batches, then prepares due targets and dispatches persisted delivery rows. Users are scanned by oldest reconciliation timestamp, so recovery does not depend on Redis retaining delayed ETA messages. Apply migrations before starting either worker. The OCR worker remains separate and unchanged.

The database is the schedule of record. Source keys plus timestamp/generation digests prevent duplicate logical reminders. A unique delivery target and row locks prevent simultaneous workers claiming the same target. A persisted preparation marker prevents old in-app-only notifications starving newer batches. A two-minute lease recovers interrupted delivery attempts; an interrupted attempt is recorded as `unknown`, never silently reported successful. Transient failures back off 60, 120, 240, 480… seconds, capped at one hour and `NOTIFICATION_MAX_ATTEMPTS` (default five). Invalid FCM tokens are cleared and revoked. Permanent/configuration errors do not retry indefinitely.

Provider acceptance is `sent`. `delivered_at` remains null because the implemented providers do not supply confirmed delivery receipts. Local acknowledgement is `local_scheduled`; foreground observation is separately recorded. Neither is proof of delivery. Read state is a separate timestamp, preserving the transport outcome.

Local alarms are preferred per device when the device has acknowledged that exact notification. FCM is skipped for that device; other registered devices may still receive it. Once a push target is processing or accepted, the same device cannot claim a local alarm for it. Stable native identifiers and time comparisons update/cancel alarms without duplicating unchanged alarms. The native queue is capped at 50 upcoming alarms; later reminders are scheduled during subsequent foreground syncs. Legacy hearing/planning identifiers are removed during reconciliation.

Exactly-once delivery across an external network cannot be guaranteed: a worker can crash after provider acceptance but before its database commit. Stable FCM collapse keys/tags and email Message-ID reduce visible duplicates, but are not provider idempotency guarantees. This ambiguity is recorded and bounded by the retry policy.

## Timezones, preferences and privacy

All instants are stored in UTC. Wall-clock reminder settings use the existing IANA timezone preference. Date-only hearings retain a null hearing time; a separately configurable reminder clock (default 09:00) determines their reminder instant. Day-before offsets use local calendar days, including DST boundaries. Manual local times in a DST gap are rejected; ambiguous times use the first occurrence. Standard task date-only reminder clock remains the existing 18:00 convention.

Quiet hours support daytime and overnight intervals. All priorities wait until the interval ends unless the advocate explicitly enables the urgent override. Urgent means an explicitly urgent task/follow-up, not every upcoming event. Native channel DND bypass is disabled.

Existing category choices and daily-summary preference are preserved. Push/email, document/draft follow-ups, automatic hearing/finance rules, derived task alerts, and urgent quiet-hour override default off. Local reminders retain the existing enabled behavior, but permission is never requested during passive sync. Daily summaries default off for new accounts and include actual owner-scoped counts. Repeated overdue alerts default off; an advocate can choose a 1–30 day repeat interval.

All lock-screen text is generic in English/Malayalam. Push data contains only notification UUID and category. No client names, case numbers, confidential notes, documents or financial amounts enter notification payloads or provider error logs. Details and source navigation require authentication and ownership checks. Native tap data cannot supply an arbitrary route or URL.

Device tokens use Fernet authenticated encryption at rest and a SHA-256 lookup digest; API output never returns tokens/digests/ciphertext. The first configured encryption key encrypts new tokens; previous comma-separated keys permit rotation. Retain previous keys until old devices re-register. Store keys outside source control and backups of plaintext application configuration.

Registration is idempotent per advocate/installation. A refreshed token updates that installation; transfer of a token revokes its old registration without reassigning historical attempts. Revoked installations cannot silently reactivate: use the explicit Enable/re-register button. Logout sends the device/installation ID and revokes its own registration, cancels native alarms, dismisses native notifications and unregisters native push. Password reset/change revokes all account devices. Remote revocation prevents future server delivery immediately; already downloaded alarms are removed when that device next synchronizes.

An offline or terminated device cannot immediately learn about server-side cancellation, payment receipt, preference changes, or a changed timezone. OS delivery timing/battery restrictions also apply. Server changes are applied on app foreground, after business mutations and every minute while active. This phase does not claim background/offline synchronization or guaranteed deadline delivery.

## Mobile screens and workflow

* Home bell: notification center and periodically refreshed unread count.
* `/notifications`: category icons, read/unread/all filters, date ordering, pagination, scheduled inclusion, mark all read and empty/loading/error states.
* `/notifications/[id]`: read-on-open, schedule/status, provider/local outcomes and attempt counts, authenticated source navigation, daily-count navigation, dismiss/cancel and manual reschedule.
* `/notifications/create`: document/draft/agreement/invoice selection, configured timezone, local date/time, priority and review/filing/collection/payment/general purpose. Rescheduling creates a new historical notification and cancels the previous one atomically. It does not mark a document filed or approved.
* `/settings/notifications`: channel/category controls, automatic intervals, due-today/overdue/priority rules, summary clock, timezone, quiet hours, optional urgent override, OS permission flow and device revocation.

Document detail, draft editor and agreement/invoice detail expose contextual follow-up actions. Related records remain subject to their existing ownership checks. English and Malayalam strings are supplied for all new controls and generic messages. Subsequent attempts after permission denial open OS settings instead of repeatedly prompting.

## API surface

All endpoints are under `/api/v1`, authenticated and advocate-scoped.

* `GET /notifications` — category, unread_only/read_only, scheduled inclusion, ascending date sort, offset/limit (maximum 100).
* `GET /notifications/unread-count`, `POST /notifications/read-all`.
* `GET /notifications/{id}`, `PATCH /notifications/{id}/read` (POST alias retained), `POST /notifications/{id}/dismiss`.
* `GET/PATCH /notification-preferences` — reuses existing preference row; validates merged settings, IANA timezone, quiet-hour pair and interval bounds. Returns provider capability flags, never credentials.
* `POST /notifications/register-device`, `GET /notifications/devices`, `DELETE /notifications/devices/{id}`.
* `POST /notifications/reminders` — explicit future follow-up, optional `replaces` for atomic rescheduling, owner-validated document/draft/agreement/invoice. Future range limited to one year.
* `GET /notifications/local-plan?device_id=…&local_allowed=true`, `POST /notifications/local-ack`, `POST /notifications/{id}/observed?device_id=…` — bounded native schedule reconciliation, not arbitrary background-job control.
* `/auth/logout` additionally accepts optional device/installation UUIDs; older clients remain compatible.

## Setup from scratch

1. Configure the existing backend `.env`, PostgreSQL and Redis. Install backend requirements in the project's virtual environment. Existing storage/OCR configuration continues to apply.
2. Run `alembic upgrade head` against the configured PostgreSQL database before deploying API/worker code.
3. Start the API, existing OCR worker as needed, plus notification worker and a single Beat instance. Docker Compose now includes `notification_worker` and `notification_beat`. Outside Docker:

   ```text
   celery -A app.workers.notifications.celery_app worker --loglevel=WARNING --concurrency=1
   celery -A app.workers.notifications.celery_app beat --loglevel=WARNING
   ```

4. For FCM, create a Firebase project and register Android package `in.courtassist.advocate`. Download the Android client `google-services.json` to a private local path. Set mobile build variable `GOOGLE_SERVICES_FILE` to that path. `app.config.js` applies it to Android configuration. This file is client configuration, **not** the Admin SDK service-account key.
5. Create server-side service-account credentials with permission to send FCM messages, or use workload/Application Default Credentials. Set backend `FCM_ENABLED=true`, `FCM_PROJECT_ID`, `FCM_CREDENTIALS_FILE` (optional with ADC), and `NOTIFICATION_TOKEN_KEYS`. Generate a persistent Fernet key with:

   ```text
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Mount server credentials read-only into API/notification-worker containers, e.g. `/run/secrets/courtassist-fcm.json`, and set `FCM_CREDENTIALS_FILE` to the container path. The default Compose file deliberately does not reference nonexistent local credentials. Use a deployment-specific volume/secret override for both services. Do not place the admin key in mobile configuration, `EXPO_PUBLIC_*`, source control or the Docker build context. Ignore rules cover Firebase files and `secrets/`; arbitrary credential filenames must also remain outside the repository.
6. Build a native Android development build. Expo Go does not certify remote FCM functionality. With EAS, configure a development profile and use `npx eas-cli@latest build --platform android --profile development`; configure the Firebase build file as a file environment variable where appropriate. Install the build on a device, sign in, enable push in notification preferences and tap Enable/re-register. FCM on Android requires Google Play services/network support.
7. Optional email uses existing `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and a verified account email. TLS is required (SSL on 465; STARTTLS otherwise). Enable email explicitly. Never manufacture an email verification flag; use the application's account-verification/provisioning process.
8. WhatsApp is an unsupported adapter point. No unofficial automation, client messages or provider credentials have been added.

Useful primary references: [Expo SDK 58 notifications](https://docs.expo.dev/versions/v58.0.0/sdk/notifications/), [Firebase Admin messaging](https://firebase.google.com/docs/cloud-messaging/send/admin-sdk).

## Files added or modified for this phase

Backend additions: `app/models/notifications.py`, `app/schemas/notifications.py`, `app/api/v1/notifications.py`, `app/services/notification_channels.py`, `notification_devices.py`, `notification_events.py`, `notification_service.py`, `notification_delivery.py`, `app/workers/notifications.py`, `migrations/versions/0018_notifications.py`, `tests/test_notifications.py`.

Backend extensions: `app/models/user.py`, `app/models/__init__.py`, `app/core/config.py`, `app/main.py`, `app/api/v1/router.py`, `app/api/v1/auth.py`, `app/schemas/auth.py`, `app/schemas/hearing.py`, `app/services/auth_service.py`, `app/services/hearing_service.py`, `requirements.txt`, `docker-compose.yml`, `.env.example`, `.dockerignore`.

Mobile additions: `src/services/notification-api.ts`, `notification-plan.ts`, `notification-manager.ts`, `src/components/NotificationLifecycle.tsx`, `src/app/notifications/index.tsx`, `[id].tsx`, `create.tsx`, `tests/notifications.test.mjs`.

Mobile extensions: `src/app/_layout.tsx`, `src/app/(tabs)/index.tsx`, `src/app/settings/notifications.tsx`, `src/app/hearings/[id].tsx`, `src/app/documents/[id].tsx`, `src/app/practice-tools/draft-editor.tsx`, `src/app/finance/detail.tsx`, `src/services/api.ts`, `hearing-api.ts`, `local-hearing-reminders.ts`, `planning-reminders.ts`, `src/features/auth/services/auth-api.ts`, both locale JSON files, `app.config.js`, `package.json`/lockfile (SDK-compatible `expo-crypto`), mobile `.env.example`. Root `.gitignore`, README and architecture docs also updated. Earlier phase changes already present in this workspace were preserved.

## Verification and deployment limits

| Check | Result |
| --- | --- |
| Full backend regression suite | 38 passed |
| Notification-specific backend suite | 18 passed |
| Mobile Node tests | 7 passed (6 notification/native-adapter tests and the existing scanner PDF test) |
| TypeScript type check | Passed |
| ESLint | Passed |
| Android JavaScript/Hermes export | Passed, 4,010 modules |
| Additive migration 0018 against legacy fixture | Passed; existing preferences and hearing reminder retained |
| Full PostgreSQL migration run | Not run: PostgreSQL/deployment configuration unavailable |
| Real FCM/SMTP/device delivery | Not run: credentials and device unavailable |


Commands:

```text
# backend
.venv\Scripts\python -m pytest -q
# mobile (Node 24 supports the TypeScript pure helper import)
npm run typecheck
npm run lint
node --test tests/*.test.mjs
npx expo export --platform android --output-dir dist-check
```

The handover verification includes the full backend regression suite; notification-specific tests cover hearing date-only/timezone rescheduling and inheritance, quiet hours/DST/urgent opt-in, task reschedule/completion/overdue/re-enable, appointment cancellation/change alerts, received-vs-pending fee balances, invoice deduplication, real daily counts, token encryption/transfer/revocation/logout, owner constraints and cross-user access, local acknowledgement/permission withdrawal, retry limits/lease recovery, mocked FCM/SMTP privacy and additive migration preserving legacy choices. Native-adapter tests cover denied permission, no automatic prompt, stable schedule identifiers, cancellation, bounded queues, remote revocation and safe payload routing. Locale key parity is tested.

Migration `0018` was executed in an isolated legacy-schema SQLite test, including repeat execution. A full fresh-database Alembic run was attempted in an isolated temporary SQLite database and stopped in pre-existing migration `0002_workspace` at PostgreSQL-specific `'[]'::json` SQL. No `.env`, PostgreSQL server, Docker executable or deployed database is configured in this workspace, so a full PostgreSQL `alembic upgrade head` remains a deployment check; it has not been claimed successful. Existing database records were not altered by that attempt.

No Firebase configuration, Android device/emulator, SMTP account or live Redis/Celery deployment was supplied. FCM/SMTP were tested with mocks; worker tick/restart logic was tested against a database session. Actual Android notification appearance/timing, Google Play services, OS reboot behavior, permissions on physical hardware, broker recovery and PostgreSQL concurrent-worker locking require staging verification. Do not treat a successful JavaScript export as a native-device test. Dependency warnings about Starlette's httpx transition, Firebase's legacy registration-token argument and Node's inferred module format do not indicate failed tests.

Phase 14 has not been started.
