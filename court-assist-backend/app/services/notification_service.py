"""DB-backed coordination. Existing reminder records remain the per-item configuration."""
import hashlib
import json
import uuid
from datetime import datetime,date,time,timedelta,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select,func
from app.models.user import User,UserPreference
from app.models.hearing import Hearing,HearingReminder
from app.models.planning import Task,Appointment,PlanningReminder
from app.models.phase10 import FeeAgreement,Payment,DraftDocument
from app.models.finance import Invoice
from app.models.document import Document
from app.models.notifications import Notification,NotificationEvent,NotificationDelivery
from app.services.notification_channels import generic_text

ENTITY_MODELS={'hearing':Hearing,'task':Task,'appointment':Appointment,'agreement':FeeAgreement,'payment':Payment,'invoice':Invoice,'document':Document,'draft':DraftDocument}
CATEGORY_FIELDS={'hearing':'hearing_reminders','task':'task_reminders','appointment':'appointment_reminders','payment':'payment_reminders','document':'document_reminders','draft':'draft_reminders','daily_summary':'daily_summary'}
def utcnow():return datetime.now(timezone.utc)
def aware(value):return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
def zone(preferences):
    try:return ZoneInfo(preferences.timezone)
    except (ValueError,KeyError):return ZoneInfo('Asia/Kolkata')
def wall(day,clock,preferences):return datetime.combine(day,clock,zone(preferences)).astimezone(timezone.utc)

def get_preferences(db,user_id,lock=False):
    query=select(UserPreference).where(UserPreference.user_id==user_id)
    preferences=db.scalar(query.with_for_update() if lock else query)
    if not preferences:preferences=UserPreference(user_id=user_id);db.add(preferences);db.flush()
    return preferences

def category_enabled(preferences,category):return bool(getattr(preferences,CATEGORY_FIELDS.get(category,''),True))
def channels(preferences):return [key for key,enabled in [('local',preferences.local_notifications),('push',preferences.push_notifications),('email',preferences.email_notifications)] if enabled]

def quiet_adjust(instant,preferences,priority='normal'):
    instant=aware(instant)
    if not preferences.quiet_start or not preferences.quiet_end or (priority=='urgent' and preferences.urgent_quiet_override):return instant
    local=instant.astimezone(zone(preferences));clock=local.time().replace(tzinfo=None);start,end=preferences.quiet_start,preferences.quiet_end
    overnight=start>end
    quiet=(clock>=start or clock<end) if overnight else start<=clock<end
    if not quiet:return instant
    day=local.date()+timedelta(days=1) if overnight and clock>=start else local.date()
    return wall(day,end,preferences)

def owned_entity(db,user_id,entity_type,entity_id):
    model=ENTITY_MODELS.get(entity_type)
    return db.scalar(select(model).where(model.id==entity_id,model.user_id==user_id)) if model and entity_id else None

def balance(db,agreement):
    received=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.user_id==agreement.user_id,Payment.agreement_id==agreement.id,Payment.status=='received'))
    return max(Decimal(0),agreement.amount-received)

def valid_source(db,notification,preferences,now=None):
    now=now or utcnow()
    if not category_enabled(preferences,notification.category):return False
    if notification.category=='daily_summary':return preferences.daily_summary and date.fromisoformat(notification.details['date'])>=now.astimezone(zone(preferences)).date()
    if notification.entity_type is None:return True
    source=owned_entity(db,notification.user_id,notification.entity_type,notification.entity_id)
    if not source:return False
    if notification.details.get('change'):return True
    if notification.entity_type=='task':return source.status not in ('Completed','Cancelled') and not source.archived_at
    if notification.entity_type=='appointment':return source.status=='Scheduled' and not source.archived_at and wall(source.appointment_date,source.end_time,preferences)>=now
    if notification.entity_type=='hearing':return source.status in ('Scheduled','Awaiting Order') and source.reminder_enabled and source.hearing_date>=now.astimezone(zone(preferences)).date()
    if notification.entity_type=='agreement':return source.status=='active' and balance(db,source)>0
    if notification.entity_type=='invoice':
        if source.status!='issued':return False
        if source.agreement_id:
            agreement=owned_entity(db,notification.user_id,'agreement',source.agreement_id)
            if not agreement or agreement.status!='active':return False
            paid=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.user_id==notification.user_id,Payment.agreement_id==agreement.id,Payment.status=='received'))
            return paid<source.total
        return True
    if notification.entity_type=='document':return not source.is_archived
    if notification.entity_type=='draft':return not source.archived_at
    return True

def cancel(db,notification,reason='source_inactive',now=None):
    if notification.cancelled_at:return
    notification.cancelled_at=now or utcnow();notification.cancellation_reason=reason;notification.status='cancelled'
    for delivery in db.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_id==notification.id,NotificationDelivery.status.in_(['pending','scheduled']))):
        delivery.status='cancelled';delivery.error_code=reason

def ensure(db,user,preferences,key,category,entity_type,entity_id,when,priority='normal',details=None,now=None,once=False):
    now=now or utcnow();when=aware(when);scheduled=quiet_adjust(when,preferences,priority)
    latest=db.scalar(select(Notification).where(Notification.user_id==user.id,Notification.source_key==key).order_by(Notification.created_at.desc(),Notification.id.desc()).limit(1))
    if latest:
        same=aware(latest.nominal_at)==when
        if latest.dismissed_at and same:return latest
        local_attempted=db.scalar(select(NotificationDelivery.id).where(NotificationDelivery.notification_id==latest.id,NotificationDelivery.channel=='local',NotificationDelivery.status=='scheduled',NotificationDelivery.local_scheduled_at<=now).limit(1)) if once else None
        if once and (latest.sent_at or latest.read_at or local_attempted):return latest
        if same and latest.sent_at and not latest.cancelled_at:return latest
        if same and not latest.cancelled_at:
            latest.title,latest.message=generic_text(category,user.preferred_language,bool(latest.details.get('change')))
            if aware(latest.scheduled_at)!=scheduled:
                latest.scheduled_at=scheduled
                for delivery in db.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_id==latest.id,NotificationDelivery.channel=='local',NotificationDelivery.status=='scheduled')):delivery.status='cancelled';delivery.error_code='rescheduled'
            latest.channels=['push'] if latest.details.get('requested_channel')=='push' and preferences.push_notifications else [] if latest.details.get('requested_channel')=='push' else channels(preferences);return latest
        if not latest.cancelled_at and not latest.sent_at:cancel(db,latest,'rescheduled',now)
    generation=str(latest.id) if latest and latest.cancelled_at else ''
    digest=hashlib.sha256((key+'|'+when.isoformat()+'|'+generation).encode()).hexdigest()
    existing=db.scalar(select(Notification).where(Notification.user_id==user.id,Notification.deduplication_key==digest))
    if existing:return existing
    title,message=generic_text(category,user.preferred_language,bool((details or {}).get('change')))
    row=Notification(user_id=user.id,source_key=key,deduplication_key=digest,category=category,title=title,message=message,entity_type=entity_type,entity_id=entity_id,nominal_at=when,scheduled_at=scheduled,priority=priority,channels=(['push'] if preferences.push_notifications else []) if (details or {}).get('requested_channel')=='push' else channels(preferences),details=details or {},created_at=now)
    db.add(row);db.flush();return row

def stable_overdue_time(db,user_id,key,fallback):
    previous=db.scalar(select(Notification).where(Notification.user_id==user_id,Notification.source_key==key).order_by(Notification.created_at.desc()).limit(1))
    return aware(previous.nominal_at) if previous and not previous.cancelled_at else fallback

def daily_counts(db,user_id,day,preferences,now=None):
    now=now or utcnow()
    count=lambda model,*filters:db.scalar(select(func.count()).select_from(model).where(model.user_id==user_id,*filters)) or 0
    active=(Task.status.in_(['Pending','In Progress']),Task.archived_at.is_(None))
    candidates=db.scalars(select(Task).where(Task.user_id==user_id,*active,Task.due_date<=day)).all()
    overdue=sum(1 for row in candidates if wall(row.due_date,row.due_time or time(23,59,59),preferences)<now)
    return {'date':str(day),'hearings':count(Hearing,Hearing.hearing_date==day,Hearing.status.in_(['Scheduled','Awaiting Order'])),
            'appointments':count(Appointment,Appointment.appointment_date==day,Appointment.status=='Scheduled',Appointment.archived_at.is_(None)),
            'tasks_due_today':count(Task,*active,Task.due_date==day),'overdue_tasks':overdue,
            'upcoming_deadlines':count(Task,*active,Task.due_date>day,Task.due_date<=day+timedelta(days=7)),
            'pending_followups':count(Notification,Notification.manual.is_(True),Notification.cancelled_at.is_(None),Notification.dismissed_at.is_(None),Notification.read_at.is_(None),Notification.nominal_at<=wall(day+timedelta(days=7),time(23,59),preferences)),
            'generated_at':now.isoformat()}

def reconcile_user(db,user,now=None):
    now=aware(now or utcnow());preferences=get_preferences(db,user.id,lock=True);today=now.astimezone(zone(preferences)).date();desired=set()
    events=db.scalars(select(NotificationEvent).where(NotificationEvent.user_id==user.id,NotificationEvent.processed_at.is_(None)).order_by(NotificationEvent.created_at).limit(500)).all()
    def plan(key,category,kind,identifier,when,priority='normal',details=None,once=False):
        desired.add(key)
        if not category_enabled(preferences,category):return
        return ensure(db,user,preferences,key,category,kind,identifier,when,priority,details,now,once)
    # Reuse recurring-task generation and its existing reminder synchronization.
    from app.services.planning_service import generate_recurrences
    for root in db.scalars(select(Task).where(Task.user_id==user.id,Task.recurrence_root_id.is_(None),Task.recurrence_kind!='none',Task.archived_at.is_(None))):generate_recurrences(db,user,root)
    db.flush()
    for reminder in db.scalars(select(HearingReminder).where(HearingReminder.user_id==user.id,HearingReminder.status.in_(['pending','scheduled_local','retry']))):
        hearing=owned_entity(db,user.id,'hearing',reminder.hearing_id)
        if not hearing or not hearing.reminder_enabled or hearing.status not in ('Scheduled','Awaiting Order') or hearing.hearing_date<today:continue
        if reminder.reminder_type=='custom':when=aware(reminder.scheduled_at)
        else:
            days={'day_of':0,'one_day':1,'two_days':2,'three_days':3,'one_week':7}.get(reminder.reminder_type)
            if days is None:continue
            when=wall(hearing.hearing_date-timedelta(days=days),hearing.hearing_time or preferences.reminder_time,preferences)
            reminder.scheduled_at=when if aware(reminder.scheduled_at)!=when else reminder.scheduled_at
        if when<now-timedelta(days=1):continue
        plan('hearing-reminder:'+str(reminder.id),'hearing','hearing',hearing.id,when,details={'requested_channel':reminder.delivery_channel})
    if preferences.hearing_auto_reminders:
        for hearing in db.scalars(select(Hearing).where(Hearing.user_id==user.id,Hearing.reminder_enabled.is_(True),Hearing.status.in_(['Scheduled','Awaiting Order']),Hearing.hearing_date>=today)):
            configured=db.scalars(select(HearingReminder).where(HearingReminder.user_id==user.id,HearingReminder.hearing_id==hearing.id,HearingReminder.status!='cancelled')).all()
            existing_days={{'day_of':0,'one_day':1,'two_days':2,'three_days':3,'one_week':7}.get(row.reminder_type) for row in configured}
            for days in preferences.hearing_reminder_days:
                if days in existing_days:continue
                when=wall(hearing.hearing_date-timedelta(days=days),hearing.hearing_time or preferences.reminder_time,preferences)
                if when>=now-timedelta(minutes=10):plan(f'hearing-auto:{hearing.id}:{days}','hearing','hearing',hearing.id,when)
    # A preference can have suppressed creation in Phase 9. Recover from the
    # existing task/appointment configuration, keeping its single reminder row.
    for kind,model in [('task',Task),('appointment',Appointment)]:
        if not category_enabled(preferences,kind):continue
        for source in db.scalars(select(model).where(model.user_id==user.id,model.reminder_minutes.is_not(None),model.archived_at.is_(None))):
            if source.status not in ('Pending','In Progress','Scheduled'):continue
            if kind=='task' and not source.due_date:continue
            when=(wall(source.due_date,source.due_time or time(18),preferences) if kind=='task' else wall(source.appointment_date,source.start_time,preferences))-timedelta(minutes=source.reminder_minutes)
            if when<=now:continue
            column=PlanningReminder.task_id if kind=='task' else PlanningReminder.appointment_id
            reminder=db.scalar(select(PlanningReminder).where(PlanningReminder.user_id==user.id,column==source.id))
            if not reminder:
                db.add(PlanningReminder(user_id=user.id,task_id=source.id if kind=='task' else None,appointment_id=source.id if kind=='appointment' else None,scheduled_at=when))
            elif reminder.status=='cancelled':reminder.status='pending';reminder.scheduled_at=when
    db.flush()
    for reminder in db.scalars(select(PlanningReminder).where(PlanningReminder.user_id==user.id,PlanningReminder.status=='pending')):
        kind='task' if reminder.task_id else 'appointment';identifier=reminder.task_id or reminder.appointment_id
        source=owned_entity(db,user.id,kind,identifier)
        if not source or source.archived_at or source.status not in ('Pending','In Progress','Scheduled'):continue
        if source.reminder_minutes is None:continue
        when=(wall(source.due_date,source.due_time or time(18),preferences) if kind=='task' and source.due_date else wall(source.appointment_date,source.start_time,preferences) if kind=='appointment' else None)
        if not when:continue
        when-=timedelta(minutes=source.reminder_minutes);reminder.scheduled_at=when if aware(reminder.scheduled_at)!=when else reminder.scheduled_at
        if when>=now-timedelta(days=1):plan('planning-reminder:'+str(reminder.id),kind,kind,source.id,when,'urgent' if kind=='task' and source.priority=='Urgent' else 'normal')
    for task in db.scalars(select(Task).where(Task.user_id==user.id,Task.status.in_(['Pending','In Progress']),Task.archived_at.is_(None),Task.due_date.is_not(None),Task.reminder_minutes.is_not(None))):
        if preferences.task_due_today and task.due_date==today:plan(f'task-today:{task.id}:{today}','task','task',task.id,wall(today,preferences.reminder_time,preferences),once=True)
        if preferences.task_high_priority and task.priority in ('High','Urgent') and today<=task.due_date<=today+timedelta(days=1):plan(f'task-priority:{task.id}:{task.due_date}','task','task',task.id,wall(today,preferences.reminder_time,preferences),'urgent' if task.priority=='Urgent' else 'high',once=True)
        if preferences.task_overdue_alerts and wall(task.due_date,task.due_time or time(23,59,59),preferences)<now:
            period=(today-task.due_date).days//preferences.overdue_repeat_days if preferences.overdue_repeat_days else 0
            key=f'task-overdue:{task.id}:{task.due_date}:{period}'
            when=stable_overdue_time(db,user.id,key,now)
            plan(key,'task','task',task.id,when,once=True)
    for agreement in db.scalars(select(FeeAgreement).where(FeeAgreement.user_id==user.id,FeeAgreement.status=='active',FeeAgreement.due_date.is_not(None))) if preferences.finance_auto_reminders else []:
        if balance(db,agreement)<=0:continue
        key=f'agreement-due:{agreement.id}:{agreement.due_date}';when=wall(agreement.due_date-timedelta(days=preferences.payment_due_days),preferences.reminder_time,preferences)
        plan(key,'payment','agreement',agreement.id,when if when>now else stable_overdue_time(db,user.id,key,now),once=True)
    for invoice in db.scalars(select(Invoice).where(Invoice.user_id==user.id,Invoice.status=='issued',Invoice.due_date.is_not(None))) if preferences.finance_auto_reminders else []:
        if invoice.agreement_id:
            agreement=owned_entity(db,user.id,'agreement',invoice.agreement_id)
            if not agreement or agreement.status!='active' or balance(db,agreement)<=0 or agreement.due_date:continue
            paid=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.user_id==user.id,Payment.agreement_id==agreement.id,Payment.status=='received'))
            if paid>=invoice.total:continue
        key=f'invoice-due:{invoice.id}:{invoice.due_date}';when=wall(invoice.due_date-timedelta(days=preferences.payment_due_days),preferences.reminder_time,preferences)
        plan(key,'payment','invoice',invoice.id,when if when>now else stable_overdue_time(db,user.id,key,now),once=True)
    latest_events={(event.entity_type,event.entity_id):event.id for event in events}
    for event in events:
        if event.event_name in ('hearing.changed','appointment.changed') and latest_events[(event.entity_type,event.entity_id)]==event.id:
            source=owned_entity(db,user.id,event.entity_type,event.entity_id)
            if source:
                fields=['hearing_date','hearing_time','status','follow_up_hearing_id'] if event.entity_type=='hearing' else ['appointment_date','start_time','end_time','status','archived_at']
                fingerprint=hashlib.sha256(json.dumps([str(getattr(source,key)) for key in fields]).encode()).hexdigest()[:24]
                identifier=source.follow_up_hearing_id if event.entity_type=='hearing' and source.follow_up_hearing_id else source.id
                plan(f'change:{event.entity_type}:{source.id}:{fingerprint}:{event.id}',event.entity_type,event.entity_type,identifier,now,details={'change':True},once=True)
        event.processed_at=now
    if preferences.daily_summary:
        for day in (today+timedelta(days=index) for index in range(7)):
            row=plan('daily-summary:'+str(day),'daily_summary',None,None,wall(day,preferences.daily_summary_time,preferences),details={'date':str(day)},once=True)
            if row and aware(row.nominal_at)<=now and 'summary' not in row.details:row.details={**row.details,'summary':daily_counts(db,user.id,day,preferences,now)}
    for row in db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.dismissed_at.is_(None))):
        if row.manual:
            if not valid_source(db,row,preferences,now):cancel(db,row,'preferences' if not category_enabled(preferences,row.category) else 'source_inactive',now)
            elif row.cancelled_at and row.cancellation_reason=='preferences' and aware(row.nominal_at)>now:row.cancelled_at=None;row.cancellation_reason=None;row.status='scheduled'
            if not row.cancelled_at:
                if not row.sent_at:row.title,row.message=generic_text(row.category,user.preferred_language)
                next_time=quiet_adjust(row.nominal_at,preferences,row.priority)
                if aware(row.scheduled_at)!=next_time:
                    for delivery in db.scalars(select(NotificationDelivery).where(NotificationDelivery.notification_id==row.id,NotificationDelivery.channel=='local',NotificationDelivery.status=='scheduled')):delivery.status='cancelled';delivery.error_code='rescheduled'
                row.channels=channels(preferences);row.scheduled_at=next_time
        elif row.category!='system' and not row.details.get('change') and not row.source_key.startswith('daily-summary:') and row.source_key not in desired and not row.sent_at:cancel(db,row,'source_inactive',now)
        if not category_enabled(preferences,row.category) and not row.sent_at:cancel(db,row,'preferences',now)
    preferences.notification_checked_at=now;db.flush()
    return preferences
