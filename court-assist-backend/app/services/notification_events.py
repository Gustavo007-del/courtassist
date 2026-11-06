"""Transactional module events. The durable outbox survives broker/worker outages."""
import uuid
from sqlalchemy import event,inspect
from sqlalchemy.orm import Session
from app.models.notifications import NotificationEvent
from app.models.hearing import Hearing,HearingReminder
from app.models.planning import Task,Appointment,PlanningReminder
from app.models.phase10 import FeeAgreement,Payment,DraftDocument
from app.models.finance import Invoice
from app.models.document import Document
from app.models.user import UserPreference

SOURCES={
    Hearing:('hearing',{'hearing_date','hearing_time','status','reminder_enabled','follow_up_hearing_id'}),
    HearingReminder:('hearing_reminder',{'scheduled_at','status','reminder_type','delivery_channel'}),
    Task:('task',{'due_date','due_time','status','priority','reminder_minutes','archived_at','recurrence_kind','recurrence_interval'}),
    Appointment:('appointment',{'appointment_date','start_time','end_time','status','reminder_minutes','archived_at'}),
    PlanningReminder:('planning_reminder',{'scheduled_at','status'}),
    FeeAgreement:('agreement',{'amount','status','due_date'}),
    Payment:('payment',{'amount','status','agreement_id'}),
    Invoice:('invoice',{'total','status','due_date','agreement_id'}),
    Document:('document',{'is_archived','storage_status'}),
    DraftDocument:('draft',{'status','archived_at'}),
}

def publish_event(db,user_id,entity_type,entity_id,event_name):
    db.add(NotificationEvent(user_id=user_id,entity_type=entity_type,entity_id=entity_id,event_name=event_name))

def collect_events(db,flush_context,instances):
    # ORM changes and their event are committed atomically. No network calls occur here.
    for row in tuple(db.new)+tuple(db.dirty):
        if isinstance(row,UserPreference):
            changed=any(inspect(row).attrs[column.name].history.has_changes() for column in row.__table__.columns if column.name not in ('notification_checked_at','updated_at'))
            if row.user_id and (row in db.new or changed):
                publish_event(db,row.user_id,'preferences',row.user_id,'preferences.changed')
            continue
        source=SOURCES.get(type(row))
        if not source or not row.user_id:continue
        entity,fields=source
        created=row in db.new
        if not created and not any(inspect(row).attrs[name].history.has_changes() for name in fields):continue
        if row.id is None:row.id=uuid.uuid4()
        publish_event(db,row.user_id,entity,row.id,entity+('.created' if created else '.changed'))

def install():
    if not event.contains(Session,'before_flush',collect_events):event.listen(Session,'before_flush',collect_events)
