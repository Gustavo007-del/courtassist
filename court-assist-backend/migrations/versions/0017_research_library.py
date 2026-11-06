"""Extend the private research records, retaining existing text and citations."""

import uuid
from alembic import op
import sqlalchemy as sa
from app.models.research import (
    ResearchTag,
    ResearchItemTag,
    ResearchNote,
    ResearchNoteTag,
    ResearchCaseLink,
    ResearchSourceMetadata,
    ResearchAudit,
    ResearchImportBatch,
)
from app.services.research_search import SEARCH_SQL

revision = "0017_research_library"
down_revision = "0016_finance_metadata"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {row["name"] for row in sa.inspect(bind).get_columns("research_items")}
    additions = []
    for name, length in [
        ("case_number", 120),
        ("cnr_number", 32),
        ("case_title", 240),
        ("source_name", 240),
        ("language", 10),
        ("act_name", 240),
        ("section_number", 240),
        ("verification_status", 30),
        ("page_reference", 240),
        ("paragraph_reference", 240),
    ]:
        additions.append(
            sa.Column(
                name,
                sa.String(length),
                nullable=False,
                server_default="en"
                if name == "language"
                else "unverified"
                if name == "verification_status"
                else "",
            )
        )
    additions.extend(
        sa.Column(name, sa.Text, nullable=False, server_default="")
        for name in ("full_text", "party_information", "verification_notes")
    )
    additions.extend(
        sa.Column(name, sa.Date) for name in ("judgment_date", "accessed_date")
    )
    additions.extend(
        [
            sa.Column(
                "favorite", sa.Boolean, nullable=False, server_default=sa.false()
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
        ]
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("research_items", column)
    for name, target in [("client_id", "clients"), ("document_id", "documents")]:
        if name not in columns:
            if bind.dialect.name == "sqlite":
                op.execute(
                    sa.text(
                        f"ALTER TABLE research_items ADD COLUMN {name} CHAR(32) REFERENCES {target}(id)"
                    )
                )
            else:
                op.add_column(
                    "research_items",
                    sa.Column(
                        name,
                        sa.Uuid,
                        sa.ForeignKey(
                            target + ".id",
                            name="fk_research_"
                            + ("client" if name == "client_id" else "document"),
                        ),
                    ),
                )
    bind.execute(
        sa.text(
            "UPDATE research_items SET updated_at=created_at WHERE updated_at IS NULL"
        )
    )
    if bind.dialect.name == "postgresql":
        op.alter_column("research_items", "updated_at", nullable=False)
    for model in (
        ResearchTag,
        ResearchItemTag,
        ResearchNote,
        ResearchNoteTag,
        ResearchCaseLink,
        ResearchSourceMetadata,
        ResearchAudit,
        ResearchImportBatch,
    ):
        model.__table__.create(bind, checkfirst=True)
    meta = sa.MetaData()
    items = sa.Table("research_items", meta, autoload_with=bind)
    tags = ResearchTag.__table__
    links = ResearchItemTag.__table__
    existing = {
        (str(row.user_id), row.normalized_name): row.id
        for row in bind.execute(sa.select(tags)).all()
    }
    cases = sa.Table("cases", meta, autoload_with=bind)
    for row in bind.execute(
        sa.select(items.c.id, items.c.user_id, items.c.tags, items.c.case_id)
    ).all():
        if (
            row.case_id
            and bind.execute(
                sa.select(cases.c.id).where(
                    cases.c.id == row.case_id, cases.c.user_id == row.user_id
                )
            ).first()
        ):
            case_links = ResearchCaseLink.__table__
            if not bind.execute(
                sa.select(case_links.c.item_id).where(
                    case_links.c.item_id == uuid.UUID(str(row.id)),
                    case_links.c.case_id == uuid.UUID(str(row.case_id)),
                )
            ).first():
                bind.execute(
                    case_links.insert().values(
                        item_id=uuid.UUID(str(row.id)),
                        case_id=uuid.UUID(str(row.case_id)),
                    )
                )
        seen = set()
        for value in row.tags if isinstance(row.tags, list) else []:
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value.strip()) > 80
            ):
                continue
            name = value.strip()
            key = (str(uuid.UUID(str(row.user_id))), name.casefold())
            if key in seen:
                continue
            seen.add(key)
            if key not in existing:
                identifier = uuid.uuid4()
                existing[key] = identifier
                bind.execute(
                    tags.insert().values(
                        id=identifier,
                        user_id=uuid.UUID(str(row.user_id)),
                        name=name,
                        normalized_name=name.casefold(),
                    )
                )
            identifier = existing[key]
            if not bind.execute(
                sa.select(links.c.item_id).where(
                    links.c.item_id == uuid.UUID(str(row.id)),
                    links.c.tag_id == identifier,
                )
            ).first():
                bind.execute(
                    links.insert().values(
                        item_id=uuid.UUID(str(row.id)), tag_id=identifier
                    )
                )
    for name, fields in [
        ("ix_research_owner_updated", ["user_id", "updated_at"]),
        ("ix_research_owner_case", ["user_id", "case_id"]),
        ("ix_research_owner_court_date", ["user_id", "court", "judgment_date"]),
        ("ix_research_notes_owner_pinned", ["user_id", "pinned", "updated_at"]),
        ("ix_research_notes_owner_case", ["user_id", "case_id"]),
    ]:
        table = "research_notes" if "notes_" in name else "research_items"
        if name not in {index["name"] for index in sa.inspect(bind).get_indexes(table)}:
            op.create_index(name, table, fields)
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_research_fulltext ON research_items USING gin(to_tsvector('simple', "
                + SEARCH_SQL
                + "))"
            )
        )
    for row in bind.execute(
        sa.select(items.c.id, items.c.user_id).where(
            items.c.source_status == "verified_external"
        )
    ).all():
        bind.execute(
            ResearchAudit.__table__.insert().values(
                id=uuid.uuid4(),
                user_id=uuid.UUID(str(row.user_id)),
                item_id=uuid.UUID(str(row.id)),
                action="legacy_verification_review",
                details={
                    "previous_source_status": "verified_external",
                    "reason": "No verified external integration is available",
                },
            )
        )
        bind.execute(
            items.update()
            .where(items.c.id == row.id)
            .values(source_status="unverified")
        )
    # Normalize the vault state used by earlier generated files; keys/content remain unchanged.
    bind.execute(
        sa.text(
            "UPDATE documents SET storage_status='cloud_stored' WHERE storage_status='stored'"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE document_versions SET storage_status='cloud_stored' WHERE storage_status='stored'"
        )
    )


def downgrade():
    # Preserve privately entered sources and notes. Rollback requires an explicit retention decision.
    pass
