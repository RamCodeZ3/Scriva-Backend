from __future__ import annotations

from fastapi import APIRouter, Depends

from domain.entities.user import User
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo

from application.dtos.document_dtos import CreateDocumentInput
from application.use_cases.create_document_use_case import CreateDocumentUseCase

from api.deps import get_create_document_use_case, get_current_user
from api.schemas.documents import CreateDocumentRequest, CreateDocumentResponse

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# The request body doesn't carry a document_type, so every document
# created through this endpoint uses the same default for now — add it
# as a request field later if you need the caller to choose between
# SUMMARY / SYNTHESIS / REPORT / BRIEF.
_DEFAULT_DOCUMENT_TYPE = DocumentType.REPORT


@router.post("/", response_model=CreateDocumentResponse)
async def create_document(
    body: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateDocumentUseCase = Depends(get_create_document_use_case),
) -> CreateDocumentResponse:
    """
    Creates a document from a source and runs the full pipeline
    (extraction -> Gemini draft -> Google Docs export) before
    answering, since there's a single endpoint and no polling for now.
    Expect this call to take as long as the slowest step (usually the
    AI draft or a heavy web page).
    """
    subject = _infer_subject(body)

    presentation = PresentationInfo(
        student_name=body.user,
        professor=body.professor,
        subject=subject,
        student_id=body.student_id,
        institution=body.institution,
    )

    data = CreateDocumentInput(
        user_id=current_user.id,
        title=f"Documento generado - {subject}",
        document_type=_DEFAULT_DOCUMENT_TYPE,
        presentation=presentation,
        source_raw=body.source,
        source_type=body.source_type,
    )

    result = await use_case.execute(data)

    return CreateDocumentResponse(
        status=result.status.value,
        document_url=result.export_url,
    )


def _infer_subject(body: CreateDocumentRequest) -> str:
    # `PresentationInfo.subject` is required but nothing in the request
    # specifies it — derive a provisional one from `source` until you
    # decide whether it should come from the AI draft or become an
    # explicit request field.
    first_line = body.source.strip().splitlines()[0] if body.source.strip() else "documento"
    return first_line[:80]
