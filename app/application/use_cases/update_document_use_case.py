from application.dtos.document_dtos import DocumentOutput, UpdateDocumentInput
from application.exceptions import DocumentAccessDeniedError, DocumentNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort


class UpdateDocumentUseCase:
    def __init__(self, document_repository: DocumentRepositoryPort) -> None:
        self._documents = document_repository

    async def execute(self, data: UpdateDocumentInput) -> DocumentOutput:
        document = await self._documents.get_by_id(data.document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{data.document_id}' does not exist.")
        if document.user_id != data.user_id:
            raise DocumentAccessDeniedError(
                f"Document '{data.document_id}' does not belong to this account."
            )

        document.update_content(
            title=data.title, sections=data.sections, presentation=data.presentation
        )
        await self._documents.save(document)

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
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
