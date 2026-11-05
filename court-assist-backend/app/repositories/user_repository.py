from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User


def by_identifier(db: Session, identifier: str) -> User | None:
    column = User.email if '@' in identifier else User.phone_number
    return db.scalar(select(User).where(column == identifier))
