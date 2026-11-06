from app.models.user import User, UserPreference, RefreshSession, PasswordResetToken
from app.models.account_erasure import AccountErasure
from app.models.activity import Activity
from app.models.image_upload import ImageUpload
from app.models.client import Client, ClientNote, ClientInteraction
from app.models.court import Court, AdvocateCourtFavorite
from app.models.case import Case, CaseParty, CaseAdvocate, CaseStatusHistory, CaseActivity
from app.models.hearing import Hearing, HearingReminder
from app.models.diary import CaseDiaryEntry
from app.models.document import Document, DocumentVersion, DocumentOCR, DocumentAccessLog
from app.models.planning import Task, Appointment, PlanningReminder
from app.models.phase10 import DraftTemplate, DraftDocument, DraftVersion, DraftClause, FeeAgreement, Payment, Expense, ResearchItem
from app.models.finance import FinancialAdjustment, Invoice, Receipt, AgreementHistory
from app.models.drafting import DraftExport, DraftAudit
from app.models.research import ResearchTag, ResearchItemTag, ResearchNote, ResearchNoteTag, ResearchCaseLink, ResearchSourceMetadata, ResearchAudit, ResearchImportBatch
from app.models.notifications import Notification, UserDevice, NotificationDelivery, NotificationDeliveryAttempt, NotificationEvent
from app.models.ai import AIPreference, AIConversation, AIJob, AIChunk
from app.models.sync import SyncChange, SyncDevice, SyncOperation
