from abc import ABC, abstractmethod
from uuid import UUID

from domain.entities.user import User


class UserRepositoryPort(ABC):
    """Driven port for persisting User entities. Adapter: Supabase."""

    @abstractmethod
    async def save(self, user: User) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError
