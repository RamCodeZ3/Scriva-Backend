from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.entities.source import Source, SourceType


@dataclass(frozen=True)
class SourceOutput:
    id: UUID
    source_type: SourceType
    raw: str
    char_count: int
    created_at: datetime

    @classmethod
    def from_source(cls, source: Source) -> "SourceOutput":
        if source.created_at is None:
            raise ValueError(f"Source '{source.id}' has no creation date.")
        return cls(
            id=source.id,
            source_type=source.source_type,
            raw=source.raw,
            char_count=source.char_count or 0,
            created_at=source.created_at,
        )


@dataclass(frozen=True)
class SourceDetailOutput(SourceOutput):
    content: str

    @classmethod
    def from_source(cls, source: Source) -> "SourceDetailOutput":
        if source.created_at is None:
            raise ValueError(f"Source '{source.id}' has no creation date.")
        return cls(
            id=source.id,
            source_type=source.source_type,
            raw=source.raw,
            content=source.content or "",
            char_count=source.char_count or 0,
            created_at=source.created_at,
        )
