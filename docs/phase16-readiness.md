# Phase 16 · Release readiness and audit report

## Scope and changes

The review covered the API router and owner checks, schema and migrations, auth, vault and OCR, casework, planning, drafting, finance, research, notifications, AI and sync, plus mobile routes, settings, offline storage, configuration and release assets. Before changes, 56 backend and 12 mobile tests passed, including the optional Malayalam PDF fixture. TypeScript and lint passed.

- Authentication uses Argon2id, expiring access JWTs and rotating hashed refresh tokens. Issued JWTs now identify a session family and private requests require an active family. Logout, password changes, refresh reuse, revocation and erasure block subsequent requests. Production requires the session claim. Legacy clients can refresh to obtain it. Existing access on fully disconnected devices is constrained by the Phase 15 lease. Added an owner-scoped session list and revocation in Settings, a per-account password-reset cooldown, and certificate verification for recovery email.
- HTTP controls now enforce size and body time limits, suppress raw validation values, use trusted hosts and explicit CORS in hardened environments, require configured Redis for auth rate limiting, and emit correlation IDs and content-free request telemetry. Signed file responses and API data use no-store. Production disables the interactive schema endpoint. Broader abuse controls and privileged penetration testing remain staging work.
- The private vault validates declared size, extension, signature and checksum. Added safe attachment filenames, storage timeouts and optional ClamAV scanning before promotion. Malware and scanner failures leave bytes inaccessible in staging. OCR has limits on rendered image size, subprocess time and Celery task time, and uses a dedicated queue. Notification work also has a dedicated queue. Worker telemetry excludes extracted text.
- AI remains off by default. Reviewed provider-scoped consent, separate document and external consent, owner checks, configured destinations, response and job limits, and human review. The provider processes confidential data only under the enabled configuration and consent. The guardrails reduce prompt injection risk. They cannot prove that model output is correct or guarantee provider conduct.
- Finance uses decimal INR calculations and existing append-only adjustments and reversals. A canonical request digest protects new payment retries even when the stored payment changes status. Concurrent replay relies on the existing owner/key unique index and transaction handling. Existing payments keep their legacy comparison path.
- The database adds a partial active-session index and migration `0021_release_controls`. PostgreSQL connections have pool and statement bounds. Dashboard task counts and overdue filtering run in SQL. The hearing conflict summary loads each day's active hearings in one query instead of querying per hearing. A regression test measures the same dashboard SELECT count with zero and three same-day hearings. Case and client feeds use virtualized lists with existing server pagination. Production timings, large-workspace benchmarks and Android profiling require staging data and a device.
- Android release profiles require HTTPS, block microphone access, disable ordinary app backup, and guard private routes after logout and on unauthenticated deep links. Existing device and app settings still govern local offline access. The existing package ID is retained.
- Account erasure is password-confirmed. The API disables access and records a receipt, and the operator purge removes stored files and owner records after review. Staging must verify the erasure role and versioned bucket behavior. A full workspace export uses the documented identity-verified support process. External deletion intake and support staffing require operator setup.

## Readiness checklist

| Area | Status | Evidence or remaining work |
| --- | --- | --- |
| Authentication security | Verified | API regression tests for session rotation, reuse, revocation, logout and password changes. OTP is absent. Live SMTP delivery requires configuration |
| Authorization and isolation | Verified | API tests use unrelated advocates, nested UUIDs and foreign linked records. Includes finance, vault metadata, drafts, research, notifications and sync |
| Document privacy and scanning | Partially implemented | Vault unit and API tests and scanner verdict tests. Verify production IAM, live signed transfers, real clamd quarantine, and parser behavior on hostile files |
| Database integrity and migration | Verified | Full chain applied to native PostgreSQL 17.11. A separate rehearsal also verified that legacy cases remained visible in the incremental feed |
| Financial integrity | Verified | Accounting tests passed. Two concurrent requests with the same payment key produced one record on native PostgreSQL 17.11 |
| AI privacy | Partially implemented | Consent and isolation tests use a controlled adapter. Live provider settings, terms, limits and egress require review |
| Offline synchronization | Partially implemented | Tests cover cross-owner isolation, revocation, stale edits, replay, deletion and restart simulation. Two concurrent case edits on native PostgreSQL produced one applied operation and one conflict. Physical two-device reconnect checks remain |
| API reliability | Partially implemented | Readiness, body limits and error redaction tested. Load, failover, saturation and ingress checks remain |
| Android compatibility | Requires manual verification | Expo SDK and release bundle checks pass. Physical install, upgrade, camera, sharing, notifications and WorkManager runs remain |
| Automated tests | Verified | 62 backend tests passed in the standard suite and the PostgreSQL concurrency test passed separately. The cross-module API and erasure workflow passed on native PostgreSQL. All 15 mobile tests, TypeScript, ESLint, Expo Doctor and Android bundle export passed. The device smoke flow remains pending |
| Backup and recovery | Requires external configuration | The backup script encrypted a native PostgreSQL archive with age. The decrypted archive restored to a separate local database with matching migration head, account count and payment count. Schedule production backups and rehearse recovery with the vault and profile files |
| Monitoring | Requires external configuration | Request logs, health and readiness endpoints, queue probe and alert examples. Configure collection, alerts and on-call |
| Deployment | Requires manual verification | Compose 5.7 validated the production configuration with all profiles. The Docker image, HTTPS ingress and worker processes still need a staging run |
| Privacy and legal readiness | Requires manual verification | Draft terms, notice, retention, export, erasure and incident process. Operator and qualified counsel review required |
| Android signing and release | Requires external configuration | EAS profiles and app identity prepared. Signed AAB and Play listing still pending |
| Operational support | Requires external configuration | Assign owners for security, account requests, backup, release, incident response and recovery |

The backend audit identified advisories affecting `cryptography` 48.0.1. After upgrading to 50.0.2, the audit found no known vulnerabilities in the installed Python packages. [PyCA changelog](https://github.com/pyca/cryptography/blob/main/CHANGELOG.rst) · [PyPA advisory](https://github.com/pypa/advisory-database/blob/main/vulns/cryptography/PYSEC-2026-3552.yaml)

The npm production dependency audit reported five moderate dependency findings in Expo build tooling related to glob and minimatch. No high or critical findings were reported by that scan. Its proposed automatic fix changes the Expo SDK major. Verify a compatible Expo fix before release. [Glob advisory](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4) · [Minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249)

## Handover files

- [Backend and Android release, monitoring, backup and restore](phase16-deployment.md)
- [Privacy notice, terms, account requests and incident process](phase16-privacy.md)
- Backend entry points include `app/core/http.py`, `app/api/v1/auth.py`, `app/services/account_erasure.py`, `app/services/malware_scan.py` and migration `0021_release_controls.py`.
- Release files include `Dockerfile.production`, `compose.production.yml`, `ops/`, mobile `eas.json`, the Maestro flow and `.github/workflows/release-checks.yml`.

No live release, paid service, public deployment or app-store submission was performed.

