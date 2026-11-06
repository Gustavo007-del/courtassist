# Phase 12: Legal Research Library

## Workspace and data ownership

Phase 12 extends the existing ResearchItem table and the existing private document vault. It adds structured metadata, favorites, archive state, a private tag catalogue with item/note associations, dedicated research notes, case links, extraction provenance, import previews and research audit events. Previously saved titles, citations, inline notes and source URLs remain intact. Existing inline research notes remain on their original item; they are not silently duplicated into the new dedicated notes table.

Every item, note, tag, import batch, extraction source and audit lookup is authenticated and owner scoped. Linked cases, clients and documents are validated before writes. Case association records do not copy or modify the practice case's details. Tag rename updates the owning advocate's item/note tag snapshots and associations; a tag can be deleted only when no item or note, including archived records, uses it. Core records are archived rather than silently deleted.

Research notes separate formatted personal analysis from quoted source text and citation/page/paragraph references. Notes support tags, pinning, case/item links, search, archive and restore. Personal analysis is not represented as quoted legal authority.

## Source integrity

Citations are retained verbatim, including punctuation and whitespace, on create, patch and CSV import. Missing legal details stay blank. Source names, URLs, user-entered access dates, page/paragraph references and verification notes are available. Manual verification is explicitly labelled as an advocate annotation and requires verification notes; it does not represent official validation. Structured extraction resets verification to unverified. Previous citation/source metadata is retained in private audit records when edited.

There is no official, comprehensive or live legal database integration. The initial library uses user-entered records, user-selected files, CSV imports and supplied URLs. URLs are validated as HTTP(S), credential-bearing URLs are rejected, and the backend never fetches their content. The mobile app opens them only on explicit selection. The optional future provider boundary in research_sources.py has no registered adapters or network calls; a future adapter requires verified access permission and provenance before registration. The migration retains any old unsupported external-verification marker in audit and resets the active marker to unverified.

## Search and organization

GET /research-items and /research-items/search return an items/total/limit/offset envelope. Search covers titles, case names/numbers, CNR, citations, courts, Act/section references, subjects, notes, permitted full text, source names, tags, and available OCR/extracted document text. Document matches are restricted to the owned document's current version. List results omit large source text and include a shortened summary; details contain the full stored fields.

PostgreSQL uses to_tsvector('simple', ...) and plainto_tsquery with a GIN expression index on the research metadata/text. It reuses the vault OCR text-search architecture rather than copying document text into another search store. Owner/update, owner/type, owner/court/date, owner/case, reverse tag associations, and note owner/pin/case indexes support common filters. SQLite development/testing uses case-insensitive metadata substring matching. Filters include type, exact court, judgment date range, language, tag, favorite, linked case and archive status; sorting supports recent update, title and judgment date. Pagination is bounded to 100 records.

Tags are private, case-insensitive catalogue entries with user-defined names; the subject field also allows free-form classification. No exhaustive legal taxonomy is imposed. Notes can be searched by title, analysis, quotations and references, and filtered by item, case, tag, pin and archive state.

## Private documents and extraction

The existing vault uploader accepts PDF, DOCX and UTF-8 TXT, alongside its earlier image types. It retains private upload staging, immutable stored versions, size/checksum/signature checks, short-lived signed downloads and document audit logs. DOCX structure and macro checks remain enforced. TXT rejects invalid UTF-8 and binary control content. Research upload routes reuse that uploader and attach the confirmed document to an existing research item; retrying a failed link after successful upload does not repeat the upload.

Extraction reuses DocumentOCR, the current private document version, the existing Celery task and Redis broker. ResearchSourceMetadata references that job and version, with suggestions, source text, page evidence and explicit review decisions. The worker reads private objects only; there are no external AI/OCR provider calls. Existing PDF/image OCR is reused. DOCX/TXT extraction is added to the same worker; these formats are marked unpaginated, with no invented page numbers. PDF evidence preserves the original OCR page number.

Conservative patterns suggest explicitly labelled citations, case titles, courts, case/CNR numbers, judgment/order dates, parties and Act/section references where available. Unavailable fields are listed for manual entry. A generic date is not automatically treated as a judgment date. Labelled dates are interpreted as day/month/year; review ambiguous dates against the original source. Extraction never writes case or research metadata automatically. The advocate accepts, edits or rejects suggestions; approved values are schema-validated, old metadata is audited, and the original source file remains unchanged. Reviews retain original evidence and actor/timestamp. Reviewing a stale document version is rejected. Accuracy/confidence is not claimed; unknown confidence remains null.

## CSV import

A sample is provided in docs/research-import-sample.csv and GET /research-items/import/sample. The app supports choosing or pasting CSV and displays validation errors and possible duplicate records before confirmation. Supported headers are documented by CSV_FIELDS in research_service.py; title is required, other metadata is optional. CSV tags use a pipe separator. Dates use YYYY-MM-DD. Unsupported/duplicate headers and malformed/incomplete rows produce an error report. A batch supports at most 500 rows and a bounded request size.

POST /research-items/import first creates an owner-scoped preview batch. Confirmation references its batch_id, expires after 30 minutes, rechecks duplicates against current private data and executes atomically. Any invalid rows block import. Possible duplicates require explicit approval; no rows are silently skipped. Confirmed batch IDs are repeat safe and return the original imported IDs rather than importing again. Imported metadata is labelled imported and unverified. Preview payloads are cleared after successful import; abandoned preview retention should follow the deployment's private-data retention policy.

## API inventory (/api/v1)

- Research items: GET/POST /research-items; GET /research-items/search; GET/PATCH/DELETE /research-items/{id}; POST archive, restore and favorite; GET audit.
- Tags: GET/POST /research-tags; PATCH/DELETE /research-tags/{id}.
- Notes: GET/POST /research-notes; GET/PATCH/DELETE /research-notes/{id}; POST /research-notes/{id}/restore. DELETE archives.
- Import: POST /research-items/import and GET /research-items/import/sample.
- Extraction: POST /research-items/{id}/extract-metadata; GET /research-items/{id}/extraction-status; POST /research-items/{id}/confirm-metadata.
- Case integration: GET/POST /cases/{id}/research-items; DELETE /cases/{id}/research-items/{item_id}. Case-linked notes use the notes case_id filter.

The previous starter research list now uses the paginated envelope; the existing mobile service wrapper is adapted. Favorite requests may provide an explicit boolean for repeat-safe UI actions; an empty POST retains toggle compatibility.

## Files and screens

Backend additions: app/models/research.py, app/schemas/research.py, app/api/v1/research.py, app/services/research_service.py, research_search.py, research_extraction.py and research_sources.py; migration 0017_research_library.py; tests/test_research.py. ResearchItem remains in app/models/phase10.py and is extended, not duplicated. Its old starter routes are moved from app/api/v1/phase10.py to the dedicated router. Model/router registration and the shared document validation/OCR/publishing services are updated. app/database/session.py hides SQL bind parameters in database error messages to avoid logging private research content. Earlier generated document status names are normalized to the vault's canonical cloud_stored state without changing keys or file content.

Mobile additions under src/app/research/: workspace/list, search, filters, details, create/edit, tags, notes, note editor, upload entry, case research and metadata review. ResearchItemForm and research-api.ts provide shared UI/contracts. Existing vault upload/OCR views, home actions, Practice tools, case detail navigation, starter service compatibility, and English/Malayalam locale strings are integrated. The five-tab navigation is retained. Notes reuse the Phase 10 rich editor, including its explicit HTML-source web fallback; metadata and CSV are never executed.

## Setup and migration

No new secrets, environment variables or native dependencies are introduced. Keep the existing private S3 settings, file-size limits, signed-URL lifetime and bucket access/CORS policy. Install current backend requirements (python-docx was already added in Phase 10). Apply alembic upgrade head; the current revision is 0017_research_library. Restart the API and the existing OCR worker after deployment.

For extraction, configure REDIS_URL and OCR_PROVIDER=pypdf for PDF/DOCX/TXT text extraction, or tesseract for scanned PDFs/images as well. The existing container provides English/Malayalam Tesseract support; verify your deployment binaries/language packs if running outside it. Start the existing worker with celery -A app.workers.ocr.celery_app worker. With no worker configured, extraction returns an explicit unavailable/failure state; ordinary manual library and note operations continue to work.

The migration uses additive columns and new tables/indexes, retains existing records, migrates tag associations and primary case links, and records unsupported legacy verification flags in audit. It was run against a temporary legacy SQLite schema containing an existing citation/tag/case link; the exact citation and original case data were preserved. PostgreSQL-specific migration/index execution must still be checked against the deployment PostgreSQL server, which is unavailable in this workspace.

## Verification and limits

The full backend suite passed 20 tests, including six Phase 12 tests. Coverage includes cross-user denial, linked ownership, verbatim citations, search/OCR scope, filters/pagination, tags/rename/usage restrictions, notes, favorites/archive, repeat-safe CSV confirmation, extraction review/version integrity, actual existing worker execution with private-storage replacement, and DOCX/UTF-8 extraction. Tests use SQLite and a storage replacement, not a live S3/Redis deployment. There is an existing Starlette/httpx deprecation warning.

Mobile TypeScript/lint and Android Metro/Hermes export pass. No new native dependencies were required. A physical Android device, live private storage and broker, and real PostgreSQL query plans still require deployment checks. Pattern-based extraction is intentionally incomplete and may identify quoted or irrelevant source passages; always review the original. Scanned-image quality depends on Tesseract and the source. There is no semantic legal reasoning, source freshness guarantee, public-source connector, AI interpretation or offline synchronization.

Reproduce checks with .venv/Scripts/python.exe -m pytest -q in backend; npm run typecheck, npm run lint and npx expo export --platform android --output-dir dist-check in mobile. Scope stops at Phase 12.
