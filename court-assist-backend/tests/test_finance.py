import os
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-with-at-least-32-chars")
from app import models
from app.database.base import Base
from app.models.phase10 import FeeAgreement, Payment, Expense
from app.api.v1.finance import reverse_payment, adjust_expense, Reason, Adjustment
from app.services.finance_service import summary


def test_cash_balances_reversal_correction_and_ownership():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    owner, other, client = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=owner)
    with Session(engine) as db:
        agreement = FeeAgreement(
            user_id=owner,
            client_id=client,
            amount=Decimal("1000.10"),
            agreement_date=date(2026, 1, 1),
            status="active",
        )
        db.add(agreement)
        db.flush()
        payment = Payment(
            user_id=owner,
            client_id=client,
            agreement_id=agreement.id,
            amount=Decimal("100.05"),
            payment_date=date(2026, 2, 1),
            status="received",
        )
        pending = Payment(
            user_id=owner,
            client_id=client,
            amount=Decimal("50.05"),
            payment_date=date(2026, 2, 1),
            status="pending",
        )
        expense = Expense(
            user_id=owner, amount=Decimal("20.01"), expense_date=date(2026, 2, 1)
        )
        db.add_all([payment, pending, expense])
        db.commit()
        totals = summary(db, owner)
        assert totals["received"] == "100.05" and totals["outstanding"] == "900.05"
        assert totals["net_cash_flow"] == "80.04"
        assert summary(db, other)["received"] == "0.00"
        assert (
            summary(db, owner, date(2026, 3, 1), date(2026, 3, 31))["received"]
            == "0.00"
        )
        with pytest.raises(HTTPException) as denied:
            reverse_payment(
                payment.id,
                Reason(reason="Incorrect entry"),
                SimpleNamespace(id=other),
                db,
            )
        assert denied.value.status_code == 404
        reverse_payment(payment.id, Reason(reason="Incorrect entry"), user, db)
        assert summary(db, owner)["received"] == "0.00"
        assert summary(db, owner)["outstanding"] == "1000.10"
        with pytest.raises(HTTPException):
            reverse_payment(payment.id, Reason(reason="Repeated reversal"), user, db)
        adjust_expense(
            expense.id,
            Adjustment(reason="Correct receipt amount", amount=Decimal("-5.01")),
            user,
            db,
        )
        assert expense.amount == Decimal("20.01")
        assert summary(db, owner)["expenses"] == "15.00"
        with pytest.raises(HTTPException):
            adjust_expense(
                expense.id,
                Adjustment(reason="Invalid overcorrection", amount=Decimal("-16")),
                user,
                db,
            )
