import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
import phonenumbers
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import HTTPException
from app.core.config import get_settings

hasher = PasswordHasher()


def normalize_email(value: str) -> str:
    email = value.strip().casefold()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 320:
        raise HTTPException(422, 'Invalid email address')
    return email


def normalize_phone(value: str) -> str:
    try:
        parsed = phonenumbers.parse(value.strip(), 'IN')
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError()
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except (phonenumbers.NumberParseException, ValueError):
        raise HTTPException(422, 'Invalid phone number') from None


def validate_password(value: str) -> None:
    if len(value) < 12 or len(value) > 128 or not re.search(r'[a-zA-Z]', value) or not re.search(r'\d', value):
        raise HTTPException(422, 'Password must contain 12–128 characters, a letter and a number')


def hash_password(value: str) -> str:
    return hasher.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    try:
        return hasher.verify(hashed, value)
    except (VerifyMismatchError, VerificationError):
        return False


def create_access_token(user_id: UUID, family_id: UUID | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {'sub': str(user_id), 'type': 'access', 'iat': now, 'exp': now + timedelta(minutes=settings.access_token_expire_minutes)}
    if family_id is not None:
        claims['sid'] = str(family_id)
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_session(token: str) -> tuple[UUID, UUID | None]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], options={'require': ['sub', 'exp', 'type']})
        if payload['type'] != 'access':
            raise ValueError()
        session = UUID(payload['sid']) if 'sid' in payload else None
        if session is None and settings.hardened:
            raise ValueError()
        return UUID(payload['sub']), session
    except (jwt.PyJWTError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(401, 'Invalid or expired access token', headers={'WWW-Authenticate': 'Bearer'}) from None


def decode_access_token(token: str) -> UUID:
    return decode_access_session(token)[0]


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
