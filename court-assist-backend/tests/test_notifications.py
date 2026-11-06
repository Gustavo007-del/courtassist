import os
import uuid
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ.setdefault('DATABASE_URL','sqlite+pysqlite:///:memory:')
os.environ.setdefault('JWT_SECRET_KEY','test-only-secret-key-with-at-least-32-chars')
from app import models
from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.api.v1.dependencies import current_user
from app.models.user import User, UserPreference
from app.models.case import Case
from app.models.client import Client
from app.models.hearing import Hearing, HearingReminder
from app.models.planning import Task, Appointment, PlanningReminder
from app.models.phase10 import FeeAgreement, Payment, DraftDocument
from app.models.finance import Invoice
from app.models.notifications import Notification, NotificationDelivery, NotificationDeliveryAttempt, NotificationEvent, UserDevice
from app.services import notification_service as service, notification_delivery as delivery, notification_channels as channels
from app.services.notification_devices import register
from app.schemas.notifications import RegisterDevice
from app.core.config import get_settings

NOW=datetime(2026,11,6,4,0,tzinfo=timezone.utc)

@pytest.fixture
def setup(monkeypatch):
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    event.listen(engine,'connect',lambda connection,_:connection.execute('PRAGMA foreign_keys=ON'))
    Base.metadata.create_all(engine)
    settings=get_settings();monkeypatch.setattr(settings,'fcm_enabled',True);monkeypatch.setattr(settings,'notification_token_keys',Fernet.generate_key().decode())
    with Session(engine,expire_on_commit=False) as db:
        one=User(full_name='PRIVATE advocate',password_hash='unused',email='fixture@example.com',is_email_verified=True)
        two=User(full_name='Other advocate',password_hash='unused')
        db.add_all([one,two]);db.flush()
        prefs=UserPreference(user_id=one.id);other=UserPreference(user_id=two.id)
        db.add_all([prefs,other]);db.flush()
        case=Case(user_id=one.id,case_title='PRIVATE case title',case_number='PRIVATE number',case_category='Civil',filing_date=date(2026,1,1),current_status='Pending',description='',priority='Medium')
        client=Client(user_id=one.id,client_type='Individual',full_name='PRIVATE client',phone_number='9999999999',address='Fixture',city='Kochi',district='Ernakulam',state='Kerala',postal_code='682001')
        db.add_all([case,client]);db.commit()
        active=[one]
        def session_override():yield db
        app.dependency_overrides[get_db]=session_override
        app.dependency_overrides[current_user]=lambda:active[0]
        with TestClient(app) as api:yield db,api,active,one,two,prefs,case,client,engine
    app.dependency_overrides.clear();engine.dispose()

def hearing(db,user,case,day=date(2026,11,8),clock=None):
    row=Hearing(user_id=user.id,case_id=case.id,hearing_date=day,hearing_time=clock,hearing_type='Arguments',purpose='PRIVATE arguments',status='Scheduled')
    db.add(row);db.flush();return row

def notification(db,user,prefs,kind='system',identifier=None,when=NOW,key='fixture'):
    row=service.ensure(db,user,prefs,key,kind if kind not in ('agreement','invoice') else 'payment',None if kind=='system' else kind,identifier,when,now=NOW)
    db.commit();return row

def device(db,user,token='mock-token-with-private-content-123456789'):
    return register(db,user,RegisterDevice(installation_id=uuid.uuid4(),platform='android',token=token))

def test_hearing_timezone_date_only_idempotency_and_reschedule(setup):
    db,api,active,user,other,prefs,case,*_=setup
    prefs.timezone='Asia/Kolkata';prefs.reminder_time=time(8,15)
    row=hearing(db,user,case)
    reminder=HearingReminder(user_id=user.id,hearing_id=row.id,reminder_type='two_days',scheduled_at=NOW,delivery_channel='local')
    db.add(reminder);db.commit()
    service.reconcile_user(db,user,NOW);db.commit()
    first=db.scalar(select(Notification).where(Notification.entity_id==row.id))
    assert service.aware(first.scheduled_at)==datetime(2026,11,6,2,45,tzinfo=timezone.utc)
    assert row.hearing_time is None
    user.preferred_language='ml';db.commit()
    service.reconcile_user(db,user,NOW);db.commit()
    assert db.scalar(select(func.count()).select_from(Notification))==1
    assert first.message==channels.generic_text('hearing','ml')[1]
    result=api.post(f'/api/v1/hearings/{row.id}/reschedule',json={'hearing_date':'2026-11-10','hearing_time':None,'reason':'Advocate changed date'})
    assert result.status_code==200,result.text
    service.reconcile_user(db,user,NOW);db.commit();db.refresh(first)
    assert first.cancelled_at
    next_id=row.follow_up_hearing_id
    inherited=db.scalar(select(HearingReminder).where(HearingReminder.hearing_id==next_id))
    assert inherited.reminder_type=='two_days'
    assert service.aware(inherited.scheduled_at)==datetime(2026,11,8,2,45,tzinfo=timezone.utc)
    assert db.scalar(select(Notification).where(Notification.entity_id==next_id,Notification.details['change'].as_boolean()==True))

def test_quiet_hours_timezone_and_urgent_override(setup):
    db,api,active,user,other,prefs,*_=setup
    prefs.quiet_start=time(22);prefs.quiet_end=time(7)
    night=datetime(2026,11,6,18,0,tzinfo=timezone.utc)
    assert service.quiet_adjust(night,prefs)==datetime(2026,11,7,1,30,tzinfo=timezone.utc)
    assert service.quiet_adjust(night,prefs,'urgent')>night
    prefs.urgent_quiet_override=True
    assert service.quiet_adjust(night,prefs,'urgent')==night
    prefs.timezone='America/New_York';prefs.urgent_quiet_override=False
    assert service.quiet_adjust(datetime(2026,11,1,5,30,tzinfo=timezone.utc),prefs)==datetime(2026,11,1,12,tzinfo=timezone.utc)
    assert api.patch('/api/v1/notification-preferences',json={'quiet_start':'22:00','quiet_end':None}).status_code==422
    assert api.patch('/api/v1/notification-preferences',json={'timezone':'Not/AZone'}).status_code==422

def test_tasks_reschedule_complete_overdue_and_no_repeats(setup):
    db,api,active,user,other,prefs,*_=setup
    task=Task(user_id=user.id,title='PRIVATE task',due_date=date(2026,11,7),due_time=time(10),reminder_minutes=60)
    db.add(task);db.flush();reminder=PlanningReminder(user_id=user.id,task_id=task.id,scheduled_at=NOW)
    db.add(reminder);db.commit();service.reconcile_user(db,user,NOW);db.commit()
    original=db.scalar(select(Notification).where(Notification.entity_id==task.id))
    task.due_date=date(2026,11,8);db.commit();service.reconcile_user(db,user,NOW);db.commit()
    assert original.cancelled_at
    current=db.scalar(select(Notification).where(Notification.entity_id==task.id,Notification.cancelled_at.is_(None)))
    assert current.id!=original.id
    task.status='Completed';db.commit();service.reconcile_user(db,user,NOW);db.commit();assert current.cancelled_at
    task.status='Pending';task.due_date=date(2026,11,4);prefs.task_overdue_alerts=True
    db.commit();service.reconcile_user(db,user,NOW);db.commit()
    overdue=db.scalar(select(Notification).where(Notification.source_key.like('task-overdue:%')))
    assert overdue
    service.reconcile_user(db,user,NOW+timedelta(hours=1));db.commit()
    assert len(db.scalars(select(Notification).where(Notification.source_key.like('task-overdue:%'))).all())==1
    task.reminder_minutes=None;db.commit();service.reconcile_user(db,user,NOW);db.commit();assert overdue.cancelled_at

def test_appointment_change_and_cancellation(setup):
    db,api,active,user,other,prefs,*_=setup
    row=Appointment(user_id=user.id,title='PRIVATE appointment',appointment_date=date(2026,11,7),start_time=time(10),end_time=time(11),reminder_minutes=30)
    db.add(row);db.flush();db.add(PlanningReminder(user_id=user.id,appointment_id=row.id,scheduled_at=NOW));db.commit()
    service.reconcile_user(db,user,NOW);db.commit()
    planned=db.scalar(select(Notification).where(Notification.entity_id==row.id))
    row.status='Cancelled';db.commit();service.reconcile_user(db,user,NOW);db.commit()
    assert planned.cancelled_at
    changes=db.scalars(select(Notification).where(Notification.source_key.like('change:appointment:%'))).all()
    assert len(changes)==1 and changes[0].details['change']
    service.reconcile_user(db,user,NOW);db.commit();assert len(db.scalars(select(Notification).where(Notification.source_key.like('change:appointment:%'))).all())==1

def test_financial_reminders_actual_received_balances_and_invoice(setup):
    db,api,active,user,other,prefs,case,client,*_=setup
    agreement=FeeAgreement(user_id=user.id,client_id=client.id,amount=Decimal('12000'),due_date=date(2026,11,7))
    db.add(agreement);db.flush()
    invoice=Invoice(user_id=user.id,client_id=client.id,number='PRIVATE invoice',issue_date=date(2026,11,1),due_date=date(2026,11,7),total=Decimal('12000'),status='issued',agreement_id=agreement.id)
    db.add(invoice);db.commit();service.reconcile_user(db,user,NOW);db.commit()
    assert not db.scalar(select(Notification).where(Notification.category=='payment'))
    prefs.finance_auto_reminders=True;db.commit();service.reconcile_user(db,user,NOW);db.commit()
    rows=db.scalars(select(Notification).where(Notification.category=='payment')).all()
    assert len(rows)==1 # Agreement and its invoice must not double alert.
    assert '12000' not in rows[0].message and 'PRIVATE' not in rows[0].message
    payment=Payment(user_id=user.id,client_id=client.id,agreement_id=agreement.id,amount=Decimal('12000'),payment_date=NOW.date(),status='pending')
    db.add(payment);db.commit();service.reconcile_user(db,user,NOW);db.commit();assert not rows[0].cancelled_at
    payment.status='received';db.commit();service.reconcile_user(db,user,NOW);db.commit();assert rows[0].cancelled_at

def test_daily_summary_actual_counts_and_once_per_day(setup):
    db,api,active,user,other,prefs,case,*_=setup
    prefs.daily_summary=True
    hearing(db,user,case,day=NOW.date())
    db.add_all([Task(user_id=user.id,title='due',due_date=NOW.date()),Task(user_id=user.id,title='late',due_date=NOW.date()-timedelta(days=1)),Task(user_id=other.id,title='not mine',due_date=NOW.date())]);db.commit()
    service.reconcile_user(db,user,NOW);db.commit()
    row=db.scalar(select(Notification).where(Notification.source_key=='daily-summary:2026-11-06'))
    assert row.details['summary']['hearings']==1 and row.details['summary']['tasks_due_today']==1 and row.details['summary']['overdue_tasks']==1
    count=db.scalar(select(func.count()).select_from(Notification))
    service.reconcile_user(db,user,NOW+timedelta(minutes=1));db.commit();assert db.scalar(select(func.count()).select_from(Notification))==count
    assert 'PRIVATE' not in row.message

def test_registration_secrets_revocation_and_token_transfer(setup):
    db,api,active,user,other,prefs,*_=setup
    installation=str(uuid.uuid4());raw='private-device-token-with-sufficient-length'
    response=api.post('/api/v1/notifications/register-device',json={'installation_id':installation,'platform':'android','token':raw})
    assert response.status_code==200 and raw not in response.text and 'ciphertext' not in response.text
    identifier=response.json()['id'];row=db.get(UserDevice,uuid.UUID(identifier))
    assert raw not in row.token_ciphertext and channels.decrypt_token(row.token_ciphertext)==raw
    assert api.delete('/api/v1/notifications/devices/'+identifier).status_code==204
    assert api.post('/api/v1/notifications/register-device',json={'installation_id':installation,'platform':'android','token':raw}).status_code==409
    assert api.post('/api/v1/notifications/register-device',json={'installation_id':installation,'platform':'android','token':raw,'reactivate':True}).status_code==200
    active[0]=other
    transferred=api.post('/api/v1/notifications/register-device',json={'installation_id':str(uuid.uuid4()),'platform':'android','token':raw})
    assert transferred.status_code==200;db.refresh(row);assert row.revoked_at and not row.token_ciphertext
    assert api.delete('/api/v1/notifications/devices/'+identifier).status_code==404

def test_local_plan_ack_no_duplicate_push_and_cross_user(setup,monkeypatch):
    db,api,active,user,other,prefs,*_=setup
    prefs.push_notifications=True;db.commit();dev=device(db,user)
    future=service.utcnow()+timedelta(minutes=10)
    row=notification(db,user,prefs,when=future)
    plan=api.get('/api/v1/notifications/local-plan',params={'device_id':str(dev.id)})
    assert plan.status_code==200,plan.text
    value=plan.json()['plans'][0]
    payload={'device_id':str(dev.id),'notification_id':str(row.id),'scheduled_at':value['scheduled_at']}
    assert api.post('/api/v1/notifications/local-ack',json=payload).status_code==200
    assert api.post('/api/v1/notifications/local-ack',json=payload).status_code==200
    assert db.scalar(select(func.count()).select_from(NotificationDeliveryAttempt))==1
    delivery.prepare_due(db,future+timedelta(seconds=2))
    assert not db.scalar(select(NotificationDelivery).where(NotificationDelivery.channel=='push'))
    assert row.delivered_at is None and row.sent_at is None
    active[0]=other
    for method,path,body in [('get',f'/notifications/{row.id}',None),('patch',f'/notifications/{row.id}/read',{}),('post',f'/notifications/{row.id}/dismiss',{}),('post','/notifications/local-ack',payload)]:
        result=getattr(api,method)('/api/v1'+path,**({'json':body} if body is not None else {}));assert result.status_code==404
    assert api.get('/api/v1/notifications/local-plan',params={'device_id':str(dev.id)}).status_code==404
    assert api.get('/api/v1/notifications?scheduled=true').json()['total']==0
    active[0]=user
    assert api.post(f'/api/v1/notifications/{row.id}/dismiss').status_code==200
    assert str(row.id) not in api.get('/api/v1/notifications/local-plan',params={'device_id':str(dev.id)}).json()['active_ids']

def test_manual_draft_followup_archive_and_center(setup):
    db,api,active,user,other,prefs,*_=setup
    draft=DraftDocument(user_id=user.id,title='PRIVATE draft',category='Petition',content='PRIVATE content')
    db.add(draft);db.commit()
    future=service.utcnow()+timedelta(hours=2)
    data={'entity_type':'draft','entity_id':str(draft.id),'scheduled_at':future.isoformat(),'purpose':'filing'}
    assert api.post('/api/v1/notifications/reminders',json=data).status_code==409
    assert api.patch('/api/v1/notification-preferences',json={'draft_reminders':True}).status_code==200
    result=api.post('/api/v1/notifications/reminders',json=data);assert result.status_code==201,result.text
    row=db.get(Notification,uuid.UUID(result.json()['id']));assert row.manual and 'PRIVATE' not in row.message
    assert draft.status=='draft'
    active[0]=other;assert api.post('/api/v1/notifications/reminders',json=data).status_code==404
    active[0]=user
    assert api.patch(f'/api/v1/notifications/{row.id}/read').status_code==200
    assert api.get('/api/v1/notifications?scheduled=true&read_only=true').json()['total']==1
    replacement=api.post('/api/v1/notifications/reminders',json={**data,'replaces':str(row.id),'scheduled_at':(future+timedelta(hours=1)).isoformat()})
    assert replacement.status_code==201 and replacement.json()['id']!=str(row.id)
    assert row.cancellation_reason=='rescheduled'
    draft.archived_at=service.utcnow();db.commit();service.reconcile_user(db,user);db.commit();assert row.cancelled_at

def test_delivery_transient_retry_acceptance_and_lease_recovery(setup,monkeypatch):
    db,api,active,user,other,prefs,*_=setup
    prefs.push_notifications=True;prefs.local_notifications=False;db.commit();dev=device(db,user)
    row=notification(db,user,prefs,when=service.utcnow()-timedelta(seconds=1))
    delivery.prepare_due(db);job=db.scalar(select(NotificationDelivery));assert job
    calls=[]
    def flaky(*args):
        calls.append(1)
        if len(calls)==1:raise channels.ProviderFailure('provider_unavailable',retryable=True)
        return 'provider/accepted'
    monkeypatch.setattr(delivery,'send_push',flaky)
    now=service.utcnow();delivery.send_one(db,job.id,now);assert job.status=='pending' and job.attempt_count==1
    assert service.aware(job.next_attempt_at)==now+timedelta(seconds=60)
    assert not delivery.send_one(db,job.id,now+timedelta(seconds=59))
    delivery.send_one(db,job.id,now+timedelta(seconds=61));assert job.status=='sent' and row.sent_at and row.delivered_at is None
    delivery.dispatch(db,now+timedelta(seconds=62));assert len(calls)==2
    second=notification(db,user,prefs,when=now,key='recovery');job2=delivery.target(db,second,'push',dev,now)
    job2.status='processing';job2.attempt_count=1;job2.lease_until=now-timedelta(seconds=1)
    db.add(NotificationDeliveryAttempt(user_id=user.id,notification_id=second.id,delivery_id=job2.id,channel='push',number=1,status='started'));db.commit()
    delivery.send_one(db,job2.id,now);assert job2.status=='sent' and job2.attempt_count==2
    previous=db.scalar(select(NotificationDeliveryAttempt).where(NotificationDeliveryAttempt.delivery_id==job2.id,NotificationDeliveryAttempt.number==1))
    assert previous.status=='unknown' and previous.error_code=='worker_interrupted'

def test_invalid_token_and_retry_limit(setup,monkeypatch):
    db,api,active,user,other,prefs,*_=setup
    prefs.push_notifications=True;prefs.local_notifications=False;db.commit();dev=device(db,user)
    row=notification(db,user,prefs,when=service.utcnow());job=delivery.target(db,row,'push',dev,service.utcnow());db.commit()
    def invalid(*_):raise channels.ProviderFailure('invalid_device_token',invalid_token=True)
    monkeypatch.setattr(delivery,'send_push',invalid);delivery.send_one(db,job.id);assert job.status=='failed' and dev.revoked_at and not dev.token_ciphertext
    dev=register(db,user,RegisterDevice(installation_id=dev.installation_id,platform='android',token='another-device-token-with-sufficient-length',reactivate=True))
    second=notification(db,user,prefs,when=service.utcnow(),key='bounded');job2=delivery.target(db,second,'push',dev,service.utcnow());db.commit()
    def transient(*_):raise channels.ProviderFailure('unavailable',retryable=True)
    monkeypatch.setattr(delivery,'send_push',transient)
    now=service.utcnow()
    for index in range(8):delivery.send_one(db,job2.id,now+timedelta(hours=index))
    assert job2.attempt_count==get_settings().notification_max_attempts and job2.status=='failed'

def test_fcm_adapter_generic_payload_and_optional_email(setup,monkeypatch):
    from firebase_admin import messaging
    db,api,active,user,other,prefs,*_=setup
    dev=device(db,user);row=notification(db,user,prefs)
    monkeypatch.setattr(channels,'firebase_app',lambda:object())
    captured=[]
    monkeypatch.setattr(messaging,'send',lambda payload,app=None:captured.append(payload) or 'accepted')
    assert channels.send_push(row,dev)=='accepted'
    payload=captured[0]
    assert set(payload.data)=={'notification_id','category'} and 'PRIVATE' not in payload.notification.body
    assert payload.android.notification.tag=='court-assist-'+str(row.id)
    def invalid(*args,**kwargs):raise messaging.UnregisteredError('token raw provider content')
    monkeypatch.setattr(messaging,'send',invalid)
    with pytest.raises(channels.ProviderFailure) as error:channels.send_push(row,dev)
    assert error.value.invalid_token and 'raw' not in str(error.value)
    settings=get_settings();monkeypatch.setattr(settings,'smtp_host','fixture.smtp');monkeypatch.setattr(settings,'smtp_from','notifications@example.com')
    sent=[]
    class SMTP:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def starttls(self,**kwargs):pass
        def login(self,*args):pass
        def send_message(self,message):sent.append(message);return {}
    monkeypatch.setattr(channels.smtplib,'SMTP',SMTP)
    assert channels.send_email(row,user,uuid.uuid4())
    assert 'PRIVATE' not in sent[0].get_content()
    user.is_email_verified=False
    with pytest.raises(channels.ProviderFailure):channels.send_email(row,user,uuid.uuid4())

def test_event_atomicity_preference_disable_and_worker_restart(setup,monkeypatch):
    db,api,active,user,other,prefs,case,client,engine=setup
    before=db.scalar(select(func.count()).select_from(NotificationEvent))
    db.add(Task(user_id=user.id,title='rollback'));db.flush();db.rollback()
    assert db.scalar(select(func.count()).select_from(NotificationEvent))==before
    prefs.push_notifications=True;prefs.local_notifications=False;db.commit();dev=device(db,user)
    row=notification(db,user,prefs,kind='hearing',identifier=hearing(db,user,case).id,when=service.utcnow())
    job=delivery.target(db,row,'push',dev,service.utcnow());db.commit()
    prefs.hearing_reminders=False;db.commit()
    monkeypatch.setattr(delivery,'send_push',lambda *_:pytest.fail('Disabled category reached provider'))
    delivery.send_one(db,job.id);assert job.status=='cancelled'
    from app.workers import notifications as worker
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr(worker,'SessionLocal',sessionmaker(bind=engine))
    worker.tick.run();worker.tick.run();db.expire_all()
    assert db.get(Notification,row.id).cancelled_at

def test_additive_migration_preserves_legacy_preferences_and_reminders():
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from pathlib import Path
    engine=create_engine('sqlite+pysqlite:///:memory:')
    omitted={'notifications','user_devices','notification_deliveries','notification_delivery_attempts','notification_events','user_preferences'}
    Base.metadata.create_all(engine,tables=[table for name,table in Base.metadata.tables.items() if name not in omitted])
    old=sa.MetaData()
    Base.metadata.tables['users'].to_metadata(old)
    new_columns={'push_notifications','local_notifications','email_notifications','document_reminders','draft_reminders','hearing_auto_reminders','hearing_reminder_days','reminder_time','daily_summary_time','quiet_start','quiet_end','urgent_quiet_override','task_due_today','task_overdue_alerts','task_high_priority','overdue_repeat_days','payment_due_days','finance_auto_reminders','notification_checked_at'}
    legacy=sa.Table('user_preferences',old,*[column._copy() for column in UserPreference.__table__.columns if column.name not in new_columns])
    legacy.create(engine)
    identifier=uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(User.__table__.insert().values(id=identifier,full_name='Legacy advocate',password_hash='unused'))
        connection.execute(legacy.insert().values(user_id=identifier,hearing_reminders=False,payment_reminders=False,daily_summary=True,timezone='Asia/Kolkata'))
        case_id,hearing_id,reminder_id=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
        connection.execute(Case.__table__.insert().values(id=case_id,user_id=identifier,case_title='Legacy case',case_number='Legacy fixture',case_category='Civil',filing_date=date(2026,1,1),current_status='Pending',description='',priority='Medium'))
        connection.execute(Hearing.__table__.insert().values(id=hearing_id,user_id=identifier,case_id=case_id,hearing_date=date(2026,11,8),hearing_type='Arguments',purpose='Legacy fixture',status='Scheduled'))
        connection.execute(HearingReminder.__table__.insert().values(id=reminder_id,user_id=identifier,hearing_id=hearing_id,reminder_type='custom',delivery_channel='local',scheduled_at=NOW,status='pending'))
        module_path=Path(__file__).parents[1]/'migrations/versions/0018_notifications.py'
        spec=importlib.util.spec_from_file_location('phase13_migration',module_path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade();migration.upgrade() # Defensive checkfirst path is repeatable.
        row=connection.execute(sa.select(UserPreference.__table__)).mappings().one()
        assert row['hearing_reminders'] is False and row['payment_reminders'] is False and row['daily_summary'] is True
        assert row['push_notifications'] is False and row['local_notifications'] is True
        assert row['notification_checked_at'] is None
        retained=connection.execute(sa.select(HearingReminder.__table__).where(HearingReminder.id==reminder_id)).mappings().one()
        assert retained['reminder_type']=='custom' and retained['status']=='pending'
        assert omitted-{'user_preferences'}<=set(sa.inspect(connection).get_table_names())
    engine.dispose()

def test_device_logout_permission_withdrawal_and_owner_constraints(setup):
    from sqlalchemy.exc import IntegrityError
    db,api,active,user,other,prefs,*_=setup
    dev=device(db,user)
    row=notification(db,user,prefs,when=service.utcnow()+timedelta(minutes=15))
    plan=api.get('/api/v1/notifications/local-plan',params={'device_id':str(dev.id)}).json()['plans'][0]
    assert api.post('/api/v1/notifications/local-ack',json={'device_id':str(dev.id),'notification_id':str(row.id),'scheduled_at':plan['scheduled_at']}).status_code==200
    assert api.get('/api/v1/notifications/local-plan',params={'device_id':str(dev.id),'local_allowed':'false'}).json()['plans']==[]
    assert db.scalar(select(NotificationDelivery)).status=='cancelled'
    other_device=device(db,other,token='different-token-with-sufficient-length')
    db.add(NotificationDelivery(user_id=user.id,notification_id=row.id,device_id=other_device.id,channel='push',target_key='forbidden'))
    with pytest.raises(IntegrityError):db.commit()
    db.rollback()
    response=api.post('/api/v1/auth/logout',json={'refresh_token':'expired-but-authenticated-request','installation_id':str(dev.installation_id)})
    assert response.status_code==200;db.refresh(dev);db.refresh(other_device)
    assert dev.revoked_at and not other_device.revoked_at

def test_dispatch_batch_does_not_starve_new_notifications(setup):
    db,api,active,user,other,prefs,*_=setup
    for index in range(5):notification(db,user,prefs,when=service.utcnow(),key='batch-'+str(index))
    assert delivery.prepare_due(db,limit=2)==2
    assert delivery.prepare_due(db,limit=2)==2
    assert delivery.prepare_due(db,limit=2)==1
    assert delivery.prepare_due(db,limit=2)==0

def test_manual_quiet_reschedule_invalidates_local_reservation(setup):
    db,api,active,user,other,prefs,*_=setup
    prefs.draft_reminders=True
    draft=DraftDocument(user_id=user.id,title='Draft');db.add(draft);db.commit()
    row=notification(db,user,prefs,kind='draft',identifier=draft.id,when=datetime(2026,11,6,18,tzinfo=timezone.utc))
    row.manual=True;dev=device(db,user);local=delivery.target(db,row,'local',dev,NOW)
    local.status='scheduled';local.local_scheduled_at=row.scheduled_at;db.commit()
    prefs.quiet_start=time(22);prefs.quiet_end=time(7);db.commit()
    service.reconcile_user(db,user,NOW);db.commit()
    assert local.status=='cancelled' and local.error_code=='rescheduled'
    assert service.aware(row.scheduled_at)==datetime(2026,11,7,1,30,tzinfo=timezone.utc)

def test_reenable_preferences_recovers_existing_task_configuration(setup):
    db,api,active,user,other,prefs,*_=setup
    prefs.task_reminders=False
    task=Task(user_id=user.id,title='Configured while disabled',due_date=date(2026,11,8),reminder_minutes=30)
    db.add(task);db.commit();service.reconcile_user(db,user,NOW);db.commit()
    assert not db.scalar(select(PlanningReminder).where(PlanningReminder.task_id==task.id))
    prefs.task_reminders=True;db.commit();service.reconcile_user(db,user,NOW);db.commit()
    assert db.scalar(select(PlanningReminder).where(PlanningReminder.task_id==task.id)).status=='pending'
    assert db.scalar(select(Notification).where(Notification.entity_id==task.id)).cancelled_at is None
