# Phase 14 · Optional AI workspace

Court Assist ships with AI disabled on the server and for every advocate. Ordinary case, document, drafting, diary, finance, and notification flows work with AI disabled. All processing requires an authenticated advocate and runs in the backend worker. The app never receives a provider credential.

## Workflows

| Entry point | Workflow |
| --- | --- |
| Practice Tools → AI workspace | Start a case conversation, view jobs and usage, or open preferences |
| Case overview | Select individual case, status, hearing, timeline, diary, task, document, or research records for a question or chronology |
| Private vault document | Summarize a judgment or order, extract metadata, or review dates and events from the whole document or a selected PDF range |
| Draft editor | Save the draft, paste only the selected text, and request grammar, rewrite, organization, summary, or translation assistance |
| Diary entry or AI workspace | Select rough notes or copy a diary entry into the request form, then organize notes, correct grammar, extract action items, or arrange them chronologically |
| Job details | Poll status, inspect quoted evidence, edit a separate reviewed copy, retry a failed job, or delete AI data |

A case filters the picker. Its details enter a request only if explicitly selected. Each conversation turn has its own source selection. A follow-up can explicitly include the previous question, and source records from earlier turns require a fresh selection. Conversations store the user question and generated result in the associated job. This avoids duplicating message bodies in a second table.

Draft approval preserves a version using the existing drafting snapshot path and checks the draft revision from submission. The advocate can append the reviewed text or replace a unique exact match contained in a single formatted text segment. Complex selections crossing styled segments can be appended or edited in the ordinary editor. Diary approval creates a separate private entry and retains the original note. A date or chronology item requires an advocate-confirmed title, text, case, and date before saving as a diary entry. It creates no hearing, appointment, reminder, or calculated deadline. Reviewed chronologies can be exported as UTF-8 text through the authenticated API or native share sheet.

## Data and retrieval

Migration `0019_optional_ai` follows `0018_notifications`. It adds `ai_preferences`, `ai_conversations`, `ai_jobs`, and `ai_document_chunks`. Existing tables are retained. Jobs store the owner, related records, request identifier, provider/model, pinned source scope, consent revision, processing state, attempts, timestamps, error code, optional token counts and cost, and separate original and reviewed results. Content deletion clears the source links, prompt, results, and vectors while retaining content-free quota and usage records.

The worker resolves each selected record again against the owner. For vault documents, it uses the pinned private document version, matching OCR text and page results. If OCR text is unavailable, it calls the existing text extractor on bytes retrieved through private storage. PDF, DOCX and UTF-8 text follow the existing extractor. Scanned pages and supported images need Tesseract with English and Malayalam language data. The existing Docker image contains those packages. Unreadable or low-confidence pages are disclosed, and jobs with no usable text fail with a reviewable reason.

Document questions use retrieval augmented generation. The worker splits text at paragraph, sentence, or word boundaries without crossing pages. It embeds the question and the explicitly selected document chunks, validates vector dimensions and values, and ranks with exact cosine similarity. Non-document records use bounded lexical ranking. The top eight document passages and up to four record passages can enter a mixed question. Summary, metadata, date, and chronology jobs use bounded batches over the selected content. Jobs refuse over-limit input and let the advocate reduce the scope or select a smaller page range.

Vectors are stored as PostgreSQL-compatible JSON with job, owner, document version, ordinal and page references. Retrieval operates only on the current job's authorized chunks. There is no shared vector index or pgvector extension to install. Vectors expire or are erased with the job. Chunk text comes from the existing vault or case record and is not copied into the vector table.

The model proposes structured evidence and a section label. The backend verifies that each quote occurs in the cited passage after whitespace normalization and attaches source identifiers and page or paragraph references from the app. It discards invented quotes or invalid source numbers. This verifies the quotation's presence in the selected text. Assess its relevance and legal accuracy against the source. Dates must be explicit in the quotation in a supported numeric or named-month format. Inferred dates carry no calendar value. Chronology entries stay separate and show possible conflicts when different dates appear in one event category.

The interface is available in English and Malayalam. Writing requests offer source-language, English, and Malayalam output. Grounded evidence remains in its source language so it can be checked against the document. Generated rewrites and translations remain suggestions and can still introduce errors. OCR quality, retrieval coverage and model language quality vary by document and model.

## Consent, privacy and retention

- Enable AI per advocate. Document and case assistant permissions are separate. Server AI must also be enabled.
- For external processing, the server must be configured for HTTPS and an operator must verify the no-training terms and supply a retention disclosure. The advocate grants consent to that provider configuration in preferences, then confirms each external request. The fingerprint binds consent to provider, endpoint, models, and policy disclosure. The server rechecks consent before each outbound call.
- External document questions can send the selected text chunks to the embedding service and the retrieved excerpts to the generation service. Other document workflows can send the selected excerpts in batches. Clients supply no provider URL or storage key. Stored source URLs and document instructions cannot trigger network actions.
- Revoking consent cancels queued and processing jobs and blocks subsequent provider calls. A request already transmitted can remain with the provider under its disclosed policy. The app's retention controls govern its own database. Provider logs, retention, and any remote deletion follow the verified deployment policy.
- The default retention period is 30 days and the advocate can choose 1–90 days. Shortening the setting shortens existing content retention. Expired content immediately disappears from authenticated results and the worker purges it. Job and conversation deletion also purge vectors. Approved ordinary draft versions and diary records follow their own lifecycle.
- Model output is displayed as untrusted text. Approved text passes the existing draft HTML sanitizer. The application provides no tools to the model, no legal database integration, and no model training pipeline. API validation, transport errors and worker errors omit submitted text. Credentials live only in backend environment or secret configuration.

## Provider setup

1. Configure the existing PostgreSQL and Redis services and install the backend requirements. Apply `alembic upgrade head` to the deployment database before deploying the API and workers.
2. Run one existing notification Beat instance and the AI worker. Compose includes `ai_worker` on the dedicated `court-assist-ai` queue. The worker uses the existing Celery broker and task module. Start it separately if running outside Compose.

   ```text
   celery -A app.workers.ocr.celery_app worker -Q court-assist-ai --loglevel=WARNING --concurrency=1 --prefetch-multiplier=1
   celery -A app.workers.notifications.celery_app beat --loglevel=WARNING
   ```

3. Choose a generation endpoint and model that supports structured JSON. Both Ollama and llama.cpp adapters are available. The server sends requests only to configured endpoints and follows no redirects. For a self-hosted Ollama service, disable cloud features with `OLLAMA_NO_CLOUD=1`, use installed local models, and keep the service on a private network. Verify the provider's deployment logs and retention before allowing confidential text. For llama.cpp, use a chat-capable server and an embedding-capable server with pooling for document questions. Set the embedding URL separately when the servers differ. [Ollama chat](https://docs.ollama.com/api/chat), [Ollama embeddings](https://docs.ollama.com/api/embed), [Ollama local-only configuration](https://docs.ollama.com/faq), [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
4. Set the backend variables below on both API and worker, then restart them. A trusted self-hosted configuration can use `AI_EXTERNAL=false`. Treat any service outside the trusted environment as external and use HTTPS. Enable AI only after the endpoints and policy are ready.
5. In the app, open **Practice Tools → AI workspace → AI preferences and consent**. Enable the workflows you want, then submit a request with an explicitly selected source. Use synthetic content for the first model smoke test.

| Variable | Purpose |
| --- | --- |
| `AI_ENABLED` | Server availability switch, defaults to false |
| `AI_PROVIDER` | `ollama` or `llama_cpp` |
| `AI_BASE_URL`, `AI_MODEL` | Generation server root URL and model name |
| `AI_EMBEDDING_URL`, `AI_EMBEDDING_MODEL` | Optional separate embedding server and model. Document questions require the model |
| `AI_API_KEY` | Optional backend bearer credential. Both endpoints must accept it when supplied |
| `AI_EXTERNAL` | Defaults to true. Set false only for trusted private processing |
| `AI_EXTERNAL_NO_TRAINING_VERIFIED`, `AI_PROVIDER_POLICY` | External deployment attestation and user-visible description of verified training/retention terms. Update the disclosure when terms change |
| `AI_TIMEOUT_SECONDS` | Per provider socket operation timeout, 40 seconds by default |
| `AI_REQUESTS_PER_MINUTE`, `AI_REQUESTS_PER_DAY` | Per-owner rolling limits, default 4 and 20 |
| `AI_MAX_SOURCE_CHARS` | Selected source budget, default 60,000 characters, with an independent 160-chunk bound |
| `AI_INPUT_COST_PER_MILLION`, `AI_OUTPUT_COST_PER_MILLION` | Optional costs in the operator's chosen currency. Set both or leave unset. Estimates depend on provider-reported tokens |
| `REDIS_URL`, `OCR_PROVIDER` | Existing Celery broker and OCR settings. Use `tesseract` for scanned content |

Beat submits an expiring drain task every 15 seconds. The database holds pending jobs, leases and retry deadlines, so broker task loss does not lose a request. Workers claim a row with `FOR UPDATE SKIP LOCKED`. Explicit provider busy responses can retry with bounded backoff if no prior provider call succeeded in that attempt. Transport timeouts and expired worker leases need a reviewed retry, since a request may already have reached the provider. Duplicate request identifiers for the same payload return the original job. The queue carries no documents, prompts, results, or credentials.

## API

All paths below are under `/api/v1/ai`. Status queries and writes use advocate ownership. Lists support bounded pagination.

| Path | Methods |
| --- | --- |
| `/preferences` | GET, PATCH |
| `/context` | GET selectable records by source kind and optional case |
| `/ask` | POST first conversation turn |
| `/conversations`, `/conversations/{id}` | GET list/detail, DELETE detail |
| `/conversations/{id}/messages` | POST follow-up |
| `/documents/{id}/summarize`, `/extract-dates`, `/extract-metadata` | POST jobs under the selected document |
| `/documents/{id}/results` | GET document jobs |
| `/cases/{id}/chronology`, `/cases/{id}/chronology/{job_id}` | POST, GET respectively |
| `/drafts/{id}/improve`, `/rewrite`, `/organize`, `/summarize`, `/translate` | POST jobs under the selected draft |
| `/diary/organize` | POST |
| `/jobs`, `/jobs/{id}` | GET list/detail, DELETE detail |
| `/jobs/{id}/cancel`, `/retry` | POST |
| `/jobs/{id}/review`, `/export` | PATCH reviewed copy, GET reviewed chronology export |
| `/jobs/{id}/approve-draft`, `/approve-diary` | POST explicit approval |
| `/usage`, `/usage/summary` | GET |

## Changed files

Backend additions are `app/api/v1/ai.py`, `app/models/ai.py`, `app/schemas/ai.py`, `app/services/ai_context.py`, `ai_generation.py`, `ai_jobs.py`, `ai_provider.py`, `ai_review.py`, `migrations/versions/0019_optional_ai.py`, and `tests/test_ai.py`. Existing router, settings, model registration, diary creation, OCR task module, notification Beat configuration, Compose, environment example, and auth test fixture were extended.

Mobile additions are `src/app/ai/{_layout,index,request,conversation,history,job,preferences}.tsx`, `src/components/ai/{Controls,ResultReview}.tsx`, `src/services/ai-api.ts`, and the locale test. The request view contains the source picker and the document, chronology, draft, and diary forms. The job view contains document summary, evidence and date/chronology review. History contains jobs, conversations and usage. Entry points were added to Practice Tools, Settings, case overview, document details, draft editor, and diary details. The existing document preview accepts a version ID for evidence links. The API parser handles authenticated text exports. Both locale files were extended.

## Verification

| Check | Result |
| --- | --- |
| Backend regression and Phase 14 suite | 49 passed, including 11 Phase 14 tests with the public Malayalam PDF supplied |
| Mobile tests | 8 passed, including English/Malayalam AI locale and interpolation checks |
| TypeScript, ESLint, Android export | Passed |
| Alembic through `0019_optional_ai` | Passed on a disposable PostgreSQL 18.6 engine via PGlite |
| Live provider and Android device | Require deployment configuration and a device |

Run the backend suite with `.venv\Scripts\python -m pytest -q` on Windows. The focused AI tests use mock responses for both provider integration and workflow validation. To exercise the optional real-file test, set `COURT_ASSIST_MALAYALAM_TEST_PDF` to the downloaded public Gazette PDF, then run `.venv\Scripts\python -m pytest tests/test_ai.py -q`. The test extracts Malayalam from an actual page and checks the resulting Unicode quotation and page reference through the API. The Gazette was used as a text extraction fixture. [Kerala Gazette PDF](https://clinicalestablishments.kerala.gov.in/wp-content/uploads/2025/03/kceamendmentact2024.pdf).

Run `npm run typecheck`, `npm run lint`, `node --test tests/*.test.mjs`, and `npx expo export --platform android --output-dir dist-check` in the mobile directory.

The full Alembic chain ran through revision `0019_optional_ai` against a disposable PostgreSQL 18.6 engine via PGlite. A Phase 13 user and preference fixture survived the upgrade, and authenticated AI preferences were off by default. The production PostgreSQL 17 deployment and concurrent worker behavior still need staging verification. [PGlite Socket](https://pglite.dev/docs/pglite-socket).

This workspace has no configured generation or embedding endpoint, physical Android device, or live broker. Real inference quality, Malayalam translation accuracy, scanned Malayalam OCR accuracy, and physical-device rendering remain unverified. The successful Android export validates bundling. Phase 14 includes the provider adapters and deployment configuration.

