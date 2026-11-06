from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas.practice import Input, Money


class Line(Input):
    description: Annotated[str, Field(min_length=1, max_length=500)]
    quantity: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)] = Decimal(
        "1"
    )
    unit_price: Money


class InvoiceInput(Input):
    client_id: UUID
    case_id: UUID | None = None
    agreement_id: UUID | None = None
    issue_date: date = Field(default_factory=date.today)
    due_date: date | None = None
    terms: Annotated[str, Field(max_length=5000)] = ""
    lines: list[Line] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def dates(self):
        if self.due_date and self.due_date < self.issue_date:
            raise ValueError("Due date precedes issue date")
        return self


class PaymentMetadata(Input):
    reference: Annotated[str, Field(max_length=120)]


class ExpenseMetadata(Input):
    description: Annotated[str, Field(max_length=5000)]
    category: Annotated[str, Field(min_length=1, max_length=80)]


class AgreementChange(Input):
    amount: Money
    description: Annotated[str, Field(max_length=5000)]
    status: Literal["draft", "active", "completed", "closed", "cancelled"]
    reason: Annotated[str, Field(max_length=2000)] = ""
