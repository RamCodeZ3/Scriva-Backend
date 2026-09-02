from application.dtos.document_dtos import (
    DocumentOutput,
    UpdateDocumentInput,
    build_source_errors,
)
from application.exceptions import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
)
from application.ports.document_buffer_port import DocumentBufferPort
from application.ports.document_parser_port import DocumentParserPort
from application.ports.document_repository_port import DocumentRepositoryPort


class UpdateDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        parser: DocumentParserPort,
        buffer: DocumentBufferPort,
    ) -> None:
        self._documents = document_repository
        self._parser = parser
        self._buffer = buffer

    async def execute(self, data: UpdateDocumentInput) -> DocumentOutput:
        document = await self._documents.get_by_id(data.document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"Document '{data.document_id}' does not exist."
            )
        if document.user_id != data.user_id:
            raise DocumentAccessDeniedError(
                f"Document '{data.document_id}' does not belong to this account."
            )

        sections = data.sections
        if data.docx_bytes is not None:
            sections = await self._parser.parse(data.docx_bytes)

        document.update_content(
            title=data.title,
            sections=sections,
            presentation=data.presentation,
        )
        await self._documents.save(document)
        await self._buffer.delete(document.id)

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
