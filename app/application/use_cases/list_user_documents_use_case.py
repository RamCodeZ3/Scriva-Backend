from uuid import UUID

from application.dtos.document_dtos import DocumentReference
from application.exceptions import UserNotFoundError
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.user_repository_port import UserRepositoryPort


class ListUserDocumentsUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        user_repository: UserRepositoryPort,
    ) -> None:
        self._documents = document_repository
        self._users = user_repository

    async def execute(self, user_id: UUID) -> list[DocumentReference]:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User '{user_id}' does not exist.")

        return await self._documents.list_by_user(user_id)
