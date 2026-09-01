import asyncio
from uuid import UUID

from application.dtos.export_result import ExportResult
from application.ports.document_buffer_port import DocumentBufferPort


class InMemoryDocumentBuffer(DocumentBufferPort):
    def __init__(self) -> None:
        self._items: dict[UUID, ExportResult] = {}
        self._lock = asyncio.Lock()

    async def put(self, document_id: UUID, result: ExportResult) -> None:
        async with self._lock:
            self._items[document_id] = result

    async def get(self, document_id: UUID) -> ExportResult | None:
        async with self._lock:
            return self._items.get(document_id)

    async def delete(self, document_id: UUID) -> None:
        async with self._lock:
            self._items.pop(document_id, None)
