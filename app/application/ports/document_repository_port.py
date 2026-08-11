from abc import ABC, abstractmethod
from uuid import UUID

from domain.entities.document import Document

from application.dtos.export_result import ExportResult


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
    async def save_export_result(self, document_id: UUID, export_result: ExportResult) -> None:
        """
        Persists the outcome of `DocumentExporterPort.export(...)`.
        Kept out of the `Document` entity on purpose, since it's an
        infrastructure detail (a Google Docs URL, or a local PDF path)
        rather than a business rule the domain needs to reason about.

        RENAMED from `save_export_url(document_id, export_url: str)`:
        a PDF export doesn't produce a URL by itself, so the old
        `str`-only signature can't represent it. Map the new fields
        onto whatever columns make sense for you, e.g.:
        `export_url`, `export_storage_path`, `export_content_type`.
        Persisting `file_bytes` itself is optional — only worth it if
        you want the file retrievable after the process/disk goes
        away, instead of relying on `storage_path` on local disk.

        IMPORTANT: your `SupabaseDocumentRepository` (not shown to me)
        implements this port under the old method name — it needs to
        be renamed/updated to match, or this rename will break it.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_export_result(self, document_id: UUID) -> ExportResult | None:
        """Renamed from `get_export_url` for the same reason as above."""
        raise NotImplementedError
