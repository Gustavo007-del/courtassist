"""Provider adapters. Provider acceptance is 'sent', never proof of delivery."""
import hashlib
import smtplib
import ssl
import threading
from email.message import EmailMessage
from datetime import timedelta
from cryptography.fernet import Fernet,MultiFernet,InvalidToken
from app.core.config import get_settings

TEXT={
 'en':{'title':'Court Assist','hearing':'A court hearing reminder is due.','task':'A task reminder is due.','appointment':'An appointment reminder is due.','payment':'A payment follow-up is due.','document':'A document follow-up is due.','draft':'A draft review reminder is due.','system':'An update is available in Court Assist.','daily_summary':'Your daily advocate summary is ready.','hearing_change':'A court hearing has changed. Open Court Assist to review it.','appointment_change':'An appointment has changed. Open Court Assist to review it.'},
 'ml':{'title':'കോർട്ട് അസിസ്റ്റ്','hearing':'കോടതി ഹിയറിംഗ് ഓർമ്മപ്പെടുത്തൽ ഉണ്ട്.','task':'ഒരു ടാസ്‌ക് ഓർമ്മപ്പെടുത്തൽ ഉണ്ട്.','appointment':'ഒരു കൂടിക്കാഴ്ച ഓർമ്മപ്പെടുത്തൽ ഉണ്ട്.','payment':'പണമടവ് സംബന്ധിച്ച തുടർനടപടി ഓർമ്മപ്പെടുത്തൽ ഉണ്ട്.','document':'രേഖ സംബന്ധിച്ച തുടർനടപടി ഓർമ്മപ്പെടുത്തൽ ഉണ്ട്.','draft':'കരട് പരിശോധന ഓർമ്മപ്പെടുത്തൽ ഉണ്ട്.','system':'കോർട്ട് അസിസ്റ്റിൽ ഒരു അപ്‌ഡേറ്റ് ലഭ്യമാണ്.','daily_summary':'നിങ്ങളുടെ ദൈനംദിന സംഗ്രഹം തയ്യാറാണ്.','hearing_change':'കോടതി ഹിയറിംഗിൽ മാറ്റമുണ്ട്. കോർട്ട് അസിസ്റ്റിൽ പരിശോധിക്കുക.','appointment_change':'കൂടിക്കാഴ്ചയിൽ മാറ്റമുണ്ട്. കോർട്ട് അസിസ്റ്റിൽ പരിശോധിക്കുക.'}}

def generic_text(category,language='en',change=False):
    values=TEXT.get(language,TEXT['en']);key=category+'_change' if change else category
    return values['title'],values.get(key,values['system'])

class ProviderFailure(Exception):
    def __init__(self,code,retryable=False,invalid_token=False):
        self.code=code;self.retryable=retryable;self.invalid_token=invalid_token
        super().__init__(code)

def token_cipher():
    try:
        keys=[Fernet(value.strip().encode()) for value in get_settings().notification_token_keys.split(',') if value.strip()]
        if not keys:raise ValueError()
        return MultiFernet(keys)
    except (ValueError,TypeError):raise ProviderFailure('token_storage_unavailable')

def encrypt_token(value):return token_cipher().encrypt(value.encode()).decode()
def decrypt_token(value):
    try:return token_cipher().decrypt(value.encode()).decode()
    except (InvalidToken,ValueError,AttributeError):raise ProviderFailure('token_unreadable')
def hash_token(value):return hashlib.sha256(value.encode()).hexdigest()

def capabilities(user=None):
    settings=get_settings()
    try:token_cipher();encrypted=True
    except ProviderFailure:encrypted=False
    return {'push_configured':settings.fcm_enabled and encrypted,'email_configured':bool(settings.smtp_host and settings.smtp_from),'email_verified':bool(user and user.email and user.is_email_verified),'whatsapp_supported':False,'push_platforms':['android']}

_firebase_lock=threading.Lock()
def firebase_app():
    settings=get_settings()
    if not settings.fcm_enabled:raise ProviderFailure('push_not_configured')
    import firebase_admin
    from firebase_admin import credentials
    with _firebase_lock:
        try:return firebase_admin.get_app('court_assist_notifications')
        except ValueError:
            try:
                credential=credentials.Certificate(settings.fcm_credentials_file) if settings.fcm_credentials_file else credentials.ApplicationDefault()
                options={'projectId':settings.fcm_project_id} if settings.fcm_project_id else None
                return firebase_admin.initialize_app(credential,options,name='court_assist_notifications')
            except Exception:raise ProviderFailure('push_configuration_error')

def send_push(notification,device):
    from firebase_admin import messaging
    app=firebase_app()
    token=decrypt_token(device.token_ciphertext)
    payload=messaging.Message(token=token,notification=messaging.Notification(title=notification.title,body=notification.message),
        data={'notification_id':str(notification.id),'category':notification.category},
        android=messaging.AndroidConfig(priority='high' if notification.priority=='urgent' else 'normal',ttl=timedelta(hours=1),collapse_key=str(notification.id),notification=messaging.AndroidNotification(channel_id='court-assist-reminders',tag='court-assist-'+str(notification.id))))
    try:return messaging.send(payload,app=app)
    except messaging.UnregisteredError:raise ProviderFailure('invalid_device_token',invalid_token=True)
    except (messaging.QuotaExceededError,):raise ProviderFailure('provider_quota',retryable=True)
    except Exception as error:
        from firebase_admin import exceptions
        if isinstance(error,(exceptions.UnavailableError,exceptions.InternalError,exceptions.DeadlineExceededError)):raise ProviderFailure('provider_unavailable',retryable=True)
        if isinstance(error,(exceptions.UnauthenticatedError,exceptions.PermissionDeniedError)):raise ProviderFailure('push_configuration_error')
        if isinstance(error,exceptions.InvalidArgumentError):raise ProviderFailure('provider_invalid_argument')
        raise ProviderFailure('provider_request_error',retryable=True)

def send_email(notification,user,delivery_id):
    settings=get_settings()
    if not settings.smtp_host or not settings.smtp_from:raise ProviderFailure('email_not_configured')
    if not user.email or not user.is_email_verified:raise ProviderFailure('email_not_verified')
    message=EmailMessage();message['Subject']=notification.title;message['From']=settings.smtp_from;message['To']=user.email;message['Message-ID']=f'<{delivery_id}@court-assist.local>'
    message.set_content(notification.message+'\n\nOpen Court Assist to view this notification securely.\nNotification: '+str(notification.id))
    try:
        connection=smtplib.SMTP_SSL(settings.smtp_host,settings.smtp_port,timeout=15,context=ssl.create_default_context()) if settings.smtp_port==465 else smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15)
        with connection as smtp:
            if settings.smtp_port!=465:smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password)
            if smtp.send_message(message):raise ProviderFailure('email_recipient_rejected')
        return str(message['Message-ID'])
    except ProviderFailure:raise
    except (smtplib.SMTPAuthenticationError,smtplib.SMTPRecipientsRefused):raise ProviderFailure('email_configuration_error')
    except Exception:raise ProviderFailure('email_provider_unavailable',retryable=True)

def send_whatsapp(*args,**kwargs):raise ProviderFailure('whatsapp_not_supported')
