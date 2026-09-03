from domain.entities.document import Document
from domain.entities.source import Source

from application.dtos.document_dtos import (
    CreateDocumentInput,
    DocumentFileOutput,
    DocumentOutput,
    build_source_errors,
)
from application.exceptions import UserNotFoundError
from application.ports.document_exporter_port import DocumentExporterPort
from application.ports.document_job_dispatcher_port import (
    DocumentJobDispatcherPort,
)
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.docx_cache_port import DocxCachePort
from application.ports.source_repository_port import SourceRepositoryPort
from application.ports.user_repository_port import UserRepositoryPort
from application.services.document_docx_cache import cache_docx


class CreateDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        source_repository: SourceRepositoryPort,
        user_repository: UserRepositoryPort,
        job_dispatcher: DocumentJobDispatcherPort,
        exporter: DocumentExporterPort,
        cache: DocxCachePort,
    ) -> None:
        self._documents = document_repository
        self._sources = source_repository
        self._users = user_repository
        self._dispatcher = job_dispatcher
        self._exporter = exporter
        self._cache = cache

    async def execute(self, data: CreateDocumentInput) -> DocumentFileOutput:
        user = await self._users.get_by_id(data.user_id)
        if user is None:
            raise UserNotFoundError(f"User '{data.user_id}' does not exist.")

        raw_sources = [Source.create_auto(raw) for raw in data.sources]
        for source in raw_sources:
            await self._sources.save(source)

        document = Document.create(
            user_id=data.user_id,
            title=data.title,
            document_type=data.document_type,
            raw_sources=raw_sources,
            presentation=data.presentation,
            additional_notes=data.additional_notes,
        )
        await self._documents.save(document)

        try:
            await self._dispatcher.dispatch(document.id)
        except Exception:
            pass

        final_document = (
            await self._documents.get_by_id(document.id) or document
        )

        metadata = DocumentOutput(
            id=final_document.id,
            title=final_document.title,
            document_type=final_document.document_type,
            status=final_document.status,
            sections=final_document.sections,
            user_id=final_document.user_id,
            presentation=final_document.presentation,
            error_message=final_document.error_message,
            source_ids=[s.id for s in final_document.raw_sources],
            source_errors=build_source_errors(final_document.raw_sources),
            created_at=final_document.created_at,
            updated_at=final_document.updated_at,
        )
        exported = await self._exporter.export(final_document)
        if exported.file_bytes is None:
            raise RuntimeError("The DOCX exporter returned no binary content.")
        await cache_docx(
            self._cache,
            final_document,
            exported.file_bytes,
            invalidate_existing=True,
        )
        return DocumentFileOutput(
            document=metadata,
            file_bytes=exported.file_bytes,
            file_name=exported.file_name or f"{final_document.id}.docx",
            content_type=exported.content_type or "application/octet-stream",
        )
