from sqlalchemy import select,update
from fastapi import HTTPException
from app.models.notifications import UserDevice,NotificationDelivery
from app.services.notification_channels import encrypt_token,hash_token,ProviderFailure
from app.core.config import get_settings
from datetime import datetime,timezone

def revoke(db,row):
    row.revoked_at=datetime.now(timezone.utc);row.token_ciphertext=None;row.token_hash=None
    db.execute(update(NotificationDelivery).where(NotificationDelivery.device_id==row.id,NotificationDelivery.status.in_(['pending','scheduled'])).values(status='cancelled',error_code='device_revoked'))

def register(db,user,request):
    if request.token and request.platform!='android':raise HTTPException(422,'Native FCM registration currently supports Android only')
    encrypted=None
    if request.token:
        if not get_settings().fcm_enabled:raise HTTPException(503,'FCM is not configured; local reminders remain available')
        try:encrypted=encrypt_token(request.token)
        except ProviderFailure:raise HTTPException(503,'Encrypted push-token storage is not configured')
    row=db.scalar(select(UserDevice).where(UserDevice.user_id==user.id,UserDevice.installation_id==request.installation_id).with_for_update())
    if row and row.revoked_at and not request.reactivate:raise HTTPException(409,'Device revoked; explicitly enable notifications to register again')
    if request.token:
        previous=db.scalar(select(UserDevice).where(UserDevice.token_hash==hash_token(request.token)).with_for_update())
        if previous and (not row or previous.id!=row.id):revoke(db,previous);db.flush()
    if not row:row=UserDevice(user_id=user.id,installation_id=request.installation_id,platform=request.platform);db.add(row)
    row.label=request.label;row.platform=request.platform;row.revoked_at=None;row.last_seen_at=datetime.now(timezone.utc)
    row.token_ciphertext=encrypted;row.token_hash=hash_token(request.token) if request.token else None
    db.commit();return row
