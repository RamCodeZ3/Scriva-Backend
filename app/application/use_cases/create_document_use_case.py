from application.dtos.document_dtos import CreateDocumentInput, CreateDocumentOutput
from application.exceptions import UserNotFoundError
from application.ports.document_job_dispatcher_port import DocumentJobDispatcherPort
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.source_repository_port import SourceRepositoryPort
from application.ports.user_repository_port import UserRepositoryPort

from domain.entities.document import Document
from domain.entities.source import Source


class CreateDocumentUseCase:
    """
    Registers the request (validates the user, creates the `Source`
    entities and the `Document` aggregate in PENDING status, persists
    them) and hands the extraction + IA + export pipeline to
    `job_dispatcher`.

    With `SyncJobDispatcherAdapter`, the whole pipeline runs to
    completion inside `dispatch(...)` before this method returns, so
    `execute()` re-fetches the `Document` afterwards to report its
    final status/export result — there's no polling endpoint yet.
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        source_repository: SourceRepositoryPort,
        user_repository: UserRepositoryPort,
        job_dispatcher: DocumentJobDispatcherPort,
    ) -> None:
        self._documents = document_repository
        self._sources = source_repository
        self._users = user_repository
        self._dispatcher = job_dispatcher

    async def execute(self, data: CreateDocumentInput) -> CreateDocumentOutput:
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
            export_target=data.export_target,
        )
        await self._documents.save(document)

        await self._dispatcher.dispatch(document.id)

        final_document = await self._documents.get_by_id(document.id) or document
        export_result = await self._documents.get_export_result(document.id)

        return CreateDocumentOutput(
            document_id=final_document.id,
            status=final_document.status,
            document_type=final_document.document_type,
            export_result=export_result,
            error_message=final_document.error_message,
        )
