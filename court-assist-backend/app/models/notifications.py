import uuid
from datetime import datetime,timezone
from sqlalchemy import DateTime,ForeignKey,ForeignKeyConstraint,Index,Integer,JSON,String,Text,Uuid,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.database.base import Base

def now():return datetime.now(timezone.utc)

class Notification(Base):
    __tablename__='notifications'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    category: Mapped[str]=mapped_column(String(24))
    title: Mapped[str]=mapped_column(String(180))
    message: Mapped[str]=mapped_column(String(500))
    entity_type: Mapped[str|None]=mapped_column(String(30))
    entity_id: Mapped[uuid.UUID|None]=mapped_column(Uuid)
    source_key: Mapped[str]=mapped_column(String(240))
    deduplication_key: Mapped[str]=mapped_column(String(64))
    nominal_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    scheduled_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str|None]=mapped_column(String(60))
    status: Mapped[str]=mapped_column(String(24),default='scheduled')
    priority: Mapped[str]=mapped_column(String(12),default='normal')
    channel: Mapped[str]=mapped_column(String(16),default='in_app')
    channels: Mapped[list]=mapped_column(JSON,default=list)
    details: Mapped[dict]=mapped_column(JSON,default=dict)
    manual: Mapped[bool]=mapped_column(default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('user_id','deduplication_key',name='uq_notification_dedup'),UniqueConstraint('id','user_id',name='uq_notification_id_owner'))

class UserDevice(Base):
    __tablename__='user_devices'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    installation_id: Mapped[uuid.UUID]=mapped_column(Uuid)
    platform: Mapped[str]=mapped_column(String(12))
    label: Mapped[str]=mapped_column(String(80),default='')
    token_hash: Mapped[str|None]=mapped_column(String(64),unique=True)
    token_ciphertext: Mapped[str|None]=mapped_column(Text)
    revoked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('user_id','installation_id',name='uq_device_owner_installation'),UniqueConstraint('id','user_id',name='uq_device_id_owner'))

class NotificationDelivery(Base):
    __tablename__='notification_deliveries'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    notification_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('notifications.id',ondelete='CASCADE'))
    device_id: Mapped[uuid.UUID|None]=mapped_column(Uuid,ForeignKey('user_devices.id'))
    channel: Mapped[str]=mapped_column(String(16))
    target_key: Mapped[str]=mapped_column(String(80))
    status: Mapped[str]=mapped_column(String(24),default='pending')
    attempt_count: Mapped[int]=mapped_column(Integer,default=0)
    next_attempt_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    local_scheduled_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str|None]=mapped_column(String(300))
    error_code: Mapped[str|None]=mapped_column(String(60))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('notification_id','channel','target_key',name='uq_notification_target'),UniqueConstraint('id','user_id',name='uq_delivery_id_owner'),ForeignKeyConstraint(['notification_id','user_id'],['notifications.id','notifications.user_id'],ondelete='CASCADE',name='fk_delivery_notification_owner'),ForeignKeyConstraint(['device_id','user_id'],['user_devices.id','user_devices.user_id'],name='fk_delivery_device_owner'))

class NotificationDeliveryAttempt(Base):
    __tablename__='notification_delivery_attempts'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    delivery_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('notification_deliveries.id'),index=True)
    notification_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('notifications.id'),index=True)
    channel: Mapped[str]=mapped_column(String(16))
    number: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(24))
    error_code: Mapped[str|None]=mapped_column(String(60))
    provider_message_id: Mapped[str|None]=mapped_column(String(300))
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('delivery_id','number',name='uq_notification_attempt_number'),ForeignKeyConstraint(['delivery_id','user_id'],['notification_deliveries.id','notification_deliveries.user_id'],name='fk_attempt_delivery_owner'),ForeignKeyConstraint(['notification_id','user_id'],['notifications.id','notifications.user_id'],name='fk_attempt_notification_owner'))

class NotificationEvent(Base):
    __tablename__='notification_events'
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(Uuid,ForeignKey('users.id',ondelete='CASCADE'),index=True)
    entity_type: Mapped[str]=mapped_column(String(30))
    entity_id: Mapped[uuid.UUID]=mapped_column(Uuid)
    event_name: Mapped[str]=mapped_column(String(40))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    processed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

Index('ix_notifications_owner_due',Notification.user_id,Notification.scheduled_at,Notification.read_at)
Index('ix_notifications_owner_source',Notification.user_id,Notification.source_key)
Index('ix_notification_deliveries_due',NotificationDelivery.status,NotificationDelivery.next_attempt_at)
Index('ix_notification_events_pending',NotificationEvent.processed_at,NotificationEvent.user_id)

Index('ix_notifications_dispatch_due',Notification.status,Notification.scheduled_at)
