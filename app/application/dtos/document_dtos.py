from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from domain.entities.document import DocumentStatus
from domain.value_objects.apa_structure import APASection
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference

from application.dtos.export_result import ExportResult


@dataclass(frozen=True)
class CreateDocumentInput:
    """
    Input DTO for the request coming from the web layer:
    the source/media to process plus the user info needed for the
    presentation (cover) page.
    """
    user_id: UUID
    title: str
    document_type: DocumentType
    presentation: PresentationInfo
    source_raw: str          # URL, path, or plain text
    source_type: str         # "web" | "youtube" | "file" | "text"
    source_lang: str = "en"
    export_target: str = "pdf"   # "google" | "pdf"


@dataclass(frozen=True)
class CreateDocumentOutput:
    """
    Returned once the (currently synchronous) pipeline finishes.
    `export_result` is None only if the pipeline failed before
    reaching the export step — check `status` / `error_message` then.
    """
    document_id: UUID
    status: DocumentStatus
    document_type: DocumentType
    export_result: ExportResult | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class DocumentStatusOutput:
    """Lightweight DTO used for polling the processing state."""
    document_id: UUID
    status: DocumentStatus
    error_message: str | None = None


@dataclass(frozen=True)
class DocumentDetailOutput:
    """Full document once it's DONE, including the exported file link."""
    document_id: UUID
    title: str
    status: DocumentStatus
    export_url: str | None
    sections: list[APASection]
    sources: list[SourceReference]
