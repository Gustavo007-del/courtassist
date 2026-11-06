"""Leased, bounded delivery attempts. Network calls happen after persisting a claim."""
from datetime import timedelta
from sqlalchemy import select,or_,and_
from app.core.config import get_settings
from app.models.user import User
from app.models.notifications import Notification,UserDevice,NotificationDelivery,NotificationDeliveryAttempt
from app.services import notification_service as coordinator
from app.services.notification_channels import send_push,send_email,ProviderFailure
from app.services.notification_devices import revoke

def local_reserved(db,notification_id,device_id):
    return db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.notification_id==notification_id,NotificationDelivery.device_id==device_id,NotificationDelivery.channel=='local',NotificationDelivery.status=='scheduled')) is not None

def target(db,notification,channel,device=None,now=None):
    now=now or coordinator.utcnow();key=str(device.id) if device else 'user'
    row=db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id==notification.id,NotificationDelivery.channel==channel,NotificationDelivery.target_key==key))
    if not row:
        row=NotificationDelivery(user_id=notification.user_id,notification_id=notification.id,device_id=device.id if device else None,channel=channel,target_key=key,next_attempt_at=now);db.add(row);db.flush()
    elif row.status=='cancelled' and not notification.cancelled_at:row.status='pending';row.next_attempt_at=now;row.error_code=None
    return row

def prepare_due(db,now=None,limit=200):
    now=coordinator.aware(now or coordinator.utcnow())
    rows=db.scalars(select(Notification).where(Notification.cancelled_at.is_(None),Notification.scheduled_at<=now,Notification.status.in_(['scheduled','pending','failed']),Notification.details['delivery_prepared_at'].as_string().is_(None)).order_by(Notification.scheduled_at).limit(limit).with_for_update(skip_locked=True)).all()
    for notification in rows:
        user=db.get(User,notification.user_id)
        if not user or not user.is_active:coordinator.cancel(db,notification,'account_inactive',now);continue
        preferences=coordinator.get_preferences(db,user.id)
        if coordinator.aware(notification.scheduled_at)<now-timedelta(days=1) or not coordinator.valid_source(db,notification,preferences,now):coordinator.cancel(db,notification,'source_inactive',now);continue
        if preferences.push_notifications and 'push' in notification.channels:
            devices=db.scalars(select(UserDevice).where(UserDevice.user_id==user.id,UserDevice.revoked_at.is_(None),UserDevice.token_ciphertext.is_not(None),UserDevice.platform=='android',UserDevice.last_seen_at>=now-timedelta(days=30),UserDevice.created_at<=coordinator.aware(notification.scheduled_at)+timedelta(minutes=10))).all()
            for device in devices:
                if preferences.local_notifications and local_reserved(db,notification.id,device.id):continue
                target(db,notification,'push',device,now)
        if preferences.email_notifications and 'email' in notification.channels and user.email and user.is_email_verified:target(db,notification,'email',now=now)
        notification.details={**notification.details,'delivery_prepared_at':now.isoformat()}
        if notification.status=='scheduled':notification.status='pending'
    db.commit();return len(rows)

def send_one(db,delivery_id,now=None):
    now=coordinator.aware(now or coordinator.utcnow());maximum=get_settings().notification_max_attempts
    candidate=db.get(NotificationDelivery,delivery_id)
    if not candidate:return False
    notification_lock=db.scalar(select(Notification).where(Notification.id==candidate.notification_id).with_for_update(skip_locked=True))
    if not notification_lock:return False
    delivery=db.scalar(select(NotificationDelivery).where(NotificationDelivery.id==delivery_id).with_for_update(skip_locked=True))
    if not delivery or delivery.status in ('sent','failed','cancelled','scheduled'):return False
    if delivery.status=='processing' and delivery.lease_until and coordinator.aware(delivery.lease_until)>now:return False
    if delivery.next_attempt_at and coordinator.aware(delivery.next_attempt_at)>now:return False
    if delivery.status=='processing':
        previous=db.scalar(select(NotificationDeliveryAttempt).where(NotificationDeliveryAttempt.delivery_id==delivery.id,NotificationDeliveryAttempt.number==delivery.attempt_count))
        if previous and previous.status=='started':previous.status='unknown';previous.error_code='worker_interrupted';previous.finished_at=now
    if delivery.attempt_count>=maximum:delivery.status='failed';delivery.error_code='retry_limit';db.commit();return False
    notification=db.get(Notification,delivery.notification_id);user=db.get(User,delivery.user_id)
    if not notification or not user or not user.is_active or notification.user_id!=delivery.user_id:delivery.status='cancelled';delivery.error_code='source_unavailable';db.commit();return False
    preferences=coordinator.get_preferences(db,user.id)
    allowed=delivery.channel in notification.channels and bool(getattr(preferences,delivery.channel+'_notifications',False))
    if notification.cancelled_at or not allowed or not coordinator.valid_source(db,notification,preferences,now):delivery.status='cancelled';delivery.error_code='preferences_or_source';db.commit();return False
    quiet=coordinator.quiet_adjust(now,preferences,notification.priority)
    if quiet>now:delivery.status='pending';delivery.next_attempt_at=quiet;delivery.lease_until=None;db.commit();return False
    device=db.get(UserDevice,delivery.device_id) if delivery.device_id else None
    if delivery.channel=='push':
        if not device or device.user_id!=user.id or device.revoked_at or not device.token_ciphertext:delivery.status='cancelled';delivery.error_code='device_revoked';db.commit();return False
        if preferences.local_notifications and local_reserved(db,notification.id,device.id):delivery.status='cancelled';delivery.error_code='local_primary';db.commit();return False
    delivery.status='processing';delivery.attempt_count+=1;delivery.lease_until=now+timedelta(minutes=2)
    attempt=NotificationDeliveryAttempt(user_id=user.id,notification_id=notification.id,delivery_id=delivery.id,channel=delivery.channel,number=delivery.attempt_count,status='started',started_at=now)
    db.add(attempt);db.commit()
    try:
        provider_id=send_push(notification,device) if delivery.channel=='push' else send_email(notification,user,delivery.id) if delivery.channel=='email' else None
        if not provider_id:raise ProviderFailure('unsupported_channel')
        attempt.status='sent';attempt.provider_message_id=provider_id;delivery.provider_message_id=provider_id;delivery.status='sent';delivery.sent_at=now;delivery.error_code=None
        db.refresh(notification)
        notification.sent_at=notification.sent_at or now
        if not notification.cancelled_at:notification.status='sent'
    except ProviderFailure as error:
        attempt.status='failed';attempt.error_code=error.code;delivery.error_code=error.code
        if error.invalid_token and device:revoke(db,device)
        if error.retryable and delivery.attempt_count<maximum:delivery.status='pending';delivery.next_attempt_at=now+timedelta(seconds=min(3600,60*(2**(delivery.attempt_count-1))))
        else:delivery.status='failed'
        other=db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.notification_id==notification.id,NotificationDelivery.id!=delivery.id,NotificationDelivery.status.in_(['pending','processing','sent','scheduled'])).limit(1))
        if not other and delivery.status=='failed' and not notification.cancelled_at:notification.status='failed'
    except Exception:
        # Do not persist raw provider exceptions; they can contain tokens or addresses.
        attempt.status='failed';attempt.error_code='provider_unavailable';delivery.error_code='provider_unavailable'
        delivery.status='pending' if delivery.attempt_count<maximum else 'failed';delivery.next_attempt_at=now+timedelta(seconds=min(3600,60*(2**(delivery.attempt_count-1))))
    attempt.finished_at=now;delivery.lease_until=None;db.commit();return True

def dispatch(db,now=None,limit=100):
    now=coordinator.aware(now or coordinator.utcnow());prepare_due(db,now,limit)
    identifiers=db.scalars(select(NotificationDelivery.id).where(or_(and_(NotificationDelivery.status=='pending',NotificationDelivery.next_attempt_at<=now),and_(NotificationDelivery.status=='processing',NotificationDelivery.lease_until<=now))).order_by(NotificationDelivery.next_attempt_at).limit(limit)).all()
    return sum(bool(send_one(db,identifier,now)) for identifier in identifiers)
