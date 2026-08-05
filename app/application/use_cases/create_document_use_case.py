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
    Step 1 of the flow: the web layer sends the source/media plus the
    user info for the presentation page.

    This use case only *registers* the request: validates the user,
    creates the `Source` and `Document` aggregates in PENDING status,
    persists them, and hands the heavy lifting (extraction + IA +
    export) to a background job. It returns immediately so the API can
    answer with a document id the client will poll.
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
            title=data.title,
            document_type=data.document_type,
            source=source,
            presentation=data.presentation,
        )

        await self._sources.save(source)
        await self._documents.save(document)

        await self._dispatcher.dispatch(document.id)

        return CreateDocumentOutput(document_id=document.id, status=document.status)
