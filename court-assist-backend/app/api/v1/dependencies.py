from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.security import decode_access_session
from app.database.session import get_db
from app.models.user import RefreshSession, User

bearer = HTTPBearer(auto_error=False)


def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})
    identifier, family = decode_access_session(credentials.credentials)
    query = select(User).where(User.id == identifier, User.is_active.is_(True))
    if family is not None:
        query = query.where(select(RefreshSession.id).where(
            RefreshSession.user_id == identifier, RefreshSession.family_id == family,
            RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > datetime.now(timezone.utc),
        ).exists())
    user = db.scalar(query)
    if not user or not user.is_active:
        raise HTTPException(401, 'Account unavailable')
    request.state.session_family = family
    return user
