from uuid import UUID

from application.dtos.document_dtos import DocumentStatusOutput
from application.exceptions import DocumentNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort


class GetDocumentStatusUseCase:
    """
    Lightweight use case meant to be polled by the frontend while a
    document is being generated (PENDING -> EXTRACTING -> GENERATING ->
    DONE/FAILED).
    """

    def __init__(self, document_repository: DocumentRepositoryPort) -> None:
        self._documents = document_repository

    async def execute(self, document_id: UUID) -> DocumentStatusOutput:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' does not exist.")

        return DocumentStatusOutput(
            document_id=document.id,
            status=document.status,
            error_message=document.error_message,
        )
