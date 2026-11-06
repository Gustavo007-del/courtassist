from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models.phase10 import FeeAgreement, Payment, Expense
from app.models.finance import FinancialAdjustment
from app.models.user import UserPreference


def business_today(db, user_id):
    preferences = db.get(UserPreference, user_id)
    try:
        zone = ZoneInfo(preferences.timezone if preferences else "Asia/Kolkata")
    except (ValueError, KeyError):
        zone = ZoneInfo("Asia/Kolkata")
    return datetime.now(zone).date()


def summary(db, user_id, from_date=None, to_date=None, client_id=None, case_id=None):
    def rows(model, date_column):
        query = select(model).where(model.user_id == user_id)
        if from_date:
            query = query.where(date_column >= from_date)
        if to_date:
            query = query.where(date_column <= to_date)
        if client_id:
            query = query.where(model.client_id == client_id)
        if case_id:
            query = query.where(model.case_id == case_id)
        return db.scalars(query).all()

    payments = rows(Payment, Payment.payment_date)
    expenses = [
        row for row in rows(Expense, Expense.expense_date) if row.status == "confirmed"
    ]
    agreements = rows(FeeAgreement, FeeAgreement.agreement_date)
    received = sum((p.amount for p in payments if p.status == "received"), Decimal(0))
    expense_ids = {e.id for e in expenses}
    corrections = (
        db.scalars(
            select(FinancialAdjustment).where(
                FinancialAdjustment.user_id == user_id,
                FinancialAdjustment.expense_id.in_(expense_ids),
            )
        ).all()
        if expense_ids
        else []
    )
    expense_total = sum((e.amount for e in expenses), Decimal(0)) + sum(
        (a.amount for a in corrections), Decimal(0)
    )
    outstanding = Decimal(0)
    # A period selects agreements; the balance includes their lifetime valid payments.
    for agreement in agreements:
        if agreement.status != "active":
            continue
        valid = db.scalars(
            select(Payment).where(
                Payment.user_id == user_id,
                Payment.agreement_id == agreement.id,
                Payment.status == "received",
            )
        ).all()
        outstanding += max(
            Decimal(0), agreement.amount - sum((p.amount for p in valid), Decimal(0))
        )
    values = {
        "agreed_fees": sum(
            (a.amount for a in agreements if a.status != "cancelled"), Decimal(0)
        ),
        "received": received,
        "outstanding": outstanding,
        "expenses": expense_total,
        "net_cash_flow": received - expense_total,
        "pending_payments": sum(
            (p.amount for p in payments if p.status == "pending"), Decimal(0)
        ),
    }
    return {key: format(value, ".2f") for key, value in values.items()}


def report(
    db,
    user_id,
    from_date=None,
    to_date=None,
    client_id=None,
    case_id=None,
    method=None,
    category=None,
):
    def query(model, column):
        stmt = select(model).where(model.user_id == user_id)
        if from_date:
            stmt = stmt.where(column >= from_date)
        if to_date:
            stmt = stmt.where(column <= to_date)
        if client_id:
            stmt = stmt.where(model.client_id == client_id)
        if case_id:
            stmt = stmt.where(model.case_id == case_id)
        return stmt

    ps = query(Payment, Payment.payment_date)
    es = query(Expense, Expense.expense_date).where(Expense.status == "confirmed")
    if method:
        ps = ps.where(Payment.method == method)
    if category:
        es = es.where(Expense.category == category)
    payments = db.scalars(ps.order_by(Payment.payment_date.desc())).all()
    expenses = db.scalars(es.order_by(Expense.expense_date.desc())).all()
    ids = [row.id for row in expenses]
    adjustments = (
        db.scalars(
            select(FinancialAdjustment).where(
                FinancialAdjustment.user_id == user_id,
                FinancialAdjustment.expense_id.in_(ids),
            )
        ).all()
        if ids
        else []
    )
    corrected = {row.id: row.amount for row in expenses}
    for adjustment in adjustments:
        corrected[adjustment.expense_id] += adjustment.amount
    months = {}
    methods = {}
    categories = {}

    def month(key):
        return months.setdefault(key, {"income": Decimal(0), "expenses": Decimal(0)})

    for row in payments:
        if row.status != "received":
            continue
        month(row.payment_date.strftime("%Y-%m"))["income"] += row.amount
        methods[row.method] = methods.get(row.method, Decimal(0)) + row.amount
    for row in expenses:
        amount = corrected[row.id]
        month(row.expense_date.strftime("%Y-%m"))["expenses"] += amount
        categories[row.category] = categories.get(row.category, Decimal(0)) + amount
    fmt = lambda value: format(value, ".2f")
    income = sum(methods.values(), Decimal(0))
    cost = sum(categories.values(), Decimal(0))
    groups = {name: {} for name in ("by_client", "by_case")}
    for name, field in [("by_client", "client_id"), ("by_case", "case_id")]:
        for row in payments:
            key = str(getattr(row, field) or "unlinked")
            value = groups[name].setdefault(
                key,
                {
                    "received": Decimal(0),
                    "expenses": Decimal(0),
                    "outstanding": Decimal(0),
                },
            )
            if row.status == "received":
                value["received"] += row.amount
        for row in expenses:
            key = str(getattr(row, field) or "unlinked")
            value = groups[name].setdefault(
                key,
                {
                    "received": Decimal(0),
                    "expenses": Decimal(0),
                    "outstanding": Decimal(0),
                },
            )
            value["expenses"] += corrected[row.id]
        agreements = db.scalars(
            query(FeeAgreement, FeeAgreement.agreement_date).where(
                FeeAgreement.status == "active"
            )
        ).all()
        for agreement in agreements:
            valid = db.scalars(
                select(Payment).where(
                    Payment.user_id == user_id,
                    Payment.agreement_id == agreement.id,
                    Payment.status == "received",
                )
            ).all()
            key = str(getattr(agreement, field) or "unlinked")
            value = groups[name].setdefault(
                key,
                {
                    "received": Decimal(0),
                    "expenses": Decimal(0),
                    "outstanding": Decimal(0),
                },
            )
            value["outstanding"] += max(
                Decimal(0),
                agreement.amount - sum((p.amount for p in valid), Decimal(0)),
            )
    annual = {}
    for key, value in months.items():
        year = annual.setdefault(
            key[:4], {"income": Decimal(0), "expenses": Decimal(0)}
        )
        year["income"] += value["income"]
        year["expenses"] += value["expenses"]
    return {
        **{
            name: {
                key: {metric: fmt(amount) for metric, amount in value.items()}
                for key, value in group.items()
            }
            for name, group in groups.items()
        },
        "annual": {
            key: {metric: fmt(amount) for metric, amount in value.items()}
            for key, value in annual.items()
        },
        "summary": {
            **summary(db, user_id, from_date, to_date, client_id, case_id),
            "received": fmt(income),
            "expenses": fmt(cost),
            "net_cash_flow": fmt(income - cost),
            "pending_payments": fmt(
                sum((p.amount for p in payments if p.status == "pending"), Decimal(0))
            ),
        },
        "monthly": [
            {
                "month": key,
                "income": fmt(value["income"]),
                "expenses": fmt(value["expenses"]),
                "net_cash_flow": fmt(value["income"] - value["expenses"]),
            }
            for key, value in sorted(months.items())
        ],
        "by_method": {key: fmt(value) for key, value in methods.items()},
        "by_category": {key: fmt(value) for key, value in categories.items()},
        "payments": [
            {
                "id": str(row.id),
                "date": str(row.payment_date),
                "client_id": str(row.client_id),
                "case_id": str(row.case_id) if row.case_id else None,
                "amount": fmt(row.amount),
                "method": row.method,
                "status": row.status,
            }
            for row in payments
        ],
        "expenses": [
            {
                "id": str(row.id),
                "date": str(row.expense_date),
                "client_id": str(row.client_id) if row.client_id else None,
                "case_id": str(row.case_id) if row.case_id else None,
                "amount": fmt(corrected[row.id]),
                "original_amount": fmt(row.amount),
                "category": row.category,
            }
            for row in expenses
        ],
    }


def report_rows(values):
    rows = [(key.replace("_", " "), value) for key, value in values["summary"].items()]
    for row in values["monthly"]:
        rows.extend(
            (row["month"] + " " + metric, row[metric])
            for metric in ("income", "expenses", "net_cash_flow")
        )
    for name in ("by_method", "by_category"):
        rows.extend((name + " " + key, value) for key, value in values[name].items())
    for name in ("by_client", "by_case", "annual"):
        for key, value in values[name].items():
            rows.extend(
                (name + " " + key + " " + metric, amount)
                for metric, amount in value.items()
            )
    rows.extend(
        (
            "Payment "
            + row["date"]
            + " "
            + row["id"]
            + " "
            + row["status"]
            + " "
            + row["method"],
            row["amount"],
        )
        for row in values["payments"]
    )
    rows.extend(
        (
            "Expense " + row["date"] + " " + row["id"] + " " + row["category"],
            row["amount"],
        )
        for row in values["expenses"]
    )
    return rows
