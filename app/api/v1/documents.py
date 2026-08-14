from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from domain.entities.user import User
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo

from application.dtos.document_dtos import CreateDocumentInput
from application.use_cases.create_document_use_case import CreateDocumentUseCase

from api.deps import get_create_document_use_case, get_current_user
from api.schemas.documents import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DocumentSectionOut,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/", response_model=CreateDocumentResponse)
async def create_document(
    body: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateDocumentUseCase = Depends(get_create_document_use_case),
) -> CreateDocumentResponse:
    try:
        document_type = DocumentType(body.document_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_type '{body.document_type}': {exc}",
        ) from exc

    presentation = PresentationInfo(
        student_name=body.user,
        professor=body.professor,
        subject=body.subject,
        student_id=body.student_id,
        institution=body.institution,
    )

    data = CreateDocumentInput(
        user_id=current_user.id,
        title=_title_snippet(body),
        document_type=document_type,
        presentation=presentation,
        sources=body.sources,
        additional_notes=body.additional_notes,
    )

    result = await use_case.execute(data)

    return CreateDocumentResponse(
        status=result.status.value,
        document_id=str(result.document_id),
        document_type=result.document_type.value,
        document_title=result.document_title,
        document_sections=[
            DocumentSectionOut(section_type=s.section_type.value, title=s.title, content=s.content)
            for s in result.sections
        ],
        error_message=result.error_message,
    )


def _title_snippet(body: CreateDocumentRequest) -> str:
    if body.subject:
        return body.subject[:80]
    first = next((s.strip() for s in body.sources if s.strip()), "documento")
    return first.splitlines()[0][:80]
