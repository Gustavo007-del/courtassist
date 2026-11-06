import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    CheckConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class FinancialAdjustment(Base):
    __tablename__ = "financial_adjustments"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("payments.id"), index=True
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("expenses.id"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    __table_args__ = (
        CheckConstraint(
            "(payment_id IS NOT NULL AND expense_id IS NULL) OR (payment_id IS NULL AND expense_id IS NOT NULL)",
            name="ck_adjustment_target",
        ),
    )


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id"))
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("cases.id"))
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fee_agreements.id")
    )
    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    issue_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(Date)
    terms: Mapped[str] = mapped_column(Text, default="")
    lines: Mapped[list] = mapped_column(JSON, default=list)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("documents.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("payments.id"), unique=True
    )
    number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("documents.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AgreementHistory(Base):
    __tablename__ = "fee_agreement_history"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    agreement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fee_agreements.id"), index=True
    )
    previous: Mapped[dict] = mapped_column(JSON)
    current: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text, default="Metadata update")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
