from application.dtos.document_dtos import CreateDocumentInput, CreateDocumentOutput
from application.exceptions import UnsupportedSourceTypeError, UserNotFoundError
from application.ports.document_job_dispatcher_port import DocumentJobDispatcherPort
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.source_repository_port import SourceRepositoryPort
from application.ports.user_repository_port import UserRepositoryPort

from domain.entities.document import Document
from domain.entities.source import Source, SourceType


class CreateDocumentUseCase:
    """
    Registers the request (validates the user, creates the `Source`
    and `Document` aggregates in PENDING status, persists them) and
    hands the extraction + IA + export pipeline to `job_dispatcher`.

    NOTE on the "returns immediately" claim the original docstring
    made: with `SyncJobDispatcherAdapter`, the whole pipeline actually
    runs to completion inside `dispatch(...)` before this method
    returns. So `execute()` re-fetches the `Document` afterwards to
    report its *final* status/export result in the same response,
    instead of the stale PENDING snapshot it built a few lines above
    — there's no polling endpoint yet. Swap the dispatcher for a real
    queue later and this re-fetch will simply reflect PENDING/
    EXTRACTING again, which is still the correct behavior.
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

        try:
            source_type = SourceType(data.source_type)
        except ValueError as exc:
            raise UnsupportedSourceTypeError(
                f"Source type '{data.source_type}' is not supported."
            ) from exc

        source = Source.create(raw=data.source_raw, source_type=source_type)
        document = Document.create(
            user_id=data.user_id,
            title=data.title,
            document_type=data.document_type,
            source=source,
            presentation=data.presentation,
            export_target=data.export_target,
        )

        await self._sources.save(source)
        await self._documents.save(document)

        await self._dispatcher.dispatch(document.id)

        # `document` above is a stale, PENDING in-memory snapshot: the
        # sync dispatcher ran the whole pipeline against its own copy
        # fetched from the repository. Re-fetch to report reality.
        final_document = await self._documents.get_by_id(document.id) or document
        export_result = await self._documents.get_export_result(document.id)

        return CreateDocumentOutput(
            document_id=final_document.id,
            status=final_document.status,
            document_type=final_document.document_type,
            export_result=export_result,
            error_message=final_document.error_message,
        )

        await self._sources.save(source)
        await self._documents.save(document)

        await self._dispatcher.dispatch(document.id)

        return CreateDocumentOutput(document_id=document.id, status=document.status)
