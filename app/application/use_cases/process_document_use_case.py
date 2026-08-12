from uuid import UUID

from application.exceptions import DocumentNotFoundError, SourceNotFoundError
from application.ports.document_exporter_resolver_port import DocumentExporterResolverPort
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.document_writer_port import DocumentWriterPort
from application.ports.extractor_factory_port import ExtractorFactoryPort
from application.ports.source_repository_port import SourceRepositoryPort

from domain.entities.source import SourceStatus


class ProcessDocumentUseCase:
    """
    Steps 2, 3 and 4 of the flow:
      2. Extract plain text from every source in `document.raw_sources`,
         each through its own extractor via `ExtractorFactoryPort`.
      3. Concatenate them and send to Gemini for the APA draft.
      4. Resolve the exporter for `document.export_target` and store
         the resulting `ExportResult`.
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        source_repository: SourceRepositoryPort,
        extractor_factory: ExtractorFactoryPort,
        document_writer: DocumentWriterPort,
        exporter_resolver: DocumentExporterResolverPort,
    ) -> None:
        self._documents = document_repository
        self._sources = source_repository
        self._extractor_factory = extractor_factory
        self._writer = document_writer
        self._exporter_resolver = exporter_resolver

    async def execute(self, document_id: UUID) -> None:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' does not exist.")

        sources = []
        for raw_source in document.raw_sources:
            source = await self._sources.get_by_id(raw_source.id)
            if source is None:
                raise SourceNotFoundError(f"Source '{raw_source.id}' does not exist.")
            sources.append(source)

        try:
            document.start_extraction()
            await self._documents.save(document)

            for source in sources:
                extractor = self._extractor_factory.get_extractor(source.source_type)
                content = await extractor.extract(source.raw)
                source.mark_extracted(content)
                await self._sources.save(source)

            combined_content = "\n\n".join(
                f"[Fuente {i + 1}]\n{s.get_content()}" for i, s in enumerate(sources)
            )

            document.start_generation()
            await self._documents.save(document)

            title, sections, references = await self._writer.write(
                source_content=combined_content,
                title=document.title,
                document_type=document.document_type,
                presentation=document.presentation,
            )
            
            document.title = title
            document.complete(sections=sections, sources=references)
            await self._documents.save(document)

            exporter = await self._exporter_resolver.resolve(
                document.export_target, document.user_id
            )
            export_result = await exporter.export(document)
            await self._documents.save_export_result(document.id, export_result)

        except Exception as exc:
            for source in sources:
                if source.status != SourceStatus.EXTRACTED:
                    source.mark_failed(str(exc))
                    await self._sources.save(source)
            document.fail(str(exc))
            await self._documents.save(document)
            raise
