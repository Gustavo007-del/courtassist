from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AccountErasure(Base):
    __tablename__ = "account_erasures"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # Cleared after purge, so the remaining receipt no longer identifies the account.
    user_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

