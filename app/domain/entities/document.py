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
    raw: str
    source_type: str
    lang: str = "en"


class DocumentStatus(Enum):
    PENDING    = "pending"
    EXTRACTING = "extracting"
    GENERATING = "generating"
    DONE       = "done"
    FAILED     = "failed"


@dataclass
class Document:
    id: UUID
    user_id: UUID
    title: str
    document_type: DocumentType
    raw_sources: list[Source]
    presentation: PresentationInfo
    status: DocumentStatus
    sections: list[APASection]
    sources: list[SourceReference]
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    additional_notes: str | None = None

    @classmethod
    def create(
        cls,
        user_id: UUID,
        title: str,
        document_type: DocumentType,
        raw_sources: list[Source],
        presentation: PresentationInfo,
        additional_notes: str | None = None,
    ) -> Document:
        if not raw_sources:
            raise DocumentBuildError("A document needs at least one source.")

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            user_id=user_id,
            title=title,
            document_type=document_type,
            raw_sources=raw_sources,
            presentation=presentation,
            status=DocumentStatus.PENDING,
            sections=[],
            sources=[],
            created_at=now,
            updated_at=now,
            additional_notes=additional_notes,
        )

    def start_extraction(self) -> None:
        self._assert_status(DocumentStatus.PENDING)
        self.status = DocumentStatus.EXTRACTING
        self._touch()

    def start_generation(self) -> None:
        self._assert_status(DocumentStatus.EXTRACTING)
        self.status = DocumentStatus.GENERATING
        self._touch()

    def complete(
        self, title: str, sections: list[APASection], sources: list[SourceReference]
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

        self.title = title
        self.sections = sorted(sections, key=lambda s: s.section_type.order)
        self.sources = sources
        self.status = DocumentStatus.DONE
        self._touch()

    def update_content(
        self,
        title: str | None = None,
        sections: list[APASection] | None = None,
        presentation: PresentationInfo | None = None,
    ) -> None:
        if title is not None:
            self.title = title
        if sections is not None:
            self.sections = sorted(sections, key=lambda s: s.section_type.order)
        if presentation is not None:
            self.presentation = presentation
        self._touch()

    def fail(self, reason: str) -> None:
        self.status = DocumentStatus.FAILED
        self.error_message = reason
        self._touch()

    def is_ready(self) -> bool:
        return self.status == DocumentStatus.DONE

    def get_section(self, section_type: APASectionType) -> APASection | None:
        return next((s for s in self.sections if s.section_type == section_type), None)

    def _assert_status(self, expected: DocumentStatus) -> None:
        if self.status != expected:
            raise DocumentBuildError(
                f"Invalid operation: document is '{self.status.value}', expected '{expected.value}'."
            )

    def _touch(self) -> None:
        self.updated_at = datetime.utcnow()
