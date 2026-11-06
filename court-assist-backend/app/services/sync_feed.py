"""Transactional change feed, shared by normal online writes and sync writes."""

from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import object_session
from sqlalchemy import event, func, insert, literal, select, text

from app.models.case import Case, CaseActivity, CaseAdvocate, CaseParty, CaseStatusHistory
from app.models.client import Client, ClientInteraction, ClientNote
from app.models.court import AdvocateCourtFavorite, Court
from app.models.diary import CaseDiaryEntry
from app.models.document import Document
from app.models.finance import Invoice, Receipt
from app.models.hearing import Hearing, HearingReminder
from app.models.phase10 import DraftDocument, Expense, FeeAgreement, Payment, ResearchItem
from app.models.planning import Appointment, PlanningReminder, Task
from app.models.research import ResearchNote
from app.models.sync import SyncChange


MODELS = {
    "case": Case, "timeline": CaseActivity, "party": CaseParty, "advocate": CaseAdvocate, "case_status": CaseStatusHistory,
    "client": Client, "client_note": ClientNote, "client_interaction": ClientInteraction, "court": Court,
    "hearing": Hearing, "hearing_reminder": HearingReminder, "diary": CaseDiaryEntry, "task": Task,
    "appointment": Appointment, "planning_reminder": PlanningReminder, "document": Document, "draft": DraftDocument,
    "research": ResearchItem, "research_note": ResearchNote, "agreement": FeeAgreement, "payment": Payment,
    "expense": Expense, "invoice": Invoice, "receipt": Receipt,
}
TRIGGERS = ", ".join(f"ca_sync_{model.__tablename__}" for model in MODELS.values())
PRIVATE_FIELDS = {"storage_key", "upload_expires_at", "idempotency_key", "request_id", "request_digest"}


def install_triggers(connection):
    if connection.dialect.name == "postgresql":
        connection.execute(text("""
            CREATE FUNCTION ca_capture_sync_change() RETURNS trigger LANGUAGE plpgsql AS $$
            DECLARE owner_id uuid; record_id uuid;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    owner_id := OLD.user_id; record_id := OLD.id;
                ELSE
                    IF TG_OP = 'UPDATE' AND to_jsonb(OLD) = to_jsonb(NEW) THEN RETURN NULL; END IF;
                    owner_id := NEW.user_id; record_id := NEW.id;
                END IF;
                IF owner_id IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE id = owner_id) THEN
                    PERFORM pg_advisory_xact_lock(hashtextextended('courtassist-sync-feed:' || owner_id::text, 0));
                    INSERT INTO sync_changes(user_id, kind, entity_id, deleted)
                        VALUES(owner_id, TG_ARGV[0], record_id, TG_OP = 'DELETE');
                END IF;
                RETURN NULL;
            END $$
        """))
        for kind, model in MODELS.items():
            table = model.__tablename__
            connection.execute(text(f"""
                CREATE CONSTRAINT TRIGGER ca_sync_{table} AFTER INSERT OR UPDATE OR DELETE ON {table}
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ca_capture_sync_change('{kind}')
            """))
    elif connection.dialect.name == "sqlite":
        for kind, model in MODELS.items():
            table = model.__tablename__
            for operation, row in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
                connection.execute(text(f"""
                    CREATE TRIGGER ca_sync_{table}_{operation.lower()} AFTER {operation} ON {table}
                    WHEN {row}.user_id IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE id = {row}.user_id)
                    BEGIN INSERT INTO sync_changes(user_id, kind, entity_id, deleted)
                        VALUES ({row}.user_id, '{kind}', {row}.id, {int(operation == 'DELETE')}); END
                """))


def bootstrap(connection):
    for kind, model in MODELS.items():
        connection.execute(insert(SyncChange).from_select(
            ["user_id", "kind", "entity_id", "deleted"],
            select(model.user_id, literal(kind), model.id, literal(False)).where(model.user_id.is_not(None)),
        ))


@event.listens_for(SyncChange.metadata, "after_create")
def create_sqlite_triggers(metadata, connection, **kwargs):
    # Disposable SQLite databases use the same event feed in API tests.
    if connection.dialect.name == "sqlite" and SyncChange.__table__ in kwargs.get("tables", []):
        install_triggers(connection)


def advisory_lock(db, key):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})


def flush_feed(db):
    db.flush()
    if db.bind.dialect.name == "postgresql":
        db.execute(text(f"SET CONSTRAINTS {TRIGGERS} IMMEDIATE"))


def version(db, owner, kind, identifier):
    return db.scalar(select(func.max(SyncChange.revision)).where(
        SyncChange.user_id == owner, SyncChange.kind == kind, SyncChange.entity_id == identifier,
    )) or 0


def record(db, owner, kind, identifier, lock=False):
    model = MODELS[kind]
    query = select(model).where(model.id == identifier, model.user_id == owner)
    return db.scalar(query.with_for_update() if lock else query)


def serialize(row, user):
    from app.models.phase10 import DraftDocument
    from app.services import case_service, court_service, diary_service, hearing_service, planning_service
    from app.services.draft_generation import safe_html

    if isinstance(row, Case):
        return jsonable_encoder(case_service.serialize(row))
    if isinstance(row, Hearing):
        return jsonable_encoder(hearing_service.serialize(row))
    if isinstance(row, CaseDiaryEntry):
        return diary_service.serialize(row).model_dump(mode="json")
    if isinstance(row, Task):
        return jsonable_encoder(planning_service.task_data(row, user))
    if isinstance(row, Court):
        favorite_ids = object_session(row).scalars(select(AdvocateCourtFavorite.court_id).where(
            AdvocateCourtFavorite.user_id == user.id, AdvocateCourtFavorite.court_id == row.id,
        )).all()
        return court_service.serialize(row, favorite_ids, user).model_dump(mode="json")
    values = {}
    for prop in row.__mapper__.column_attrs:
        if prop.key in PRIVATE_FIELDS:
            continue
        value = getattr(row, prop.key)
        if isinstance(value, Decimal):
            value = str(value)
        values[prop.key] = value
    if isinstance(row, DraftDocument):
        values["content"] = safe_html(row.content)
    return jsonable_encoder(values)


def snapshot(db, user, kind, identifier, revision=None):
    row = record(db, user.id, kind, identifier)
    return {
        "kind": kind, "id": str(identifier), "revision": str(revision if revision is not None else version(db, user.id, kind, identifier)),
        "deleted": row is None, "record": serialize(row, user) if row is not None else None,
    }

