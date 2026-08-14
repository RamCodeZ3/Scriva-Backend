from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from domain.entities.document import DocumentStatus
from domain.value_objects.apa_structure import APASection
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference


@dataclass(frozen=True)
class CreateDocumentInput:
    user_id: UUID
    title: str
    document_type: DocumentType
    presentation: PresentationInfo
    sources: list[str]
    additional_notes: str | None = None


@dataclass(frozen=True)
class CreateDocumentOutput:
    document_id: UUID
    status: DocumentStatus
    document_type: DocumentType
    document_title: str
    sections: list[APASection]
    error_message: str | None = None


@dataclass(frozen=True)
class DocumentStatusOutput:
    document_id: UUID
    status: DocumentStatus
    error_message: str | None = None


@dataclass(frozen=True)
class DocumentDetailOutput:
    document_id: UUID
    title: str
    status: DocumentStatus
    export_url: str | None
    sections: list[APASection]
    sources: list[SourceReference]
