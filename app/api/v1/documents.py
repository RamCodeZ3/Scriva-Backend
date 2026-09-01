from __future__ import annotations

import base64
import json
from io import BytesIO
from urllib.parse import quote
from uuid import UUID

from application.dtos.document_dtos import (
    AugmentDocumentInput,
    CreateDocumentInput,
    ExportDocumentInput,
    UpdateDocumentInput,
)
from application.exceptions import UserNotFoundError
from application.use_cases.augment_document_use_case import (
    AugmentDocumentUseCase,
)
from application.use_cases.create_document_use_case import (
    CreateDocumentUseCase,
)
from application.use_cases.delete_document_use_case import (
    DeleteDocumentUseCase,
)
from application.use_cases.export_document_use_case import (
    ExportDocumentUseCase,
)
from application.use_cases.get_document_use_case import GetDocumentUseCase
from application.use_cases.list_user_documents_use_case import (
    ListUserDocumentsUseCase,
)
from application.use_cases.update_document_use_case import (
    UpdateDocumentUseCase,
)
from domain.entities.user import User
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from api.deps import (
    get_augment_document_use_case,
    get_create_document_use_case,
    get_current_user,
    get_delete_document_use_case,
    get_export_document_use_case,
    get_get_document_use_case,
    get_list_user_documents_use_case,
    get_update_document_use_case,
)
from api.schemas.documents import (
    AugmentDocumentRequest,
    CreateDocumentRequest,
    DeleteDocumentResponse,
    DocumentMetadataResponse,
    DocumentPatchResponse,
    DocumentReferenceResponse,
    ExportDocumentResponse,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.post(
    "/",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Generated DOCX; metadata is in X-Document-Metadata."
            ),
            "content": {DOCX_MEDIA_TYPE: {}},
            "headers": {
                "X-Document-Metadata": {
                    "schema": {"type": "string"},
                    "description": "JSON matching DocumentMetadataResponse.",
                }
            },
        }
    },
)
async def create_document(
    body: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateDocumentUseCase = Depends(get_create_document_use_case),
) -> StreamingResponse:
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

    return _docx_response(result)


@router.post(
    "/{document_id}/export/{type_export}",
    response_model=ExportDocumentResponse,
)
async def export_document(
    document_id: UUID,
    type_export: str,
    current_user: User = Depends(get_current_user),
    use_case: ExportDocumentUseCase = Depends(get_export_document_use_case),
) -> ExportDocumentResponse:
    try:
        pass
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_id '{document_id}': {exc}",
        ) from exc

    data = ExportDocumentInput(
        document_id=document_id, user_id=current_user.id, export=type_export
    )
    result = await use_case.execute(data)

    return ExportDocumentResponse(
        status="exported",
        document_id=str(document_id),
        export=type_export,
        url=result.url,
        file_base64=(
            base64.b64encode(result.file_bytes).decode("ascii")
            if result.file_bytes
            else None
        ),
        file_name=result.file_name,
        content_type=result.content_type,
    )


@router.get(
    "/{document_id}",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {DOCX_MEDIA_TYPE: {}},
            "headers": {
                "X-Document-Metadata": {
                    "schema": {"type": "string"},
                    "description": "JSON matching DocumentMetadataResponse.",
                }
            },
        }
    },
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    use_case: GetDocumentUseCase = Depends(get_get_document_use_case),
) -> StreamingResponse:
    result = await use_case.execute(document_id, current_user.id)

    return _docx_response(result)


@router.patch(
    "/ai/{document_id}",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Updated DOCX; metadata is in X-Document-Metadata.",
            "content": {DOCX_MEDIA_TYPE: {}},
            "headers": {
                "X-Document-Metadata": {
                    "schema": {"type": "string"},
                    "description": "JSON matching DocumentMetadataResponse.",
                }
            },
        }
    },
)
async def augment_document(
    document_id: UUID,
    body: AugmentDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: AugmentDocumentUseCase = Depends(get_augment_document_use_case),
) -> StreamingResponse:
    data = AugmentDocumentInput(
        document_id=document_id,
        user_id=current_user.id,
        sources=body.sources,
        additional_notes=body.additional_notes,
    )
    result = await use_case.execute(data)

    return _docx_response(result)


@router.patch("/{document_id}", response_model=DocumentPatchResponse)
async def update_document(
    document_id: UUID,
    title: str | None = Form(default=None),
    document: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    use_case: UpdateDocumentUseCase = Depends(get_update_document_use_case),
) -> DocumentPatchResponse:
    if title is None and document is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least 'title' or a DOCX file.",
        )
    docx_bytes = None
    if document is not None:
        if not (document.filename or "").lower().endswith(".docx"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only .docx files are accepted.",
            )
        docx_bytes = await document.read()

    data = UpdateDocumentInput(
        document_id=document_id,
        user_id=current_user.id,
        title=title,
        docx_bytes=docx_bytes,
    )
    result = await use_case.execute(data)

    return DocumentPatchResponse(
        id=str(result.id),
        title=result.title,
        document_type=result.document_type.value,
        user_id=str(result.user_id),
        error_message=result.error_message,
        source_ids=[str(sid) for sid in result.source_ids],
        updated_at=result.updated_at.isoformat(),
    )


@router.get("/list/{user_id}", response_model=list[DocumentReferenceResponse])
async def get_list_by_user_id(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    use_case: ListUserDocumentsUseCase = Depends(
        get_list_user_documents_use_case
    ),
) -> list[DocumentReferenceResponse]:
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot access other users' documents.",
        )

    try:
        results = await use_case.execute(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [
        DocumentReferenceResponse(
            id=str(doc.id),
            title=doc.title,
            updated_at=doc.updated_at.isoformat(),
        )
        for doc in results
    ]


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    use_case: DeleteDocumentUseCase = Depends(get_delete_document_use_case),
) -> DeleteDocumentResponse:
    await use_case.execute(document_id, current_user.id)
    return DeleteDocumentResponse(
        status="deleted", document_id=str(document_id)
    )


def _title_snippet(body: CreateDocumentRequest) -> str:
    if body.subject:
        return body.subject[:80]
    first = next((s.strip() for s in body.sources if s.strip()), "documento")
    return first.splitlines()[0][:80]


def _metadata_out(result) -> DocumentMetadataResponse:
    document = result.document
    return DocumentMetadataResponse(
        id=str(document.id),
        title=document.title,
        document_type=document.document_type.value,
        status=document.status.value,
        user_id=str(document.user_id),
        error_message=document.error_message,
        source_ids=[str(source_id) for source_id in document.source_ids],
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    )


def _docx_response(result) -> StreamingResponse:
    metadata = _metadata_out(result)
    disposition = f"attachment; filename*=UTF-8''{quote(result.file_name)}"
    return StreamingResponse(
        BytesIO(result.file_bytes),
        media_type=result.content_type,
        headers={
            "Content-Disposition": disposition,
            "X-Document-Metadata": json.dumps(
                metadata.model_dump(mode="json"), ensure_ascii=True
            ),
            "Access-Control-Expose-Headers": (
                "Content-Disposition, X-Document-Metadata"
            ),
        },
    )
