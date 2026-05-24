from dataclasses import dataclass, field
from uuid import UUID, uuid4
from enum import Enum

from domain.exceptions import InvalidSourceError


class SourceType(Enum):
    WEB      = "web"
    YOUTUBE  = "youtube"
    FILE     = "file"
    TEXT     = "text"


class SourceStatus(Enum):
    PENDING   = "pending"    # not yet extracted
    EXTRACTED = "extracted"  # text content is ready
    FAILED    = "failed"     # extraction failed


@dataclass
class Source:
    """
    Entity that represents an information source after extraction.
    Holds the raw input AND the extracted plain text content
    that will be sent to the AI.
    """
    id: UUID
    source_type: SourceType
    raw: str                        # original input: URL, path, plain text
    status: SourceStatus
    content: str | None = None      # extracted plain text (ready for AI)
    char_count: int | None = None   # useful for prompt size control
    error_message: str | None = None

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def create(cls, raw: str, source_type: SourceType) -> Source:
        """Creates a Source in PENDING status, before extraction."""
        return cls(
            id=uuid4(),
            source_type=source_type,
            raw=raw,
            status=SourceStatus.PENDING,
        )

    # ── State transitions ─────────────────────────────────────────────────────

    def mark_extracted(self, content: str) -> None:
        """Called by the extractor adapter once text is ready."""
        if not content.strip():
            raise InvalidSourceError("Extracted content cannot be empty.")
        self.content  = content
        self.char_count = len(content)
        self.status   = SourceStatus.EXTRACTED

    def mark_failed(self, reason: str) -> None:
        self.status = SourceStatus.FAILED
        self.error_message = reason

    # ── Queries ───────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        return self.status == SourceStatus.EXTRACTED

    def get_content(self) -> str:
        """Safe getter — raises if content is not ready yet."""
        if not self.is_ready() or self.content is None:
            raise InvalidSourceError(
                f"Source is not ready for use. "
                f"Current status: '{self.status.value}'."
            )
        return self.content
