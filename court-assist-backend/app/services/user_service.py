from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import normalize_email, normalize_phone
from app.models.user import User, UserPreference
from app.schemas.preferences import PreferencesUpdate
from app.schemas.user import UserUpdate
from app.services.activity_service import record_activity


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    changes = data.model_dump(exclude_unset=True)
    if not changes or any(changes.get(key) is None for key in ('full_name', 'preferred_language') if key in changes):
        raise HTTPException(422, 'Provide valid profile fields')
    if 'email' in changes and changes['email'] is not None:
        changes['email'] = normalize_email(changes['email'])
    if 'phone_number' in changes and changes['phone_number'] is not None:
        changes['phone_number'] = normalize_phone(changes['phone_number'])
    if 'office_phone' in changes and changes['office_phone'] is not None:
        changes['office_phone'] = normalize_phone(changes['office_phone'])
    if 'professional_email' in changes and changes['professional_email'] is not None:
        changes['professional_email'] = normalize_email(changes['professional_email'])
    if changes.get('email', user.email) is None and changes.get('phone_number', user.phone_number) is None:
        raise HTTPException(422, 'An email or phone number is required')
    changed = []
    for key, value in changes.items():
        value = value.strip() if isinstance(value, str) else value
        if getattr(user, key) != value:
            setattr(user, key, value)
            changed.append(key)
            if key == 'email':
                user.is_email_verified = False
            elif key == 'phone_number':
                user.is_phone_verified = False
    if not changed:
        return user
    record_activity(db, user.id, 'profile_updated', 'Profile updated', entity_type='user', entity_id=user.id, details={'fields': changed})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Email or phone number already in use') from None
    db.refresh(user)
    return user


def update_preferences(db: Session, user: User, data: PreferencesUpdate) -> UserPreference:
    changes = data.model_dump(exclude_unset=True)
    if not changes or any(value is None for value in changes.values()):
        raise HTTPException(422, 'Provide valid preferences')
    preferences = user.preferences
    if preferences is None:
        preferences = UserPreference(user_id=user.id)
        db.add(preferences)
    changed = []
    for key, value in changes.items():
        if getattr(preferences, key) != value:
            setattr(preferences, key, value)
            changed.append(key)
    if changed:
        record_activity(db, user.id, 'preferences_updated', 'Preferences updated', entity_type='user', entity_id=user.id, details={'fields': changed})
        db.commit()
        db.refresh(preferences)
    return preferences
