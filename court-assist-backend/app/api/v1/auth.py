from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.api.v1.rate_limit import auth_rate_limit
from app.database.session import get_db
from app.models.user import RefreshSession, User
from app.schemas.auth import (ChangePasswordIn, ForgotPasswordIn, LoginIn, MessageOut, RefreshIn, SessionInfoOut,
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
    auth_service.logout(db, data.refresh_token, user)
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
