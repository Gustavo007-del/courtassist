# Phase 10 and 11 handover

## Delivered workflows

- Native drafting editor with formatted HTML, preview, undo/redo, basic editable tables and page breaks; debounced serialized autosave, foreground-exit save attempt, navigation protection and stale-revision rejection.
- Draft/template/clause management screens, literal placeholder review/correction, independent inserted clauses, draft search/pagination, duplication/archive/restore and immutable version snapshots/restoration.
- DOCX/PDF exports into the existing private vault with case/client links, export history, audit records and short-lived authorized downloads.
- Financial forms and lists for agreements, payments, expenses and invoices; agreement edits with history; pending payment/expense confirmation; original-preserving reversal/adjustment workflows; supporting vault documents.
- Historical issued invoices and receipts, automatic settlement classification from confirmed payments, private PDFs, and preserved receipt snapshots after reversal.
- Filtered reports with monthly/annual totals, client/case groups, payment-method and expense-category breakdowns, transaction histories, server CSV and private PDF exports.
- English/Malayalam interface strings; home, client and case navigation; query caches cleared at account changes to prevent stale private data appearing for a different account.

## Backend file inventory

Base records and routes remain in app/models/phase10.py, app/schemas/practice.py and app/api/v1/phase10.py for compatibility. New/extended modular implementations are:

- app/models/finance.py: FinancialAdjustment, Invoice, Receipt and AgreementHistory.
- app/models/drafting.py: DraftExport and DraftAudit.
- app/api/v1/finance.py and app/api/v1/drafting.py: expanded authenticated workflows and export routes.
- app/schemas/finance.py: validated invoice line items, metadata and explicit agreement-change requests.
- app/services/finance_service.py: authoritative decimal summaries and report breakdowns.
- app/services/finance_documents.py: historical financial PDFs and shared generated-document vault publishing.
- app/services/draft_generation.py: sanitized HTML to PDF/DOCX conversion.
- app/services/draft_placeholders.py: safe literal substitution and owned workspace autofill.
- Existing document_storage.py and document schemas: private generated-file reuse and DOCX validation, including size, archive structure and macro rejection.
- tests/test_document_workflows.py and tests/test_finance.py: workflow/security/export/calculation verification.

Migrations 0012_finance_documents through 0016_finance_metadata add financial documents, drafting exports/audits, built-in structural templates, agreement history and metadata. Earlier records/models are reused. Existing columns and transaction amounts are preserved.

## Mobile file inventory

- src/app/drafting/: dashboard/list, creation, library and library editor/preview routes.
- src/app/practice-tools/draft-editor.tsx: editor, preview, versions, placeholder review, clauses, export and draft operations.
- src/components/drafting/RichEditor.tsx and RichEditor.web.tsx: native editor and explicit web HTML-source fallback.
- src/app/finance/: dashboard, lists, forms, detail/confirmation/reversal/correction screens, agreement editing and reports.
- src/services/drafting-api.ts and finance-api.ts: API contracts; services/api.ts supports authenticated CSV downloads.
- Existing practice-tools entry routes, dashboard actions/home, client and case detail screens, root account-cache boundary and English/Malayalam locale files are integrated.

## Verification

The backend suite passes 14 tests, including auth/workspace, earlier hearing/diary/document/planning checks and the new financial/drafting workflows. There is an existing Starlette/httpx deprecation warning. Mobile TypeScript and lint pass; Expo Doctor passes all 20 checks. Expo Android Metro/Hermes export succeeds. New migrations were run from an older finance schema containing an existing payment and from an existing draft schema in temporary SQLite databases; both preserved existing records. PostgreSQL is unavailable here, so deployment migration verification remains necessary.

Actual Malayalam invoice, receipt and draft PDFs were generated, rendered to PNG and visually inspected. Noto Serif Malayalam font data is embedded. Multi-page output and explicit page breaks were checked. DOCX output was opened as an OOXML archive and checked for Unicode text, formatting and tables. The PDF font check is reproducible in test_document_workflows.py. Local inspection samples are in court-assist-backend/tmp/pdfs/ (ignored diagnostic output).

## Setup

1. Install updated backend requirements. New packages are python-docx and bleach[css]; PyMuPDF was already used by the application.
2. Back up the configured deployment database, run alembic upgrade head, and restart the API. The current head is 0016_finance_metadata.
3. Configure the existing private S3 bucket/endpoint/region/access credentials, size limit and signed-URL expiration. No new secrets or AI provider settings are introduced.
4. Install mobile dependencies from the lockfile and rebuild the development client for react-native-webview. Android production signing and deployment remain part of your existing deployment process.
5. Use Drafting/Finance from home or client/case shortcuts. Apply report filters before exports. Issue an invoice before generating its historical PDF; confirm actual received funds before generating a receipt.

## Practical limits

Real PostgreSQL/S3 integration and native device behavior still require deployment/device checks; storage tests use an in-memory S3 replacement. Web editing deliberately exposes HTML source rather than a visual editor. Native formatting supports the documented HTML subset and basic tables, not arbitrary Word layout. DOCX requires a Malayalam-capable viewer font (Nirmala UI is selected); DOCX font embedding and identical Word/PDF pagination are not claimed. Autosave cannot guarantee preservation after forced app termination before the server accepts a save, and offline synchronization is outside scope. One issued invoice per agreement prevents duplicate settlement attribution; standalone invoices do not automatically match unallocated payments. Monetary APIs currently restrict currencies to INR to avoid mixed-currency sums.

The implementation does not extend the legal research or AI modules.
