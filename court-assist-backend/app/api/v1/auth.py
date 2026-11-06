from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.api.v1.rate_limit import auth_rate_limit
from app.database.session import get_db
from app.models.user import RefreshSession, User
from app.schemas.auth import (ActiveSessionOut, ChangePasswordIn, ForgotPasswordIn, LoginIn, MessageOut, RefreshIn, SessionInfoOut,
                              RegisterIn, ResetPasswordIn, TokenOut)
from app.schemas.user import UserOut
from app.services import auth_service
from app.services.auth_service import now_utc

router = APIRouter(prefix='/auth', tags=['authentication'])


@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth_rate_limit)])
def register(data: RegisterIn, db: Session = Depends(get_db)):
    return auth_service.register(db, data)


@router.post('/login', response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
def login(data: LoginIn, db: Session = Depends(get_db)):
    return auth_service.login(db, data.identifier, data.password)


@router.post('/refresh', response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    return auth_service.refresh(db, data.refresh_token)


@router.post('/logout', response_model=MessageOut)
def logout(data: RefreshIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth_service.lock_account(db, user.id)
    if data.device_id or data.installation_id:
        from app.models.notifications import UserDevice
        from app.services.notification_devices import revoke
        device = db.scalar(select(UserDevice).where(UserDevice.id == data.device_id if data.device_id else UserDevice.installation_id == data.installation_id, UserDevice.user_id == user.id))
        if device: revoke(db, device)
    auth_service.logout(db, data.refresh_token, user)
    db.commit()
    return MessageOut(detail='Signed out')


@router.post('/forgot-password', response_model=MessageOut, dependencies=[Depends(auth_rate_limit)])
def forgot_password(data: ForgotPasswordIn, db: Session = Depends(get_db)):
    auth_service.forgot_password(db, data.email)
    return MessageOut(detail='If the account exists and email recovery is configured, a reset link will be sent')


@router.post('/reset-password', response_model=MessageOut, dependencies=[Depends(auth_rate_limit)])
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    auth_service.reset_password(db, data.token, data.password)
    return MessageOut(detail='Password updated')


@router.post('/change-password', response_model=MessageOut, dependencies=[Depends(auth_rate_limit)])
def change_password(data: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth_service.change_password(db, user, data.current_password, data.new_password)
    return MessageOut(detail='Password changed. Sign in again on all devices.')


@router.get('/sessions', response_model=SessionInfoOut)
def sessions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(RefreshSession).where(
        RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None),
        RefreshSession.expires_at > now_utc())) or 0
    return SessionInfoOut(active_sessions=count, last_login_at=user.last_login_at)


@router.get('/sessions/devices', response_model=list[ActiveSessionOut])
def active_sessions(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(RefreshSession.family_id, func.max(RefreshSession.created_at), func.max(RefreshSession.expires_at)).where(
        RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > now_utc(),
    ).group_by(RefreshSession.family_id).order_by(func.max(RefreshSession.created_at).desc()).limit(100))
    return [ActiveSessionOut(id=family, refreshed_at=seen, expires_at=expires, current=family == request.state.session_family)
            for family, seen, expires in rows]


@router.delete('/sessions/{family_id}', status_code=204)
def revoke_session(family_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth_service.lock_account(db, user.id)
    result = db.execute(update(RefreshSession).where(
        RefreshSession.user_id == user.id, RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None),
    ).values(revoked_at=now_utc()))
    if not result.rowcount:
        raise HTTPException(404, 'Session unavailable')
    db.commit()
