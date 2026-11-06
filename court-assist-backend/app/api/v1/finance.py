from decimal import Decimal
from datetime import date
import csv
import io
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.api.v1.phase10 import owned, dump, validate_links
from app.database.session import get_db
from app.models.user import User
from app.models.phase10 import Payment, Expense, FeeAgreement
from app.models.finance import FinancialAdjustment, Invoice, Receipt, AgreementHistory
from app.schemas.finance import (
    InvoiceInput,
    PaymentMetadata,
    ExpenseMetadata,
    AgreementChange,
)
from app.services.finance_documents import total, publish
from app.services.document_storage import presigned_get
from app.models.document import Document, DocumentAccessLog
import uuid
from app.schemas.practice import Input
from app.services.finance_service import summary, report, report_rows, business_today
from app.models.client import Client
from app.models.case import Case

router = APIRouter(tags=["finance"])


def invoice_data(db, row):
    result = dump(row)
    if row.status == "issued" and row.agreement_id:
        paid = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.user_id == row.user_id,
                Payment.agreement_id == row.agreement_id,
                Payment.status == "received",
            )
        )
        result["status"] = (
            "paid" if paid >= row.total else "partially_paid" if paid > 0 else "issued"
        )
    return result


def snapshot_for(
    db,
    user,
    client_id,
    case_id,
    kind,
    number,
    business_date,
    rows,
    amount,
    terms="",
    status="",
):
    client = owned(db, Client, client_id, user)
    case = owned(db, Case, case_id, user) if case_id else None
    address = " · ".join(
        str(value)
        for value in (
            user.office_address or user.address,
            user.office_phone or user.phone_number,
            user.professional_email or user.email,
            user.enrollment_number,
        )
        if value
    )
    return {
        "kind": kind,
        "number": number,
        "advocate": user.full_name,
        "address": address,
        "client": client.full_name + " · " + client.address,
        "case": case.case_title + " · " + case.case_number if case else "",
        "date": str(business_date),
        "rows": rows,
        "total": str(amount),
        "terms": terms,
        "status": status,
    }


@router.get("/invoices")
def invoices(
    q: str = "",
    client_id: UUID | None = None,
    case_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, "Invalid pagination")
    query = select(Invoice).where(Invoice.user_id == user.id)
    if client_id:
        query = query.where(Invoice.client_id == client_id)
    if case_id:
        query = query.where(Invoice.case_id == case_id)
    if q:
        query = query.where(
            Invoice.number.ilike(f"%{q[:200]}%") | Invoice.status.ilike(f"%{q[:200]}%")
        )
    return [
        invoice_data(db, row)
        for row in db.scalars(
            query.order_by(Invoice.created_at.desc()).offset(offset).limit(limit)
        )
    ]


@router.post("/invoices", status_code=201)
def create_invoice(
    data: InvoiceInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if "issue_date" not in data.model_fields_set:
        data.issue_date = business_today(db, user.id)
    validate_links(db, user, data.model_dump())
    lines = [line.model_dump(mode="json") for line in data.lines]
    amount = total(lines)
    if amount > Decimal("999999999999.99"):
        raise HTTPException(422, "Invoice total exceeds limit")
    row = Invoice(
        user_id=user.id,
        number="INV-" + uuid.uuid4().hex.upper(),
        total=amount,
        **data.model_dump(exclude={"lines"}),
        lines=lines,
    )
    db.add(row)
    db.commit()
    return invoice_data(db, row)


@router.get("/invoices/{rid}")
def invoice_detail(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return invoice_data(db, owned(db, Invoice, rid, user))


@router.patch("/invoices/{rid}")
def edit_invoice(
    rid: UUID,
    data: InvoiceInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = owned(db, Invoice, rid, user)
    if row.status != "draft":
        raise HTTPException(
            409, "Issued invoice details are immutable; cancel and replace it"
        )
    validate_links(db, user, data.model_dump())
    lines = [line.model_dump(mode="json") for line in data.lines]
    amount = total(lines)
    if amount > Decimal("999999999999.99"):
        raise HTTPException(422, "Invoice total exceeds limit")
    for key, value in data.model_dump(exclude={"lines"}).items():
        setattr(row, key, value)
    row.lines = lines
    row.total = amount
    db.commit()
    return invoice_data(db, row)


@router.post("/invoices/{rid}/issue")
def issue_invoice(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = db.scalar(
        select(Invoice)
        .where(Invoice.id == rid, Invoice.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Invoice not found")
    if row.status != "draft":
        raise HTTPException(409, "Invoice is not a draft")
    if row.agreement_id:
        agreement = db.scalar(
            select(FeeAgreement)
            .where(FeeAgreement.id == row.agreement_id, FeeAgreement.user_id == user.id)
            .with_for_update()
        )
        if not agreement:
            raise HTTPException(404, "Agreement not found")
        other = db.scalar(
            select(Invoice.id).where(
                Invoice.user_id == user.id,
                Invoice.agreement_id == row.agreement_id,
                Invoice.status == "issued",
                Invoice.id != row.id,
            )
        )
        if other:
            raise HTTPException(409, "This agreement already has an issued invoice")
    row.snapshot = snapshot_for(
        db,
        user,
        row.client_id,
        row.case_id,
        "Invoice",
        row.number,
        row.issue_date,
        [
            (line["description"] + " (" + line["quantity"] + " × INR " + line["unit_price"] + ")", str(total([line])))
            for line in row.lines
        ],
        row.total,
        ("Due date: " + str(row.due_date) + ". " if row.due_date else "") + row.terms,
        "Issued",
    )
    row.status = "issued"
    db.commit()
    return invoice_data(db, row)


@router.post("/invoices/{rid}/cancel")
def cancel_invoice(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = owned(db, Invoice, rid, user)
    row.status = "cancelled"
    db.commit()
    return invoice_data(db, row)


def private_link(db, row, user):
    doc = owned(db, Document, row.document_id, user)
    db.add(DocumentAccessLog(document_id=doc.id,user_id=user.id,action='download_authorized'))
    db.commit()
    return {
        "document_id": str(doc.id),
        "url": presigned_get(doc.storage_key, doc.original_filename),
    }


@router.get("/invoices/{rid}/pdf")
def invoice_pdf(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = db.scalar(
        select(Invoice)
        .where(Invoice.id == rid, Invoice.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Invoice not found")
    if not row.snapshot:
        raise HTTPException(409, "Issue the invoice before generating its PDF")
    if not row.document_id:
        doc = publish(db, user.id, row.snapshot, row.case_id, row.client_id)
        row.document_id = doc.id
        db.commit()
    return private_link(db, row, user)


@router.get("/payments/{rid}/receipt")
def payment_receipt(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == rid, Payment.user_id == user.id)
        .with_for_update()
    )
    if not payment:
        raise HTTPException(404, "Payment not found")
    row = db.scalar(
        select(Receipt).where(Receipt.payment_id == rid, Receipt.user_id == user.id)
    )
    if not row:
        if payment.status != "received":
            raise HTTPException(
                409, "Only confirmed received payments can generate receipts"
            )
        number = "RCT-" + uuid.uuid4().hex.upper()
        snapshot = snapshot_for(
            db,
            user,
            payment.client_id,
            payment.case_id,
            "Payment receipt",
            number,
            payment.payment_date,
            [(payment.method + " · " + payment.reference, str(payment.amount))],
            payment.amount,
            terms="Fee agreement: " + str(payment.agreement_id) if payment.agreement_id else "",
            status="Received",
        )
        doc = publish(db, user.id, snapshot, payment.case_id, payment.client_id)
        row = Receipt(
            user_id=user.id,
            payment_id=rid,
            number=number,
            snapshot=snapshot,
            document_id=doc.id,
        )
        db.add(row)
        payment.receipt_number = number
        db.commit()
    return {
        **private_link(db, row, user),
        "number": row.number,
        "payment_status": payment.status,
    }


@router.patch("/payments/{rid}")
def edit_payment_metadata(
    rid: UUID,
    data: PaymentMetadata,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(Payment).where(Payment.id == rid, Payment.user_id == user.id).with_for_update())
    if row is None:
        raise HTTPException(404, "Record not found")
    if row.status == "received" or row.status == "reversed":
        raise HTTPException(409, "Confirmed payment records are immutable")
    row.reference = data.reference
    db.commit()
    return dump(row)


@router.patch("/expenses/{rid}")
def edit_expense_metadata(
    rid: UUID,
    data: ExpenseMetadata,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = owned(db, Expense, rid, user)
    # Retain original metadata and the stated correction reason in the audit ledger.
    db.add(
        FinancialAdjustment(
            user_id=user.id,
            expense_id=rid,
            amount=Decimal("0"),
            kind="metadata",
            reason="Previous category: "
            + row.category
            + "; previous description: "
            + row.description,
        )
    )
    row.description = data.description
    row.category = data.category
    db.commit()
    return dump(row)


@router.get("/fee-agreements/{rid}/payments")
def agreement_payments(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, FeeAgreement, rid, user)
    return [
        dump(row)
        for row in db.scalars(
            select(Payment)
            .where(Payment.user_id == user.id, Payment.agreement_id == rid)
            .order_by(Payment.payment_date.desc())
        )
    ]


@router.patch("/fee-agreements/{rid}")
def change_agreement(
    rid: UUID,
    data: AgreementChange,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(FeeAgreement)
        .where(FeeAgreement.id == rid, FeeAgreement.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Agreement not found")
    has_payments = db.scalar(
        select(Payment.id)
        .where(Payment.user_id == user.id, Payment.agreement_id == rid)
        .limit(1)
    )
    if has_payments and row.amount != data.amount and len(data.reason.strip()) < 3:
        raise HTTPException(
            422,
            "Changing agreed fees after payments requires a reason and explicit confirmation",
        )
    previous = {
        "amount": str(row.amount),
        "description": row.description,
        "status": row.status,
    }
    row.amount = data.amount
    row.description = data.description
    row.status = data.status
    db.add(
        AgreementHistory(
            user_id=user.id,
            agreement_id=rid,
            previous=previous,
            current={
                "amount": str(row.amount),
                "description": row.description,
                "status": row.status,
            },
            reason=data.reason or "Metadata update",
        )
    )
    db.commit()
    return dump(row)


@router.get("/fee-agreements/{rid}/history")
def agreement_history(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, FeeAgreement, rid, user)
    return [
        dump(row)
        for row in db.scalars(
            select(AgreementHistory)
            .where(
                AgreementHistory.user_id == user.id,
                AgreementHistory.agreement_id == rid,
            )
            .order_by(AgreementHistory.created_at.desc())
        )
    ]


@router.delete("/fee-agreements/{rid}")
def cancel_agreement(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = owned(db, FeeAgreement, rid, user)
    return change_agreement(
        rid,
        AgreementChange(
            amount=row.amount,
            description=row.description,
            status="cancelled",
            reason="Advocate cancelled the fee agreement",
        ),
        user,
        db,
    )


@router.get("/finance/cash-flow")
@router.get("/finance/income-report")
@router.get("/finance/expense-report")
@router.get("/finance/reports")
def financial_report(
    from_date: date | None = None,
    to_date: date | None = None,
    client_id: UUID | None = None,
    case_id: UUID | None = None,
    method: str | None = None,
    category: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Invalid date range")
    return report(db, user.id, from_date, to_date, client_id, case_id, method, category)


@router.get("/clients/{rid}/financial-summary")
def client_finances(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, Client, rid, user)
    return summary(db, user.id, client_id=rid)


@router.get("/cases/{rid}/financial-summary")
def case_finances(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, Case, rid, user)
    return summary(db, user.id, case_id=rid)


@router.get("/finance/outstanding")
def outstanding_clients(
    from_date: date | None = None,
    to_date: date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Invalid date range")
    return report(db, user.id, from_date, to_date)["by_client"]


@router.get("/finance/client-summary")
def client_report(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return report(db, user.id)["by_client"]


@router.get("/finance/case-summary")
def case_report(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return report(db, user.id)["by_case"]


@router.get("/finance/export")
def export_finances(
    from_date: date | None = None,
    to_date: date | None = None,
    client_id: UUID | None = None,
    case_id: UUID | None = None,
    method: str | None = None,
    category: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Invalid date range")
    values = report(
        db, user.id, from_date, to_date, client_id, case_id, method, category
    )
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Metric or transaction", "INR"])
    for key, value in report_rows(values):
        writer.writerow(
            ["'" + key if key.startswith(("=", "+", "-", "@")) else key, value]
        )
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="financial-summary.csv"',
            "Cache-Control": "no-store",
        },
    )


class Reason(Input):
    reason: Annotated[str, Field(min_length=3, max_length=2000)]


@router.post("/finance/report-pdf")
def report_pdf(
    from_date: date | None = None,
    to_date: date | None = None,
    client_id: UUID | None = None,
    case_id: UUID | None = None,
    method: str | None = None,
    category: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "Invalid date range")
    validate_links(db, user, {"client_id": client_id, "case_id": case_id})
    values = report(
        db, user.id, from_date, to_date, client_id, case_id, method, category
    )
    snapshot = {
        "kind": "Financial report",
        "number": "REPORT-" + uuid.uuid4().hex.upper(),
        "advocate": user.full_name,
        "address": user.office_address or user.address,
        "client": "",
        "case": "",
        "date": f"{from_date or 'All dates'} to {to_date or 'present'}",
        "rows": report_rows(values),
        "total": values["summary"]["net_cash_flow"],
        "terms": "INR. Received payments exclude pending, failed and reversed records.",
        "status": "Generated from recorded transactions",
    }
    doc = publish(db, user.id, snapshot, case_id, client_id)
    db.commit()
    return {
        "document_id": str(doc.id),
        "url": presigned_get(doc.storage_key, doc.original_filename),
    }


class Adjustment(Reason):
    amount: Annotated[
        Decimal, Field(max_digits=14, decimal_places=2, allow_inf_nan=False)
    ]


@router.post("/payments/{rid}/confirm")
def confirm_payment(
    rid: UUID,
    data: Reason,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(Payment)
        .where(Payment.id == rid, Payment.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Payment not found")
    if row.status != "pending":
        raise HTTPException(409, "Only pending payments may be confirmed")
    db.add(
        FinancialAdjustment(
            user_id=user.id,
            payment_id=rid,
            amount=Decimal(0),
            kind="confirmation",
            reason=data.reason,
        )
    )
    row.status = "received"
    db.commit()
    return dump(row)


@router.post("/expenses/{rid}/confirm")
def confirm_expense(
    rid: UUID,
    data: Reason,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(Expense)
        .where(Expense.id == rid, Expense.user_id == user.id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Expense not found")
    if row.status != "draft":
        raise HTTPException(409, "Only draft expenses may be confirmed")
    db.add(
        FinancialAdjustment(
            user_id=user.id,
            expense_id=rid,
            amount=Decimal(0),
            kind="confirmation",
            reason=data.reason,
        )
    )
    row.status = "confirmed"
    db.commit()
    return dump(row)


@router.post("/expenses/{rid}/archive")
def archive_expense(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    from datetime import datetime, timezone

    row = owned(db, Expense, rid, user)
    row.archived_at = datetime.now(timezone.utc)
    db.commit()
    return dump(row)


@router.delete("/expenses/{rid}")
def delete_draft_expense(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    row = owned(db, Expense, rid, user)
    if row.status != "draft":
        raise HTTPException(
            409, "Confirmed expenses must be corrected or archived, not deleted"
        )
    return archive_expense(rid, user, db)


@router.post("/payments/{rid}/reverse")
def reverse_payment(
    rid: UUID,
    data: Reason,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    payment = db.scalar(
        select(Payment)
        .where(Payment.id == rid, Payment.user_id == user.id)
        .with_for_update()
    )
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.status != "received":
        raise HTTPException(409, "Only a received payment can be reversed")
    db.add(
        FinancialAdjustment(
            user_id=user.id,
            payment_id=rid,
            amount=-payment.amount,
            kind="reversal",
            reason=data.reason,
        )
    )
    payment.status = "reversed"
    db.commit()
    return dump(payment)


@router.get("/payments/{rid}/history")
def payment_history(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, Payment, rid, user)
    return [
        dump(row)
        for row in db.scalars(
            select(FinancialAdjustment)
            .where(
                FinancialAdjustment.payment_id == rid,
                FinancialAdjustment.user_id == user.id,
            )
            .order_by(FinancialAdjustment.created_at)
        ).all()
    ]


@router.post("/expenses/{rid}/adjust")
def adjust_expense(
    rid: UUID,
    data: Adjustment,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    expense = db.scalar(
        select(Expense)
        .where(Expense.id == rid, Expense.user_id == user.id)
        .with_for_update()
    )
    if not expense:
        raise HTTPException(404, "Expense not found")
    if expense.status != "confirmed":
        raise HTTPException(409, "Only confirmed expenses have ledger adjustments")
    current = expense.amount + (
        db.scalar(
            select(func.coalesce(func.sum(FinancialAdjustment.amount), 0)).where(
                FinancialAdjustment.expense_id == rid,
                FinancialAdjustment.user_id == user.id,
            )
        )
        or Decimal(0)
    )
    if data.amount == 0 or current + data.amount < 0:
        raise HTTPException(
            422, "Adjustment must be nonzero and cannot make the expense negative"
        )
    row = FinancialAdjustment(
        user_id=user.id,
        expense_id=rid,
        amount=data.amount,
        kind="correction",
        reason=data.reason,
    )
    db.add(row)
    db.commit()
    return dump(row)


@router.get("/expenses/{rid}/history")
def expense_history(
    rid: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    owned(db, Expense, rid, user)
    return [
        dump(row)
        for row in db.scalars(
            select(FinancialAdjustment)
            .where(
                FinancialAdjustment.expense_id == rid,
                FinancialAdjustment.user_id == user.id,
            )
            .order_by(FinancialAdjustment.created_at)
        ).all()
    ]
