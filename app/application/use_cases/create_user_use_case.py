from application.dtos.user_dtos import CreateUserInput, UserOutput
from application.exceptions import UserAlreadyExistsError
from application.ports.user_repository_port import UserRepositoryPort

from domain.entities.user import User


class CreateUserUseCase:
    """Registers a new user account (used before they can request documents)."""

    def __init__(self, user_repository: UserRepositoryPort) -> None:
        self._users = user_repository

    async def execute(self, data: CreateUserInput) -> UserOutput:
        existing = await self._users.get_by_email(data.email)
        if existing is not None:
            raise UserAlreadyExistsError(
                f"Email '{data.email}' is already registered."
            )

        user = User.create(email=data.email, name=data.name)
        await self._users.save(user)

        return UserOutput(
            id=user.id,
            email=user.email,
            name=user.name,
            is_premium=user.is_premium,
        )
