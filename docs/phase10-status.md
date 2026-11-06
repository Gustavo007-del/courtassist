# Phase 10 drafting

The drafting workspace extends the existing records. Open Drafting from the home actions or Practice tools. Cases and clients have creation shortcuts. The five main tabs remain intact.

## Editor and library

Android/iOS editing uses SDK-compatible react-native-webview with a local HTML editor. It supports headings, paragraphs, bold/italic/underline, lists, alignment, undo/redo, page breaks, and editable basic tables. Scripts, external resources and navigation are restricted. HTML is sanitized to a documented tag/style subset for previews and exports; source content is not executed as a template. Pasted material is inserted as plain text. The web fallback exposes HTML source rather than the native visual editor.

The template and clause screens support search, categories, creation, editing and preview. Templates can be duplicated and archived. Built-in outlines are private-data-free structural examples, visibly marked as unverified forms; they contain no invented law or procedural instructions. A clause is copied into a draft, so later library changes cannot alter it. Eleven outline categories are seeded by migration 0014.

Drafts support standalone or case/client-linked records, title/category/language/status, search, archive/restore, and duplication. The editor saves after 1.6 seconds without an edit, serializes save requests, attempts a save when leaving the foreground, and prompts before navigating away with unsaved content. Failed saves keep edits in the editor. Each save sends the last server revision; stale edits receive HTTP 409 instead of silently overwriting another edit. A force-terminated app or unavailable network can still lose edits not yet accepted by the server; offline synchronization is outside this phase.

## Placeholders and versions

Templates use literal `{{advocate.name}}`, `{{client.name}}`, `{{case.number}}`, `{{case.cnr}}`, `{{case.title}}`, `{{court.name}}`, `{{court.location}}`, `{{case.filing_date}}`, `{{party.names}}`, `{{party.roles}}`, `{{petitioner.details}}`, `{{respondent.details}}`, and arbitrary advocate-defined names. Petitioner/respondent autofill requires the stored party role to match that label; other roles are never inferred. Hearing and document-specific dates remain manual values. The autofill panel presents stored values and allows correction before insertion. Unfilled tokens remain visible. Only existing placeholders are replaced, preserving other edited content.

Content edits snapshot the previous content. Manual snapshots and explicit restoration are supported. Restoring preserves the previous content and creates a new restored snapshot. Version numbers are allocated while the draft is locked on PostgreSQL. Versions are retained and scoped through the owning draft. Save/archive/restore/version/export operations have an audit trail without recording content in application logs.

## Exports and storage

The editor exports A4 PDF and editable DOCX into the existing private vault, associated with the selected client/case. DraftExport retains each generated document reference and format; last_exported_at is updated. Downloads use existing short-lived signed URLs, never public objects. Generated files have randomized private keys, size checks, signature/checksum validation and a vault version/access log. Export history is available through the API and the resulting files through the vault.

PDF uses the existing PyMuPDF Story engine, with Unicode shaping and embedded fallback fonts. Actual Malayalam draft, invoice and receipt samples were generated, rendered to PNG and inspected. Tests verify embedded Noto Serif Malayalam font data and PDF content; no external font download is required with the verified PyMuPDF build. DOCX uses python-docx and preserves Unicode, headings, inline formatting, lists, basic tables and page breaks. The document font is Nirmala UI; Word or another viewer needs a Malayalam-capable font. DOCX font embedding and pixel-identical DOCX/PDF pagination are not claimed. Merged/complex tables are outside the editor's basic table subset.

## Setup and API

Install updated backend requirements (python-docx and bleach[css] added), run `alembic upgrade head`, and restart the backend. Apply through revision 0016 for the complete current workspace. Rebuild the mobile development client after installing react-native-webview through Expo. No AI credentials or new environment variables are needed. Configure the existing private S3 settings before exporting.

Existing /api/v1 routes cover draft-templates CRUD/duplicate; draft-documents CRUD/duplicate/archive/restore; versions list/manual snapshot/restore; autofill preview; export, export history and audit; and draft-clauses CRUD. List routes support bounded pagination and search; drafts/templates/clauses support category filtering. The native editor remains subject to a real-device usability pass.

Verification: backend workflow/security tests, native TypeScript/lint checks, Android Metro/Hermes export, and actual PDF render inspection. See phase10-11-handover.md for the final check results and file inventory.
