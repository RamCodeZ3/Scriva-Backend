from uuid import UUID

from application.exceptions import DocumentAccessDeniedError, DocumentNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort


class DeleteDocumentUseCase:
    def __init__(self, document_repository: DocumentRepositoryPort) -> None:
        self._documents = document_repository

    async def execute(self, document_id: UUID, user_id: UUID) -> None:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' does not exist.")
        if document.user_id != user_id:
            raise DocumentAccessDeniedError(
                f"Document '{document_id}' does not belong to this account."
            )
        await self._documents.delete(document_id)
