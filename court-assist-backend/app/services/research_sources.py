"""Boundary for future, explicitly permitted sources. No public integration is registered."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SourceEnvelope:
    provider_id: str
    source_url: str
    retrieved_at: datetime
    metadata: dict
    evidence_references: tuple[str, ...]


class PermittedSourceProvider(Protocol):
    provider_id: str
    permission_documentation_url: str

    def retrieve_metadata(self, source_url: str) -> SourceEnvelope: ...


# Registration requires verified access rights and an implemented, reviewed adapter.
# User URLs are stored as references and are never passed to a provider here.
REGISTERED_PROVIDERS: tuple[PermittedSourceProvider, ...] = ()
