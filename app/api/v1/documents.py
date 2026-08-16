from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from domain.entities.user import User
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo

from application.dtos.document_dtos import CreateDocumentInput, UpdateDocumentInput
from application.use_cases.create_document_use_case import CreateDocumentUseCase
from application.use_cases.delete_document_use_case import DeleteDocumentUseCase
from application.use_cases.get_document_use_case import GetDocumentUseCase
from application.use_cases.update_document_use_case import UpdateDocumentUseCase

from api.deps import (
    get_create_document_use_case,
    get_current_user,
    get_delete_document_use_case,
    get_get_document_use_case,
    get_update_document_use_case,
)
from api.schemas.documents import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DeleteDocumentResponse,
    DocumentGetResponse,
    DocumentPatchResponse,
    DocumentSectionOut,
    PresentationOut,
    UpdateDocumentRequest,
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
        document_sections=_sections_out(result.sections),
        error_message=result.error_message,
    )


@router.get("/{document_id}", response_model=DocumentGetResponse)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    use_case: GetDocumentUseCase = Depends(get_get_document_use_case),
) -> DocumentGetResponse:
    result = await use_case.execute(document_id, current_user.id)

    return DocumentGetResponse(
        id=str(result.id),
        title=result.title,
        document_type=result.document_type.value,
        status=result.status.value,
        sections=_sections_out(result.sections),
        user_id=str(result.user_id),
        presentation=_presentation_out(result.presentation),
        error_message=result.error_message,
        source_ids=[str(sid) for sid in result.source_ids],
        created_at=result.created_at.isoformat(),
        updated_at=result.updated_at.isoformat(),
    )


@router.patch("/{document_id}", response_model=DocumentPatchResponse)
async def update_document(
    document_id: UUID,
    body: UpdateDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: UpdateDocumentUseCase = Depends(get_update_document_use_case),
) -> DocumentPatchResponse:
    sections = None
    if body.sections is not None:
        try:
            sections = [
                APASection(
                    section_type=APASectionType(s.section_type), title=s.title, content=s.content
                )
                for s in body.sections
            ]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid section_type in sections: {exc}",
            ) from exc

    presentation = None
    if body.presentation is not None:
        presentation = PresentationInfo(
            student_name=body.presentation.student_name,
            professor=body.presentation.professor,
            subject=body.presentation.subject,
            student_id=body.presentation.student_id,
            institution=body.presentation.institution,
        )

    data = UpdateDocumentInput(
        document_id=document_id,
        user_id=current_user.id,
        title=body.title,
        sections=sections,
        presentation=presentation,
    )
    result = await use_case.execute(data)

    return DocumentPatchResponse(
        id=str(result.id),
        title=result.title,
        document_type=result.document_type.value,
        sections=_sections_out(result.sections),
        user_id=str(result.user_id),
        presentation=_presentation_out(result.presentation),
        error_message=result.error_message,
        source_ids=[str(sid) for sid in result.source_ids],
        updated_at=result.updated_at.isoformat(),
    )


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    use_case: DeleteDocumentUseCase = Depends(get_delete_document_use_case),
) -> DeleteDocumentResponse:
    await use_case.execute(document_id, current_user.id)
    return DeleteDocumentResponse(status="deleted", document_id=str(document_id))


def _title_snippet(body: CreateDocumentRequest) -> str:
    if body.subject:
        return body.subject[:80]
    first = next((s.strip() for s in body.sources if s.strip()), "documento")
    return first.splitlines()[0][:80]


def _sections_out(sections) -> list[DocumentSectionOut]:
    return [
        DocumentSectionOut(section_type=s.section_type.value, title=s.title, content=s.content)
        for s in sections
    ]


def _presentation_out(p: PresentationInfo) -> PresentationOut:
    return PresentationOut(
        student_name=p.student_name,
        professor=p.professor,
        subject=p.subject,
        student_id=p.student_id,
        institution=p.institution,
    )
