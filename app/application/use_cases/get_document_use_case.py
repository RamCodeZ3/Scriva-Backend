from uuid import UUID

from application.dtos.document_dtos import DocumentOutput, build_source_errors
from application.exceptions import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
)
from application.ports.document_repository_port import DocumentRepositoryPort


class GetDocumentUseCase:
    def __init__(self, document_repository: DocumentRepositoryPort) -> None:
        self._documents = document_repository

    async def execute(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentOutput:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"Document '{document_id}' does not exist."
            )
        if document.user_id != user_id:
            raise DocumentAccessDeniedError(
                f"Document '{document_id}' does not belong to this account."
            )

        return DocumentOutput(
            id=document.id,
            title=document.title,
            document_type=document.document_type,
            status=document.status,
            sections=document.sections,
            user_id=document.user_id,
            presentation=document.presentation,
            error_message=document.error_message,
            source_ids=[s.id for s in document.raw_sources],
            source_errors=build_source_errors(document.raw_sources),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
