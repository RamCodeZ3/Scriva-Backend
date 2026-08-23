from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    user: str = Field(..., min_length=1)
    document_type: str
    sources: list[str] = Field(..., min_length=1)
    professor: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    institution: str = Field(..., min_length=1)
    subject: str | None = None
    additional_notes: str | None = None


class MarkOut(BaseModel):
    """Mirrors domain.value_objects.document_node.Mark."""

    type: str
    value: Any | None = None


class DocumentNodeOut(BaseModel):
    id: str | None = None
    type: str | None = None
    section_type: str | None = None
    text: str | None = None
    marks: list[MarkOut] | None = None
    children: list["DocumentNodeOut"] | None = None
    styles: dict[str, Any] | None = None
    src: str | None = None
    alt: str | None = None
    caption: str | None = None


DocumentNodeOut.model_rebuild()


class DocumentMetaOut(BaseModel):
    title: str
    style_guide: str = "APA7"


class DocumentStylesOut(BaseModel):
    fontFamily: str = "Times New Roman, serif"
    fontSize: str = "12pt"
    color: str = "#000000"
    backgroundColor: str = "#ffffff"
    pageMargin: Any = "1in"
    pageSize: Any = "letter"
    orientation: str = "portrait"
    lineHeight: float = 2.0


class DocumentResponse(BaseModel):
    id: str
    title: str
    document_type: str
    status: str
    meta: DocumentMetaOut
    document_styles: DocumentStylesOut
    document_nodes: list[DocumentNodeOut]
    user_id: str
    presentation: PresentationOut
    error_message: str | None = None
    source_ids: list[str]
    created_at: str
    updated_at: str


class PresentationOut(BaseModel):
    student_name: str
    professor: str
    subject: str | None = None
    student_id: str | None = None
    institution: str | None = None


class UpdateDocumentRequest(BaseModel):
    title: str | None = None
    document_nodes: list[DocumentNodeOut] | None = None
    presentation: PresentationOut | None = None
    document_styles: DocumentStylesOut | None = None


class DocumentPatchResponse(BaseModel):
    id: str
    title: str
    document_type: str
    document_nodes: list[DocumentNodeOut]
    user_id: str
    presentation: PresentationOut
    error_message: str | None = None
    source_ids: list[str]
    updated_at: str


class DeleteDocumentResponse(BaseModel):
    status: str
    document_id: str


class AugmentDocumentRequest(BaseModel):
    sources: list[str] = Field(..., min_length=1)
    additional_notes: str | None = None


class ExportDocumentRequest(BaseModel):
    document_id: str
    export: str


class ExportDocumentResponse(BaseModel):
    status: str
    document_id: str
    export: str
    url: str | None = None
    file_base64: str | None = None
    file_name: str | None = None
    content_type: str | None = None


class DocumentReferenceResponse(BaseModel):
    id: str
    title: str
    updated_at: str
