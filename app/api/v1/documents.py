from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status

from domain.entities.user import User
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo

from application.dtos.document_dtos import CreateDocumentInput
from application.use_cases.create_document_use_case import CreateDocumentUseCase

from api.deps import get_create_document_use_case, get_current_user
from api.schemas.documents import CreateDocumentRequest, CreateDocumentResponse

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/", response_model=CreateDocumentResponse)
async def create_document(
    body: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateDocumentUseCase = Depends(get_create_document_use_case),
) -> CreateDocumentResponse:
    """
    Creates a document from a source and runs the full pipeline
    (extraction -> Gemini draft -> export) before answering, since
    there's a single endpoint and no polling for now. Expect this call
    to take as long as the slowest step (usually the AI draft, a heavy
    web page, or the Google Docs export).

    `export_target` picks the destination:
      - "pdf" (default): no external account needed. The account is
        still identified the same way as every other call on this
        service — the Supabase-signed Bearer token resolved by
        `get_current_user` — there's no separate "Google-shaped"
        identity for this path.
      - "google": requires this account to already have linked Google
        Docs/Drive (via the other backend's OAuth consent flow); the
        response carries `document_url` instead of the inline file.
    """
    try:
        document_type = DocumentType(body.document_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_type '{body.document_type}': {exc}",
        ) from exc

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
        document_type=document_type,
        presentation=presentation,
        source_raw=body.source,
        source_type=body.source_type,
        export_target=body.export_target,
    )

    result = await use_case.execute(data)
    export = result.export_result

    return CreateDocumentResponse(
        status=result.status.value,
        document_type=result.document_type.value,
        document_url=export.url if export else None,
        file_base64=(
            base64.b64encode(export.file_bytes).decode("ascii")
            if export and export.file_bytes
            else None
        ),
        file_name=export.file_name if export else None,
        content_type=export.content_type if export else None,
        error_message=result.error_message,
    )


def _infer_subject(body: CreateDocumentRequest) -> str:
    # `PresentationInfo.subject` is required but nothing in the request
    # specifies it — derive a provisional one from `source` until you
    # decide whether it should come from the AI draft or become an
    # explicit request field.
    first_line = body.source.strip().splitlines()[0] if body.source.strip() else "documento"
    return first_line[:80]
