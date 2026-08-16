from __future__ import annotations

from application.dtos.document_dtos import AugmentDocumentInput, DocumentOutput
from application.exceptions import DocumentAccessDeniedError, DocumentNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.document_writer_port import DocumentWriterPort
from application.ports.extractor_factory_port import ExtractorFactoryPort
from application.ports.source_repository_port import SourceRepositoryPort

from domain.entities.document import DocumentStatus
from domain.entities.source import Source
from domain.exceptions import DocumentBuildError


class AugmentDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        source_repository: SourceRepositoryPort,
        extractor_factory: ExtractorFactoryPort,
        document_writer: DocumentWriterPort,
    ) -> None:
        self._documents = document_repository
        self._sources = source_repository
        self._extractor_factory = extractor_factory
        self._writer = document_writer

    async def execute(self, data: AugmentDocumentInput) -> DocumentOutput:
        document = await self._documents.get_by_id(data.document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{data.document_id}' does not exist.")
        if document.user_id != data.user_id:
            raise DocumentAccessDeniedError(
                f"Document '{data.document_id}' does not belong to this account."
            )
        if document.status != DocumentStatus.DONE:
            raise DocumentBuildError(
                f"Cannot add info to a document in '{document.status.value}' status; "
                "it must be 'done'."
            )

        new_sources = [Source.create_auto(raw) for raw in data.sources]
        for source in new_sources:
            extractor = self._extractor_factory.get_extractor(source.source_type)
            content = await extractor.extract(source.raw)
            source.mark_extracted(content)
            await self._sources.save(source)

        new_content = "\n\n".join(
            f"[Fuente nueva {i + 1}]\n{s.get_content()}" for i, s in enumerate(new_sources)
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
            title=title, sections=sections, sources=references, new_raw_sources=new_sources
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
