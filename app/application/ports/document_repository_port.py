from abc import ABC, abstractmethod
from uuid import UUID

from domain.entities.document import Document


class DocumentRepositoryPort(ABC):
    """Driven port for persisting the Document aggregate. Adapter: Supabase."""

    @abstractmethod
    async def save(self, document: Document) -> None:
        """Insert or update, based on `document.id`."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[Document]:
        """
        NOTE: requires the Document aggregate (or the persistence model)
        to track ownership (`user_id`). Add that field before wiring
        this method to a real adapter.
        """
        raise NotImplementedError

    @abstractmethod
    async def save_export_url(self, document_id: UUID, export_url: str) -> None:
        """
        Persists the link returned by the DocumentExporterPort.
        Kept out of the `Document` entity on purpose, since it's an
        infrastructure detail (a Google Docs URL) rather than a business
        rule the domain needs to reason about.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_export_url(self, document_id: UUID) -> str | None:
        raise NotImplementedError
