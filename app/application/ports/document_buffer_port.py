from abc import ABC, abstractmethod
from uuid import UUID

from application.dtos.export_result import ExportResult


class DocumentBufferPort(ABC):
    """Process-local cache for generated document binaries."""

    @abstractmethod
    async def put(self, document_id: UUID, result: ExportResult) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, document_id: UUID) -> ExportResult | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        raise NotImplementedError
