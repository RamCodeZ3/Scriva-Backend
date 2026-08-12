from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    user: str = Field(..., min_length=1)
    document_type: str
    export_target: str = "pdf"
    sources: list[str] = Field(..., min_length=1)
    professor: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    institution: str = Field(..., min_length=1)
    subject: str | None = None


class CreateDocumentResponse(BaseModel):
    status: str
    document_type: str
    document_url: str | None = None
    file_base64: str | None = None
    file_name: str | None = None
    content_type: str | None = None
    error_message: str | None = None
