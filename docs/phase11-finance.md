# Phase 11 finance

Open Finance from home, Practice tools, or the client/case shortcuts. The module includes filtered cash summaries, agreement/payment/expense/invoice lists and forms, record details, explicit confirmation/reversal/expense adjustment controls, invoice issue/cancel/PDF preview, receipt download, and report/export screens. English/Malayalam labels are supplied. Financial amounts are sent and displayed as decimal strings.

## Records and audit

The original FeeAgreement, Payment and Expense records are extended rather than duplicated. Agreement metadata includes title, arrangement, terms and notes. Payments retain description, notes, references and generated receipt number. Expenses support method, vendor, reference, notes, private supporting document link, explicit draft/confirmed state and archiving. Existing expenses migrate to confirmed status. Draft expenses are excluded from cash totals; confirmed expenses cannot be silently deleted or have their amount edited. Corrections append FinancialAdjustment records. Archiving retains the expense in financial totals.

Payment confirmation and reversal lock the original row and append actor/reason/timestamp history. Only pending payments can be confirmed; only received payments can be reversed, once. Payment amounts are never overwritten. Payment creation requires an Idempotency-Key; retries with the same payload reuse the original record and conflicting payloads return 409. Metadata edits to confirmed payments are rejected; issued receipt content remains immutable. Agreement edits retain before/after history and require a reason and explicit confirmation when an amount is changed after payments exist.

Invoices store line items, decimal totals, dates, terms and an issued snapshot. Each line rounds quantity times price to two decimals with ROUND_HALF_UP; totals sum those rounded lines. Issued invoices cannot be edited; cancel and replace them. To avoid attributing one payment to several invoices, only one invoice may be issued per agreement at a time. Settlement status derives from that agreement's confirmed payments. Standalone invoices do not infer settlement from unallocated client payments; use an agreement-linked invoice for payment tracking. There is no manual paid switch. Receipts are generated once per confirmed received payment, preserve the original snapshot, and remain historical records after reversal; current payment status is returned alongside a receipt download.

## Calculation rules

All calculations run on the backend with Decimal/NUMERIC arithmetic and INR currency validation. Agreed fees are separate from cash. Pending/failed/reversed payments are excluded from received income. Each active agreement has its own max(agreed fee minus lifetime received payments, 0) balance; overpayment on one agreement does not reduce another. Unallocated payments count as cash but do not reduce agreement balances. Net cash equals received payments minus confirmed expenses including corrections.

Date filters are inclusive business dates, not ambiguous UTC-midnight timestamps. Default backend business dates use the advocate's configured timezone. Expense corrections restate the original expense period. A date filter selects agreements by agreement date, while their remaining balance uses lifetime confirmed payments. Method filters apply to payment data; category filters apply to expenses. Client/case groups account for each selected transaction once. Annual and monthly groups use the same filtered transactions.

## Reports and export

`GET /finance/reports`, `/finance/income-report`, `/finance/expense-report` and `/finance/cash-flow` include summary metrics, monthly and annual groups, received amounts by method, expenses by category, client/case groups, and transaction histories. Date/client/case/method/category filters are supported. `/finance/summary` provides concise metrics. Context routes `/clients/{id}/financial-summary` and `/cases/{id}/financial-summary` validate ownership. Outstanding and client/case report routes are also available.

`GET /finance/export` produces CSV using the same calculation service. `POST /finance/report-pdf` creates a private vault PDF. Issued invoice PDFs and confirmed receipt PDFs use immutable snapshots and the existing storage/version/access-log infrastructure; authorized downloads use short-lived signed URLs. Actual English/Malayalam PDFs were generated and visually checked, with Noto Serif Malayalam embedded by PyMuPDF. This phase performs manual record keeping; it collects no real money and has no payment gateway.

## Migration and setup

Run `alembic upgrade head` after updating backend requirements. Revisions 0012 through 0016 add financial documents, drafting exports/outlines, agreement audit history and financial metadata. No previous table is dropped in the PostgreSQL upgrade path. Existing private storage variables remain DOCUMENT_S3_BUCKET, DOCUMENT_S3_REGION, DOCUMENT_S3_ENDPOINT (where needed), DOCUMENT_S3_ACCESS_KEY, DOCUMENT_S3_SECRET_KEY, DOCUMENT_MAX_BYTES and DOCUMENT_URL_SECONDS. Keep them server-side and deny public bucket access. Mobile still uses EXPO_PUBLIC_API_URL.

The new migrations were exercised with a legacy SQLite schema containing an existing payment and with an existing draft. Existing records and money values were preserved. PostgreSQL and real S3 integration require deployment verification because neither service is configured in this workspace. Device notification/payment-gateway functionality is not part of this change. Native editor and OS download/share behavior need a real device pass. The dependency/build checks do not substitute for that pass.

## Verification

Run `.venv\Scripts\python.exe -m pytest -q` from the backend, and `npm run typecheck`, `npm run lint` and `npx expo export --platform android --output-dir dist-check` from mobile. Tests cover decimal arithmetic, status exclusion, reversals, expense correction, agreement change history, invoices, receipts, idempotency, private generated documents, ownership, draft revisions, and Malayalam PDF/font checks. See phase10-11-handover.md for the final results.
