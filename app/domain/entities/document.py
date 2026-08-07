from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

from domain.entities.source import Source
from domain.value_objects.document_type import DocumentType
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.source_ref import SourceReference
from domain.value_objects.presentation_info import PresentationInfo
from domain.exceptions import DocumentBuildError


@dataclass(frozen=True)
class SourceInput:
    """Represents the raw source before extraction."""
    raw: str                  # URL, plain text, or file path
    source_type: str          # "web" | "youtube" | "file" | "text"
    lang: str = "en"


class DocumentStatus(Enum):
    PENDING    = "pending"      # just created, no content yet
    EXTRACTING = "extracting"   # source is being extracted
    GENERATING = "generating"   # Gemini is drafting the document
    DONE       = "done"         # ready to export
    FAILED     = "failed"       # something went wrong


@dataclass
class Document:
    """
    Aggregate root.
    Represents the fully generated document.
    Pure business logic — no frameworks, no external dependencies.
    """
    id: UUID
    user_id: UUID
    title: str
    document_type: DocumentType
    source: Source
    presentation: PresentationInfo
    status: DocumentStatus
    sections: list[APASection]
    sources: list[SourceReference]
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None

    # ── Factory method ────────────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        user_id: UUID,
        title: str,
        document_type: DocumentType,
        source: Source,
        presentation: PresentationInfo
    ) -> Document:
        """Creates a new Document in PENDING status."""
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            user_id=user_id,
            title=title,
            document_type=document_type,
            source=source,
            presentation=presentation,
            status=DocumentStatus.PENDING,
            sections=[],
            sources=[],
            created_at=now,
            updated_at=now,
        )

    # ── State transitions ─────────────────────────────────────────────────────

    def start_extraction(self) -> None:
        self._assert_status(DocumentStatus.PENDING)
        self.status = DocumentStatus.EXTRACTING
        self._touch()

    def start_generation(self) -> None:
        self._assert_status(DocumentStatus.EXTRACTING)
        self.status = DocumentStatus.GENERATING
        self._touch()

    def complete(
        self,
        sections: list[APASection],
        sources: list[SourceReference],
    ) -> None:
        self._assert_status(DocumentStatus.GENERATING)

        if not sections:
            raise DocumentBuildError("A document must have at least one section.")

        required = {
            APASectionType.PRESENTATION,
            APASectionType.INDEX,
            APASectionType.INTRODUCTION,
            APASectionType.BODY,
            APASectionType.CONCLUSION,
            APASectionType.SOURCES,
        }
        missing = required - {s.section_type for s in sections}
        if missing:
            names = ", ".join(m.value for m in missing)
            raise DocumentBuildError(f"Missing required APA sections: {names}")

        self.sections = sorted(sections, key=lambda s: s.section_type.order)
        self.sources  = sources
        self.status   = DocumentStatus.DONE
        self._touch()

    def fail(self, reason: str) -> None:
        self.status = DocumentStatus.FAILED
        self.error_message = reason
        self._touch()

    # ── Queries ───────────────────────────────────────────────────────────────

    def is_ready(self) -> bool:
        return self.status == DocumentStatus.DONE

    def get_section(self, section_type: APASectionType) -> APASection | None:
        return next((s for s in self.sections if s.section_type == section_type), None)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _assert_status(self, expected: DocumentStatus) -> None:
        if self.status != expected:
            raise DocumentBuildError(
                f"Invalid operation: document is '{self.status.value}', "
                f"expected '{expected.value}'."
            )

    def _touch(self) -> None:
        self.updated_at = datetime.utcnow()
