from uuid import UUID

from application.dtos.user_dtos import UpdateUserProfileInput, UserOutput
from application.exceptions import UserNotFoundError
from application.ports.user_repository_port import UserRepositoryPort


class UpdateUserProfileUseCase:
    """Updates a user's editable profile fields (currently just the name)."""

    def __init__(self, user_repository: UserRepositoryPort) -> None:
        self._users = user_repository

    async def execute(self, user_id: UUID, data: UpdateUserProfileInput) -> UserOutput:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User '{user_id}' does not exist.")

        user.update_profile(name=data.name)
        await self._users.save(user)

        return UserOutput(
            id=user.id,
            email=user.email,
            name=user.name,
            is_premium=user.is_premium,
        )
