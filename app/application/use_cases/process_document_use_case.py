from uuid import UUID

from application.exceptions import DocumentNotFoundError, SourceNotFoundError
from application.ports.document_exporter_port import DocumentExporterPort
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.document_writer_port import DocumentWriterPort
from application.ports.extractor_factory_port import ExtractorFactoryPort
from application.ports.source_repository_port import SourceRepositoryPort

from domain.entities.source import SourceStatus


class ProcessDocumentUseCase:
    """
    Steps 2, 3 and 4 of the flow, run by the background job dispatched
    from `CreateDocumentUseCase`:

      2. Extract plain text from the source (Playwright / PyTube / file
         reader / plain text), chosen through `ExtractorFactoryPort`.
      3. Send that text to Gemini (`DocumentWriterPort`) and get back
         the APA sections + references.
      4. Export the finished document with the Google Docs adapter
         (`DocumentExporterPort`) and store the resulting link.

    Every stage updates the `Document`'s status so `GetDocumentStatusUseCase`
    can report progress, and any failure is captured through
    `Document.fail(...)` / `Source.mark_failed(...)` instead of leaving
    the aggregate in an inconsistent state.
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        source_repository: SourceRepositoryPort,
        extractor_factory: ExtractorFactoryPort,
        document_writer: DocumentWriterPort,
        document_exporter: DocumentExporterPort,
    ) -> None:
        self._documents = document_repository
        self._sources = source_repository
        self._extractor_factory = extractor_factory
        self._writer = document_writer
        self._exporter = document_exporter

    async def execute(self, document_id: UUID) -> None:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' does not exist.")

        source = await self._sources.get_by_id(document.source.id)
        if source is None:
            raise SourceNotFoundError(f"Source '{document.source.id}' does not exist.")

        try:
            # 2. Extraction
            document.start_extraction()
            await self._documents.save(document)

            extractor = self._extractor_factory.get_extractor(source.source_type)
            content = await extractor.extract(source.raw)
            source.mark_extracted(content)
            await self._sources.save(source)

            # 3. AI drafting
            document.start_generation()
            await self._documents.save(document)

            sections, references = await self._writer.write(
                source_content=source.get_content(),
                title=document.title,
                document_type=document.document_type,
                presentation=document.presentation,
            )
            document.complete(sections=sections, sources=references)
            await self._documents.save(document)

            # 4. Export
            export_url = await self._exporter.export(document)
            await self._documents.save_export_url(document.id, export_url)

        except Exception as exc:
            if source.status != SourceStatus.EXTRACTED:
                source.mark_failed(str(exc))
                await self._sources.save(source)
            document.fail(str(exc))
            await self._documents.save(document)
            raise
