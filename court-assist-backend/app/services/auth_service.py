import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import (create_access_token, hash_password, hash_token, new_opaque_token,
                               normalize_email, normalize_phone, validate_password, verify_password)
from app.models.user import PasswordResetToken, RefreshSession, User, UserPreference
from app.repositories.user_repository import by_identifier
from app.schemas.auth import RegisterIn, TokenOut
from app.services.activity_service import record_activity

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    # SQLite used by tests drops tzinfo; PostgreSQL preserves it.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def register(db: Session, data: RegisterIn) -> User:
    validate_password(data.password)
    email = normalize_email(data.email) if data.email else None
    phone = normalize_phone(data.phone_number) if data.phone_number else None
    if email and by_identifier(db, email) or phone and by_identifier(db, phone):
        raise HTTPException(409, 'Account already exists')
    user = User(full_name=data.full_name.strip(), email=email, phone_number=phone,
                password_hash=hash_password(data.password), preferred_language=data.preferred_language)
    user.preferences = UserPreference()
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Account already exists') from None
    db.refresh(user)
    return user


def issue_tokens(db: Session, user: User, family_id=None) -> TokenOut:
    settings = get_settings()
    opaque = new_opaque_token()
    expires = now_utc() + timedelta(days=settings.refresh_token_expire_days)
    family_id = family_id or uuid4()
    db.add(RefreshSession(user_id=user.id, family_id=family_id, token_hash=hash_token(opaque), expires_at=expires))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, family_id), refresh_token=opaque,
                    access_expires_in=settings.access_token_expire_minutes * 60,
                    refresh_expires_in=settings.refresh_token_expire_days * 86400, user=user)


def login(db: Session, identifier: str, password: str) -> TokenOut:
    key = normalize_email(identifier) if '@' in identifier else normalize_phone(identifier)
    user = by_identifier(db, key)
    if user:
        user = lock_account(db, user.id)
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(401, 'Invalid credentials')
    user.last_login_at = now_utc()
    return issue_tokens(db, user)


def lock_account(db: Session, user_id):
    return db.get(User, user_id, with_for_update=True, populate_existing=True)


def _session(db: Session, token: str, owner=None) -> RefreshSession | None:
    query = select(RefreshSession).where(RefreshSession.token_hash == hash_token(token))
    if owner is not None:
        query = query.where(RefreshSession.user_id == owner)
    session = db.scalar(query)
    if session is None or lock_account(db, session.user_id) is None:
        return None
    return db.scalar(query.with_for_update().execution_options(populate_existing=True))


def refresh(db: Session, token: str) -> TokenOut:
    session = _session(db, token)
    if not session:
        raise HTTPException(401, 'Invalid refresh token')
    if session.revoked_at:
        db.execute(update(RefreshSession).where(RefreshSession.family_id == session.family_id).values(revoked_at=now_utc()))
        db.commit()
        raise HTTPException(401, 'Refresh token reused; session revoked')
    if aware(session.expires_at) <= now_utc() or not session.user.is_active:
        raise HTTPException(401, 'Expired refresh token')
    session.revoked_at = now_utc()
    db.flush()
    return issue_tokens(db, session.user, session.family_id)


def logout(db: Session, token: str, user: User) -> None:
    session = _session(db, token, user.id)
    if session and session.user_id == user.id:
        db.execute(update(RefreshSession).where(RefreshSession.family_id == session.family_id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now_utc()))
        db.commit()


def _send_reset_email(email: str, token: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message['Subject'] = 'Court Assist password reset'
    message['From'] = settings.smtp_from
    message['To'] = email
    message.set_content(f'Open this link to reset your password: {settings.reset_url_base.rstrip("/")}?token={quote(token)}\nThis link expires in 30 minutes.')
    tls = ssl.create_default_context()
    connection = (smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=tls)
                  if settings.smtp_port == 465 else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10))
    with connection as smtp:
        if settings.smtp_port != 465:
            smtp.starttls(context=tls)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def forgot_password(db: Session, email: str) -> None:
    settings = get_settings()
    try:
        normalized = normalize_email(email)
    except HTTPException:
        return
    user = by_identifier(db, normalized)
    if not settings.reset_enabled or not user or not user.is_active:
        return
    user = lock_account(db, user.id)
    if not user or not user.is_active or db.scalar(select(PasswordResetToken.id).where(
        PasswordResetToken.user_id == user.id, PasswordResetToken.created_at > now_utc() - timedelta(minutes=2),
    ).limit(1)):
        return
    token = new_opaque_token()
    record = PasswordResetToken(user_id=user.id, token_hash=hash_token(token), expires_at=now_utc() + timedelta(minutes=30))
    db.add(record)
    db.commit()
    try:
        _send_reset_email(normalized, token)
    except Exception:
        logger.warning('password_reset_delivery_failed')
        db.delete(record)
        db.commit()


def reset_password(db: Session, token: str, password: str) -> None:
    validate_password(password)
    query = select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
    record = db.scalar(query)
    user = lock_account(db, record.user_id) if record else None
    record = db.scalar(query.with_for_update().execution_options(populate_existing=True)) if user else None
    if not record or record.used_at or aware(record.expires_at) <= now_utc():
        raise HTTPException(400, 'Invalid or expired reset token')
    if not user or not user.is_active:
        raise HTTPException(400, 'Invalid or expired reset token')
    user.password_hash = hash_password(password)
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)).values(used_at=now_utc()))
    db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now_utc()))
    from app.models.notifications import UserDevice
    from app.services.notification_devices import revoke
    for device in db.scalars(select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.revoked_at.is_(None))): revoke(db, device)
    db.commit()


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    user = lock_account(db, user.id)
    if not user or not user.is_active:
        raise HTTPException(401, 'Account unavailable')
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(400, 'Current password is incorrect')
    validate_password(new_password)
    if verify_password(new_password, user.password_hash):
        raise HTTPException(422, 'New password must be different')
    user.password_hash = hash_password(new_password)
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)).values(used_at=now_utc()))
    db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now_utc()))
    from app.models.notifications import UserDevice
    from app.services.notification_devices import revoke
    for device in db.scalars(select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.revoked_at.is_(None))): revoke(db, device)
    record_activity(db, user.id, 'password_changed', 'Password changed', entity_type='user', entity_id=user.id)
    db.commit()
