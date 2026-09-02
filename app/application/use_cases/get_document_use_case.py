from uuid import UUID

from application.dtos.document_dtos import (
    DocumentFileOutput,
    DocumentOutput,
    build_source_errors,
)
from application.exceptions import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
)
from application.ports.document_buffer_port import DocumentBufferPort
from application.ports.document_exporter_port import DocumentExporterPort
from application.ports.document_repository_port import DocumentRepositoryPort


class GetDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        exporter: DocumentExporterPort,
        buffer: DocumentBufferPort,
    ) -> None:
        self._documents = document_repository
        self._exporter = exporter
        self._buffer = buffer

    async def execute(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentFileOutput:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"Document '{document_id}' does not exist."
            )
        if document.user_id != user_id:
            raise DocumentAccessDeniedError(
                f"Document '{document_id}' does not belong to this account."
            )

        metadata = DocumentOutput(
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
        exported = await self._exporter.export(document)
        await self._buffer.put(document.id, exported)
        if exported.file_bytes is None:
            raise RuntimeError("The DOCX exporter returned no binary content.")
        return DocumentFileOutput(
            document=metadata,
            file_bytes=exported.file_bytes,
            file_name=exported.file_name or f"{document.id}.docx",
            content_type=exported.content_type or "application/octet-stream",
        )
