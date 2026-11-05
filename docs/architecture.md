# Architecture decisions

## Client and server state

The Expo app owns navigation, transient form/UI state, language choice, and SecureStore session persistence. TanStack Query owns fetched server state and invalidation. The access token stays in memory; the opaque refresh token is stored in SecureStore. One shared refresh promise prevents concurrent requests from rotating the same token twice.

The FastAPI service separates versioned route handlers, Pydantic request/response schemas, service-layer ownership lookups, SQLAlchemy models, and append-only Alembic migrations. PostgreSQL is authoritative. Phase 3 does not create an offline cache of confidential client data.

## Authentication and uploads

Email is case-folded and account phone numbers are normalized to E.164. Passwords use Argon2id. Access tokens are short-lived signed JWTs; refresh tokens are random opaque values stored only as SHA-256 hashes. Refresh-token reuse revokes the session family. Password reset is single-use and revokes active sessions.

Profile/signature uploads are limited to supported image types and 5 MB, decoded and re-encoded to strip metadata, stored outside public static assets, and served only through an authenticated owner route. Mobile biometric lock is an additional device gate, not a replacement for server authentication.

## Phase 3 ownership model

```text
User
├── Client (user_id, soft-deleted/archived)
│   ├── ClientNote (client_id + user_id)
│   └── ClientInteraction (client_id + user_id)
├── Court (user_id = private creator)
└── AdvocateCourtFavorite (user_id + visible court_id, unique pair)

Court (user_id = NULL) = shared, read-only reference
```

- Every client lookup includes the authenticated `user_id` and `deleted_at IS NULL`. Normal detail/list calls also exclude archived records; explicit archived flows opt in.
- Notes and interactions verify the parent client owner and their own `user_id` before read or mutation. Foreign identifiers from another advocate resolve to 404 to reduce ID probing.
- A court is visible only when active and either shared (`user_id IS NULL`) or owned by the caller. Only its creator may update/deactivate a private record. Shared records cannot be mutated through advocate APIs.
- Favorites first validate court visibility. The database unique constraint on `(user_id, court_id)` makes repeated favorite requests idempotent.
- Request bodies never choose ownership. Services derive all `user_id` values from the authenticated session.

## Data and phase boundaries

Phone validation accepts reasonable international formats rather than assuming Indian mobile numbers. Court types are bounded strings rather than a PostgreSQL enum, so later categories can be introduced without rewriting applied migrations; the Phase 3 UI exposes the currently supported list. Kerala’s 14 districts are UI filter reference values, not fabricated court records.

No official court details are seeded by this phase. A future shared-directory ingestion path must verify source data, retain the source URL, and run separately from advocate-created private records.

Phase 4 adds owner-scoped cases with optional primary client and visible court references, multiple parties, advocate representation, explicit status history, and a read-only case activity log. Status mutation uses a dedicated endpoint. The primary advocate is the signed-in advocate; other advocate records grant no application access. All nested lookups first verify the owning case. Archived cases require explicit access and are excluded from normal listings. Client case counts include both primary-client and linked-party references without double counting.

Hearings, appointments, diary, document vault/OCR, tasks, fees, AI, and offline sync remain future modules.
## Phase 5 hearing ownership and history

`Hearing` belongs to both an advocate and one of that advocate's cases. Every hearing read or mutation scopes by the authenticated user, and creation resolves the case through the existing ownership check. `HearingReminder` belongs to the same advocate and hearing. Completing, adjourning, or postponing a hearing preserves its original row and creates a separate linked follow-up row in one database transaction. Repeated finalization is rejected once the original status changes. Calendar lists use `hearing_date`; nullable `hearing_time` is never filled with a display placeholder.

Reminder records store a UTC delivery instant. For date-only hearings, the service selects 09:00 in the advocate's timezone as the **reminder delivery time**, never as the hearing time. Local OS scheduling is performed by the mobile client with generic notification content; the server does not mark it delivered. Push transport and a worker are deployment dependencies still outstanding.
