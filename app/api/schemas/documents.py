from typing import Literal

from pydantic import BaseModel, Field


class CreateDocumentRequest(BaseModel):
    """
    Body of POST /api/v1/documents/.

    `user` here is the student's display name for the document's cover
    page — the *account* is already identified by the Bearer token, not
    by this field.
    """

    user: str = Field(..., min_length=1, description="Student name shown on the cover page.")
    document_type: str = Field(..., description="'summary' | 'synthesis' | 'report' | 'brief'")
    source_type: str = Field(..., description="'web' | 'youtube' | 'file' | 'text'")
    source: str = Field(..., min_length=1, description="URL, file path, or plain text.")
    professor: str = Field(..., min_length=1)
    student_id: str = Field(..., min_length=1)
    institution: str = Field(..., min_length=1)
    export_target: Literal["google", "pdf"] = Field(
        "pdf",
        description=(
            "'google' creates the document in the caller's linked Google "
            "Drive and returns its share link in `document_url`. 'pdf' "
            "(default) renders the document as a PDF with ReportLab, "
            "keeps a copy server-side, and returns the file inline as "
            "base64 — no Google account required."
        ),
    )


class CreateDocumentResponse(BaseModel):
    status: str
    document_type: str
    document_url: str | None = None       # populated for export_target="google"
    file_base64: str | None = None        # populated for export_target="pdf"
    file_name: str | None = None
    content_type: str | None = None
    error_message: str | None = None      # populated when status == "failed"
