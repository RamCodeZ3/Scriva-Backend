from __future__ import annotations

import base64
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from domain.entities.user import User
from domain.value_objects.apa_structure import (
    APA7_DOCUMENT_STYLES,
    APASection,
    APASectionType,
)
from domain.value_objects.document_node import HEADING_1, IMAGE, DocumentNode, Mark
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo

from application.dtos.document_dtos import (
    AugmentDocumentInput,
    CreateDocumentInput,
    ExportDocumentInput,
    UpdateDocumentInput,
)
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
from application.use_cases.update_document_use_case import (
    UpdateDocumentUseCase,
)
from application.use_cases.list_user_documents_use_case import (
    ListUserDocumentsUseCase,
)
from application.exceptions import UserNotFoundError

from api.deps import (
    get_augment_document_use_case,
    get_create_document_use_case,
    get_current_user,
    get_delete_document_use_case,
    get_export_document_use_case,
    get_get_document_use_case,
    get_update_document_use_case,
    get_list_user_documents_use_case,
)
from api.schemas.documents import (
    AugmentDocumentRequest,
    CreateDocumentRequest,
    DocumentResponse,
    DeleteDocumentResponse,
    DocumentMetaOut,
    DocumentNodeOut,
    DocumentPatchResponse,
    DocumentStylesOut,
    ExportDocumentRequest,
    ExportDocumentResponse,
    MarkOut,
    PresentationOut,
    UpdateDocumentRequest,
    DocumentReferenceResponse,
)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/", response_model=DocumentResponse)
async def create_document(
    body: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: CreateDocumentUseCase = Depends(get_create_document_use_case),
) -> DocumentResponse:
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

    return DocumentResponse(
        id=str(result.id),
        title=result.title,
        document_type=result.document_type.value,
        status=result.status.value,
        meta=DocumentMetaOut(title=result.title),
        document_styles=_styles_out(result),
        document_nodes=_nodes_out(result.sections),
        user_id=str(result.user_id),
        presentation=_presentation_out(result.presentation),
        error_message=result.error_message,
        source_ids=[str(sid) for sid in result.source_ids],
        created_at=result.created_at.isoformat(),
        updated_at=result.updated_at.isoformat()
    )


@router.post("/export/", response_model=ExportDocumentResponse)
async def export_document(
    body: ExportDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: ExportDocumentUseCase = Depends(get_export_document_use_case),
) -> ExportDocumentResponse:
    try:
        document_id = UUID(body.document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_id '{body.document_id}': {exc}",
        ) from exc

    data = ExportDocumentInput(
        document_id=document_id, user_id=current_user.id, export=body.export
    )
    result = await use_case.execute(data)

    return ExportDocumentResponse(
        status="exported",
        document_id=body.document_id,
        export=body.export,
        url=result.url,
        file_base64=(
            base64.b64encode(result.file_bytes).decode("ascii")
            if result.file_bytes
            else None
        ),
        file_name=result.file_name,
        content_type=result.content_type,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    use_case: GetDocumentUseCase = Depends(get_get_document_use_case),
) -> DocumentResponse:
    result = await use_case.execute(document_id, current_user.id)

    return DocumentResponse(
        id=str(result.id),
        title=result.title,
        document_type=result.document_type.value,
        status=result.status.value,
        meta=DocumentMetaOut(title=result.title),
        document_styles=_styles_out(result),
        document_nodes=_nodes_out(result.sections),
        user_id=str(result.user_id),
        presentation=_presentation_out(result.presentation),
        error_message=result.error_message,
        source_ids=[str(sid) for sid in result.source_ids],
        created_at=result.created_at.isoformat(),
        updated_at=result.updated_at.isoformat(),
    )


@router.patch("/ia/{document_id}", response_model=DocumentResponse)
async def augment_document(
    document_id: UUID,
    body: AugmentDocumentRequest,
    current_user: User = Depends(get_current_user),
    use_case: AugmentDocumentUseCase = Depends(get_augment_document_use_case),
) -> DocumentGetResponse:
    data = AugmentDocumentInput(
        document_id=document_id,
        user_id=current_user.id,
        sources=body.sources,
        additional_notes=body.additional_notes,
    )
    result = await use_case.execute(data)

    return DocumentResponse(
        id=str(result.id),
        title=result.title,
        document_type=result.document_type.value,
        status=result.status.value,
        meta=DocumentMetaOut(title=result.title),
        document_styles=_styles_out(result),
        document_nodes=_nodes_out(result.sections),
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
    if body.document_nodes is not None:
        try:
            sections = _sections_from_nodes(body.document_nodes)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid document_nodes: {exc}",
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
        document_nodes=_nodes_out(result.sections),
        user_id=str(result.user_id),
        presentation=_presentation_out(result.presentation),
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


def _styles_out(result) -> DocumentStylesOut:
    # `result` is whatever DTO the use case returns; if it doesn't carry
    # `document_styles` yet, fall back to the fixed APA7 defaults.
    styles = {**APA7_DOCUMENT_STYLES, **(getattr(result, "document_styles", None) or {})}
    return DocumentStylesOut(**styles)


def _presentation_out(p: PresentationInfo) -> PresentationOut:
    return PresentationOut(
        student_name=p.student_name,
        professor=p.professor,
        subject=p.subject,
        student_id=p.student_id,
        institution=p.institution,
    )


def _node_out(node: DocumentNode) -> DocumentNodeOut:
    if node.text is not None:
        marks = [MarkOut(type=m.type, value=m.value) for m in node.marks]
        return DocumentNodeOut(text=node.text, marks=marks or None)

    if node.type == IMAGE:
        return DocumentNodeOut(
            id=node.id,
            type=node.type,
            section_type=node.section_type,
            styles=dict(node.styles) if node.styles else None,
            src=node.src,
            alt=node.alt,
            caption=node.caption,
        )

    return DocumentNodeOut(
        id=node.id,
        type=node.type,
        section_type=node.section_type,
        styles=dict(node.styles) if node.styles else None,
        children=[_node_out(c) for c in node.children],
    )


def _nodes_out(sections: list[APASection]) -> list[DocumentNodeOut]:
    flat: list[DocumentNode] = []
    for section in sections:
        flat.append(section.heading)
        flat.extend(section.body_nodes)
    return [_node_out(n) for n in flat]


def _node_from_out(node: DocumentNodeOut) -> DocumentNode:
    if node.text is not None:
        marks = tuple(Mark(type=m.type, value=m.value) for m in (node.marks or ()))
        return DocumentNode(text=node.text, marks=marks)

    if node.type == IMAGE:
        return DocumentNode(
            type=node.type,
            id=node.id,
            section_type=node.section_type,
            styles=dict(node.styles or {}),
            src=node.src,
            alt=node.alt,
            caption=node.caption,
        )

    return DocumentNode(
        type=node.type,
        id=node.id,
        section_type=node.section_type,
        styles=dict(node.styles or {}),
        children=tuple(_node_from_out(c) for c in (node.children or ())),
    )


def _sections_from_nodes(nodes: list[DocumentNodeOut]) -> list[APASection]:
    heading: DocumentNode | None = None
    section_type: APASectionType | None = None
    body: list[DocumentNode] = []
    sections: list[APASection] = []

    def _flush() -> None:
        if heading is not None:
            sections.append(
                APASection(
                    section_type=section_type,
                    heading=heading,
                    body_nodes=tuple(body),
                )
            )

    for out_node in nodes:
        node = _node_from_out(out_node)
        if node.type == HEADING_1:
            _flush()
            heading = node
            body = []
            if node.section_type is None:
                raise ValueError(
                    "A 'heading-1' node is missing its 'section_type'."
                )
            try:
                section_type = APASectionType(node.section_type)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown section_type: {node.section_type!r}"
                ) from exc
        else:
            if heading is None:
                raise ValueError(
                    "document_nodes must start with a 'heading-1' node."
                )
            body.append(node)

    _flush()
    return sections
