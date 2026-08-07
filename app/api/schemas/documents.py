from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    """
    Body of POST /api/v1/documents/.

    `user` here is the student's display name for the document's cover
    page — the *account* is already identified by the Bearer token, not
    by this field.
    """

    user: str = Field(..., min_length=1, description="Student name shown on the cover page.")
    source_type: str = Field(..., description="'web' | 'youtube' | 'file' | 'text'")
    source: str = Field(..., min_length=1, description="URL, file path, or plain text.")
    professor: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    institution: str = Field(..., min_length=1)


class CreateDocumentResponse(BaseModel):
    status: str
    document_url: str | None = None
