from uuid import UUID

from application.dtos.document_dtos import DocumentDetailOutput
from application.exceptions import DocumentNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort


class GetDocumentUseCase:
    """Returns the full document (sections, sources) plus its Google Docs link."""

    def __init__(self, document_repository: DocumentRepositoryPort) -> None:
        self._documents = document_repository

    async def execute(self, document_id: UUID) -> DocumentDetailOutput:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' does not exist.")

        export_url = await self._documents.get_export_url(document_id)

        return DocumentDetailOutput(
            document_id=document.id,
            title=document.title,
            status=document.status,
            export_url=export_url,
            sections=document.sections,
            sources=document.sources,
        )
