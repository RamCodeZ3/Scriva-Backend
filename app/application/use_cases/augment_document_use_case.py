from __future__ import annotations

from domain.entities.document import DocumentStatus
from domain.entities.source import Source
from domain.exceptions import DocumentBuildError

from application.dtos.document_dtos import (
    AugmentDocumentInput,
    DocumentFileOutput,
    DocumentOutput,
    build_source_errors,
)
from application.exceptions import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
    NoSourcesExtractedError,
)
from application.ports.document_exporter_port import DocumentExporterPort
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.document_writer_port import DocumentWriterPort
from application.ports.docx_cache_port import DocxCachePort
from application.ports.extractor_factory_port import ExtractorFactoryPort
from application.ports.source_repository_port import SourceRepositoryPort
from application.services.document_docx_cache import cache_docx


class AugmentDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        source_repository: SourceRepositoryPort,
        extractor_factory: ExtractorFactoryPort,
        document_writer: DocumentWriterPort,
        exporter: DocumentExporterPort,
        cache: DocxCachePort,
    ) -> None:
        self._documents = document_repository
        self._sources = source_repository
        self._extractor_factory = extractor_factory
        self._writer = document_writer
        self._exporter = exporter
        self._cache = cache

    async def execute(self, data: AugmentDocumentInput) -> DocumentFileOutput:
        document = await self._documents.get_by_id(data.document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"Document '{data.document_id}' does not exist."
            )
        if document.user_id != data.user_id:
            raise DocumentAccessDeniedError(
                f"Document '{data.document_id}' does not belong to this "
                "account."
            )
        if document.status != DocumentStatus.DONE:
            raise DocumentBuildError(
                "Cannot add info to a document in "
                f"'{document.status.value}' status; "
                "it must be 'done'."
            )

        new_sources = [Source.create_auto(raw) for raw in data.sources]
        extracted_sources = await self._extract_sources(new_sources)

        if not extracted_sources:
            # Nothing usable came out of this batch: don't touch the
            # document at all, just surface the aggregated failure.
            raise NoSourcesExtractedError(
                "None of the new sources could be extracted; "
                "nothing was added to the document."
            )

        new_content = "\n\n".join(
            f"[Fuente nueva {i + 1}]\n{s.get_content()}"
            for i, s in enumerate(extracted_sources)
        )

        title, sections, references = await self._writer.augment(
            existing_sections=document.sections,
            existing_references=document.sources,
            new_content=new_content,
            document_type=document.document_type,
            presentation=document.presentation,
            additional_notes=data.additional_notes,
        )

        document.augment(
            title=title,
            sections=sections,
            sources=references,
            # Keep ALL new sources (including the failed ones) so they
            # show up in raw_sources -> sources_error for the caller.
            new_raw_sources=new_sources,
        )
        await self._documents.save(document)

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
        if exported.file_bytes is None:
            raise RuntimeError("The DOCX exporter returned no binary content.")
        await cache_docx(
            self._cache,
            document,
            exported.file_bytes,
            invalidate_existing=True,
        )
        return DocumentFileOutput(
            document=metadata,
            file_bytes=exported.file_bytes,
            file_name=exported.file_name or f"{document.id}.docx",
            content_type=exported.content_type or "application/octet-stream",
        )

    async def _extract_sources(self, sources: list[Source]) -> list[Source]:
        extracted: list[Source] = []
        for source in sources:
            try:
                extractor = self._extractor_factory.get_extractor(
                    source.source_type
                )
                content = await extractor.extract(source.raw)
                source.mark_extracted(content)
                extracted.append(source)
            except Exception as exc:
                source.mark_failed(str(exc))
            finally:
                await self._sources.save(source)
        return extracted
