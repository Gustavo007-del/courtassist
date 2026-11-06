"""Private notification center and device reconciliation API."""
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.v1.dependencies import current_user
from app.database.session import get_db
from app.models.user import User
from app.models.notifications import Notification, UserDevice, NotificationDelivery, NotificationDeliveryAttempt
from app.schemas.notifications import NotificationPreferences, PreferencesPatch, RegisterDevice, LocalAcknowledgement, ManualReminder
from app.services import notification_service as service, notification_devices as devices
from app.services.notification_channels import capabilities
from app.services.notification_delivery import target

router = APIRouter(tags=['notifications'])

def owned(db, model, identifier, user):
    row = db.scalar(select(model).where(model.id == identifier, model.user_id == user.id))
    if not row: raise HTTPException(404, 'Record not found')
    return row

def public(row):
    fields = ('id','category','title','message','entity_type','entity_id','scheduled_at','nominal_at','status','priority','read_at','dismissed_at','cancelled_at','sent_at','created_at','manual')
    return {**{key:getattr(row,key) for key in fields}, 'summary':row.details.get('summary'), 'purpose':row.details.get('purpose')}

def device_public(row):
    return {key:getattr(row,key) for key in ('id','platform','label','last_seen_at','revoked_at','created_at')} | {'push_registered':bool(row.token_ciphertext)}

def preference_output(db,user):
    prefs=service.get_preferences(db,user.id)
    return {'preferences':NotificationPreferences.model_validate(prefs,from_attributes=True).model_dump(), 'capabilities':capabilities(user)}

@router.get('/notification-preferences')
def preferences(user:User=Depends(current_user),db:Session=Depends(get_db)):
    output=preference_output(db,user);db.commit();return output

@router.patch('/notification-preferences')
def update_preferences(data:PreferencesPatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    prefs=service.get_preferences(db,user.id,lock=True)
    try: merged=NotificationPreferences.model_validate(NotificationPreferences.model_validate(prefs,from_attributes=True).model_dump() | data.model_dump(exclude_unset=True))
    except ValidationError: raise HTTPException(422,'Invalid notification preferences')
    for key,value in merged.model_dump().items():setattr(prefs,key,value)
    db.flush();service.reconcile_user(db,user);db.commit();return preference_output(db,user)

@router.post('/notifications/register-device')
def register_device(data:RegisterDevice,user:User=Depends(current_user),db:Session=Depends(get_db)):
    try:return device_public(devices.register(db,user,data))
    except IntegrityError:db.rollback();raise HTTPException(409,'Device registration changed; retry')

@router.get('/notifications/devices')
def list_devices(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [device_public(row) for row in db.scalars(select(UserDevice).where(UserDevice.user_id==user.id).order_by(UserDevice.created_at.desc()).limit(100))]

@router.delete('/notifications/devices/{device_id}',status_code=204)
def revoke_device(device_id:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    devices.revoke(db,owned(db,UserDevice,device_id,user));db.commit()

@router.get('/notifications/unread-count')
def unread(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return {'count':db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==user.id,Notification.read_at.is_(None),Notification.dismissed_at.is_(None),Notification.cancelled_at.is_(None),Notification.scheduled_at<=service.utcnow())) or 0}

@router.post('/notifications/read-all')
def read_all(user:User=Depends(current_user),db:Session=Depends(get_db)):
    from sqlalchemy import update
    db.execute(update(Notification).where(Notification.user_id==user.id,Notification.read_at.is_(None),Notification.scheduled_at<=service.utcnow()).values(read_at=service.utcnow()));db.commit();return {'detail':'Notifications marked as read'}

@router.get('/notifications/local-plan')
def local_plan(device_id:UUID,local_allowed:bool=True,user:User=Depends(current_user),db:Session=Depends(get_db)):
    device=owned(db,UserDevice,device_id,user)
    if device.revoked_at:raise HTTPException(409,'Device is revoked')
    prefs=service.reconcile_user(db,user);now=service.utcnow();active=[];plans=[]
    if not local_allowed:
        for delivery in db.scalars(select(NotificationDelivery).where(NotificationDelivery.device_id==device.id,NotificationDelivery.channel=='local',NotificationDelivery.status=='scheduled')):delivery.status='cancelled';delivery.error_code='permission_denied'
        db.commit();return {'active_ids':[],'plans':[]}
    rows=db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.cancelled_at.is_(None),Notification.dismissed_at.is_(None),Notification.scheduled_at>=now-timedelta(days=1),Notification.scheduled_at<=now+timedelta(days=35)).order_by(Notification.scheduled_at).limit(500)).all()
    for row in rows:
        if not prefs.local_notifications or 'local' not in row.channels or not service.valid_source(db,row,prefs,now):continue
        push=db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.notification_id==row.id,NotificationDelivery.device_id==device.id,NotificationDelivery.channel=='push',NotificationDelivery.status.in_(['processing','sent'])))
        if push:continue
        ack=db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id==row.id,NotificationDelivery.device_id==device.id,NotificationDelivery.channel=='local'))
        if service.aware(row.scheduled_at)<now-timedelta(minutes=10) and not (ack and ack.status=='scheduled'):continue
        active.append(str(row.id))
        if ack and ack.status=='scheduled' and ack.local_scheduled_at and service.aware(ack.local_scheduled_at)<=now:continue
        at=service.quiet_adjust(max(service.aware(row.scheduled_at),now+timedelta(seconds=5)),prefs,row.priority)
        plans.append({'id':row.id,'title':row.title,'message':row.message,'scheduled_at':at})
    db.commit();return {'active_ids':active,'plans':plans[:200]}

@router.post('/notifications/local-ack')
def local_ack(data:LocalAcknowledgement,user:User=Depends(current_user),db:Session=Depends(get_db)):
    device=owned(db,UserDevice,data.device_id,user);row=owned(db,Notification,data.notification_id,user)
    # Serialize against a worker claiming push delivery for this notification.
    db.refresh(row,with_for_update=True)
    prefs=service.get_preferences(db,user.id);now=service.utcnow()
    if device.revoked_at or row.cancelled_at or row.dismissed_at or not prefs.local_notifications or 'local' not in row.channels or not service.valid_source(db,row,prefs,now):raise HTTPException(409,'Reminder is no longer active')
    if db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.notification_id==row.id,NotificationDelivery.device_id==device.id,NotificationDelivery.channel=='push',NotificationDelivery.status.in_(['processing','sent']))):raise HTTPException(409,'Push delivery already claimed')
    expected=service.quiet_adjust(max(service.aware(row.scheduled_at),now),prefs,row.priority)
    if abs((data.scheduled_at-expected).total_seconds())>90:raise HTTPException(409,'Reminder time changed')
    delivery=target(db,row,'local',device,now)
    if delivery.status!='scheduled' or not delivery.local_scheduled_at or abs((service.aware(delivery.local_scheduled_at)-data.scheduled_at).total_seconds())>1:
        delivery.status='scheduled';delivery.local_scheduled_at=data.scheduled_at;delivery.attempt_count+=1
        db.add(NotificationDeliveryAttempt(user_id=user.id,notification_id=row.id,delivery_id=delivery.id,channel='local',number=delivery.attempt_count,status='local_scheduled',started_at=now,finished_at=now))
    db.commit();return {'status':'local_scheduled'}

@router.get('/notifications')
def listing(category:str|None=None,unread_only:bool=False,read_only:bool=False,scheduled:bool=False,ascending:bool=False,offset:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),user:User=Depends(current_user),db:Session=Depends(get_db)):
    service.reconcile_user(db,user);db.commit()
    filters=[Notification.user_id==user.id,Notification.dismissed_at.is_(None),Notification.cancelled_at.is_(None)]
    if not scheduled:filters.append(Notification.scheduled_at<=service.utcnow())
    if category:filters.append(Notification.category==category)
    if unread_only:filters.append(Notification.read_at.is_(None))
    if read_only:filters.append(Notification.read_at.is_not(None))
    total=db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    rows=db.scalars(select(Notification).where(*filters).order_by(Notification.scheduled_at.asc() if ascending else Notification.scheduled_at.desc(),Notification.id).offset(offset).limit(limit))
    return {'items':[public(row) for row in rows],'total':total,'offset':offset,'limit':limit}

@router.post('/notifications/reminders',status_code=201)
def manual(data:ManualReminder,user:User=Depends(current_user),db:Session=Depends(get_db)):
    source=service.owned_entity(db,user.id,data.entity_type,data.entity_id)
    if not source:raise HTTPException(404,'Record not found')
    previous=owned(db,Notification,data.replaces,user) if data.replaces else None
    if previous and (not previous.manual or previous.entity_type!=data.entity_type or previous.entity_id!=data.entity_id):raise HTTPException(422,'Only a matching manual follow-up may be rescheduled')
    prefs=service.get_preferences(db,user.id);now=service.utcnow()
    category='payment' if data.entity_type in ('agreement','invoice') else data.entity_type
    if not service.category_enabled(prefs,category):raise HTTPException(409,'Enable this reminder category in notification settings')
    when=data.scheduled_at or service.wall(data.local_date,data.local_time,prefs)
    if data.local_date and (when.astimezone(service.zone(prefs)).replace(tzinfo=None)!=datetime.combine(data.local_date,data.local_time)):raise HTTPException(422,'This local time does not exist in the selected timezone')
    if not now<when<=now+timedelta(days=365):raise HTTPException(422,'Choose a future time within one year')
    row=service.ensure(db,user,prefs,'manual:'+str(uuid4()),category,data.entity_type,data.entity_id,when,data.priority,{'purpose':data.purpose},now)
    row.manual=True
    if not service.valid_source(db,row,prefs,now):raise HTTPException(409,'This record no longer supports reminders')
    if previous:
        service.cancel(db,previous,'rescheduled',now)
        row.details={**row.details,'previous_notification_id':str(previous.id)}
    db.commit();return public(row)

@router.get('/notifications/{notification_id}')
def detail(notification_id:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,Notification,notification_id,user)
    deliveries=db.scalars(select(NotificationDelivery).where(NotificationDelivery.user_id==user.id,NotificationDelivery.notification_id==row.id))
    return public(row) | {'deliveries':[{key:getattr(d,key) for key in ('id','channel','status','attempt_count','error_code','sent_at','local_scheduled_at','observed_at')} for d in deliveries]}

@router.patch('/notifications/{notification_id}/read')
@router.post('/notifications/{notification_id}/read')
def read(notification_id:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,Notification,notification_id,user);row.read_at=row.read_at or service.utcnow();db.commit();return public(row)

@router.post('/notifications/{notification_id}/dismiss')
def dismiss(notification_id:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=owned(db,Notification,notification_id,user);row.dismissed_at=service.utcnow();service.cancel(db,row,'dismissed');db.commit();return public(row)

@router.post('/notifications/{notification_id}/observed')
def observed(notification_id:UUID,device_id:UUID,user:User=Depends(current_user),db:Session=Depends(get_db)):
    owned(db,Notification,notification_id,user);owned(db,UserDevice,device_id,user)
    for row in db.scalars(select(NotificationDelivery).where(NotificationDelivery.user_id==user.id,NotificationDelivery.notification_id==notification_id,NotificationDelivery.device_id==device_id)):
        row.observed_at=row.observed_at or service.utcnow()
    db.commit();return {'detail':'Observation recorded'}
