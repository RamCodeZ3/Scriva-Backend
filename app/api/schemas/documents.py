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
