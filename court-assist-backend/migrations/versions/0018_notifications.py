"""Central notification outbox, encrypted devices and delivery history; reuse user preferences."""
from alembic import op
import sqlalchemy as sa
from app.models.notifications import Notification,UserDevice,NotificationDelivery,NotificationDeliveryAttempt,NotificationEvent
revision='0018_notifications'
down_revision='0017_research_library'
branch_labels=None
depends_on=None

def upgrade():
    existing={column['name'] for column in sa.inspect(op.get_bind()).get_columns('user_preferences')}
    columns=[]
    for name,default in [('push_notifications',False),('local_notifications',True),('email_notifications',False),('document_reminders',False),('draft_reminders',False),('hearing_auto_reminders',False),('urgent_quiet_override',False),('task_due_today',False),('task_overdue_alerts',False),('task_high_priority',False),('finance_auto_reminders',False)]:
        columns.append(sa.Column(name,sa.Boolean,nullable=False,server_default=sa.true() if default else sa.false()))
    columns.extend([sa.Column('hearing_reminder_days',sa.JSON,nullable=False,server_default='[1]'),sa.Column('reminder_time',sa.Time,nullable=False,server_default='09:00:00'),sa.Column('daily_summary_time',sa.Time,nullable=False,server_default='08:00:00'),sa.Column('quiet_start',sa.Time),sa.Column('quiet_end',sa.Time),sa.Column('overdue_repeat_days',sa.Integer),sa.Column('payment_due_days',sa.Integer,nullable=False,server_default='1')])
    for column in columns:
        if column.name not in existing:op.add_column('user_preferences',column)
    if 'notification_checked_at' not in existing:op.add_column('user_preferences',sa.Column('notification_checked_at',sa.DateTime(timezone=True)))
    if 'ix_user_preferences_notification_checked_at' not in {row['name'] for row in sa.inspect(op.get_bind()).get_indexes('user_preferences')}:op.create_index('ix_user_preferences_notification_checked_at','user_preferences',['notification_checked_at'])
    for model in (Notification,UserDevice,NotificationDelivery,NotificationDeliveryAttempt,NotificationEvent):model.__table__.create(op.get_bind(),checkfirst=True)

def downgrade():
    # Delivery attempts and previously explicit user choices are retained.
    pass
