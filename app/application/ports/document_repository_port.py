from abc import ABC, abstractmethod
from uuid import UUID

from domain.entities.document import Document

from application.dtos.export_result import ExportResult


class DocumentRepositoryPort(ABC):
    @abstractmethod
    async def save(self, document: Document) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    async def save_export_result(
        self, document_id: UUID, export_result: ExportResult
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_export_result(
        self, document_id: UUID
    ) -> ExportResult | None:
        raise NotImplementedError
