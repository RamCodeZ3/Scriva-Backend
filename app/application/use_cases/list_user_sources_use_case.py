from uuid import UUID

from application.dtos.source_dtos import SourceOutput
from application.exceptions import SourceAccessDeniedError
from application.ports.source_repository_port import SourceRepositoryPort


class ListUserSourcesUseCase:
    def __init__(self, source_repository: SourceRepositoryPort) -> None:
        self._sources = source_repository

    async def execute(
        self, user_id: UUID, authenticated_user_id: UUID
    ) -> list[SourceOutput]:
        if user_id != authenticated_user_id:
            raise SourceAccessDeniedError(
                f"User '{authenticated_user_id}' cannot access sources "
                f"owned by '{user_id}'."
            )
        sources = await self._sources.list_by_user(user_id)
        return [SourceOutput.from_source(source) for source in sources]
