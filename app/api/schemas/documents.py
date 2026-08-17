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


class DocumentSectionOut(BaseModel):
    section_type: str
    title: str
    content: str


class CreateDocumentResponse(BaseModel):
    status: str
    document_id: str
    document_type: str
    document_title: str
    document_sections: list[DocumentSectionOut]
    error_message: str | None = None


class PresentationOut(BaseModel):
    student_name: str
    professor: str
    subject: str | None = None
    student_id: str | None = None
    institution: str | None = None


class DocumentGetResponse(BaseModel):
    id: str
    title: str
    document_type: str
    status: str
    sections: list[DocumentSectionOut]
    user_id: str
    presentation: PresentationOut
    error_message: str | None = None
    source_ids: list[str]
    created_at: str
    updated_at: str


class UpdateDocumentRequest(BaseModel):
    title: str | None = None
    sections: list[DocumentSectionOut] | None = None
    presentation: PresentationOut | None = None


class DocumentPatchResponse(BaseModel):
    id: str
    title: str
    document_type: str
    sections: list[DocumentSectionOut]
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
