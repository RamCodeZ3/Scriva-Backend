from abc import ABC, abstractmethod
from uuid import UUID

from domain.entities.source import Source


class SourceRepositoryPort(ABC):
    """Driven port for persisting Source entities. Adapter: Supabase."""

    @abstractmethod
    async def save(self, source: Source) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, source_id: UUID) -> Source | None:
        raise NotImplementedError
