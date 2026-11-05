from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.activity import Activity
from app.models.user import User


def record_activity(db: Session, user_id, activity_type: str, title: str,
                    description: str | None = None, entity_type: str | None = None,
                    entity_id=None, details: dict | None = None) -> Activity:
    activity = Activity(user_id=user_id, activity_type=activity_type, title=title,
                        description=description, entity_type=entity_type,
                        entity_id=entity_id, details=details or {})
    db.add(activity)
    return activity


def list_activities(db: Session, user: User, limit: int, offset: int,
                    activity_type: str | None = None, from_date: date | None = None,
                    to_date: date | None = None):
    filters = [Activity.user_id == user.id]
    if activity_type:
        filters.append(Activity.activity_type == activity_type)
    zone = ZoneInfo(user.preferences.timezone if user.preferences else 'Asia/Kolkata')
    if from_date:
        start = datetime.combine(from_date, time.min, zone).astimezone(timezone.utc)
        filters.append(Activity.created_at >= start)
    if to_date:
        end = datetime.combine(to_date + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
        filters.append(Activity.created_at < end)
    total = db.scalar(select(func.count()).select_from(Activity).where(*filters)) or 0
    items = db.scalars(select(Activity).where(*filters).order_by(Activity.created_at.desc(), Activity.id.desc()).offset(offset).limit(limit)).all()
    return total, items
