from uuid import UUID

from application.dtos.source_dtos import SourceDetailOutput
from application.exceptions import (
    SourceAccessDeniedError,
    SourceNotFoundError,
)
from application.ports.source_repository_port import SourceRepositoryPort


class GetUserSourceUseCase:
    def __init__(self, source_repository: SourceRepositoryPort) -> None:
        self._sources = source_repository

    async def execute(
        self,
        user_id: UUID,
        source_id: UUID,
        authenticated_user_id: UUID,
    ) -> SourceDetailOutput:
        if user_id != authenticated_user_id:
            raise SourceAccessDeniedError(
                f"User '{authenticated_user_id}' cannot access sources "
                f"owned by '{user_id}'."
            )
        source = await self._sources.get_by_id_for_user(source_id, user_id)
        if source is None:
            raise SourceNotFoundError(
                f"Source '{source_id}' does not exist for user '{user_id}'."
            )
        return SourceDetailOutput.from_source(source)
