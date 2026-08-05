from uuid import UUID

from application.dtos.document_dtos import DocumentStatusOutput
from application.exceptions import UserNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.user_repository_port import UserRepositoryPort


class ListUserDocumentsUseCase:
    """
    Returns a status summary of every document created by a user
    (e.g. for a "my documents" dashboard).

    NOTE: relies on `DocumentRepositoryPort.list_by_user`, which in turn
    requires the Document aggregate/persistence model to track
    ownership. Add a `user_id` field to `Document` (or an equivalent
    column in the Supabase table) before implementing that adapter.
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        user_repository: UserRepositoryPort,
    ) -> None:
        self._documents = document_repository
        self._users = user_repository

    async def execute(self, user_id: UUID) -> list[DocumentStatusOutput]:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User '{user_id}' does not exist.")

        documents = await self._documents.list_by_user(user_id)
        return [
            DocumentStatusOutput(
                document_id=d.id,
                status=d.status,
                error_message=d.error_message,
            )
            for d in documents
        ]
