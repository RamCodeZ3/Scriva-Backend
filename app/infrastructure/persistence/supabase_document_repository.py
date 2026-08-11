from __future__ import annotations

import asyncio
import dataclasses
import json
from datetime import datetime
from enum import Enum
from uuid import UUID

from supabase import Client

from domain.entities.document import Document, DocumentStatus
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference

from application.dtos.export_result import ExportResult
from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.source_repository_port import SourceRepositoryPort


class SupabaseDocumentRepository(DocumentRepositoryPort):
    """
    Expects a `documents` table:
      id uuid pk, user_id uuid, title text, document_type text,
      source_id uuid (fk -> sources.id), presentation jsonb,
      status text, sections jsonb, sources jsonb,
      created_at timestamptz, updated_at timestamptz,
      error_message text nullable,
      document_url text nullable,          -- ExportResult.url (Google Docs)
      export_file_name text nullable,      -- ExportResult.file_name (PDF)
      export_content_type text nullable,   -- ExportResult.content_type (PDF)
      export_storage_path text nullable    -- ExportResult.storage_path (PDF, local disk)

    NOTE: `ExportResult.file_bytes` is intentionally NEVER persisted
    here — PDFs stay on local disk only (`storage_path`); nothing
    binary goes into Postgres for now. If that changes later, this is
    the one place to add it (e.g. a Supabase Storage bucket column).
    """

    _TABLE = "documents"
    _EXPORT_COLUMNS = (
        "document_url",
        "export_file_name",
        "export_content_type",
        "export_storage_path",
    )

    def __init__(self, client: Client, source_repository: SourceRepositoryPort) -> None:
        self._client = client
        self._sources = source_repository

    async def save(self, document: Document) -> None:
        await asyncio.to_thread(self._save_sync, document)

    async def get_by_id(self, document_id: UUID) -> Document | None:
        row = await asyncio.to_thread(self._get_row_sync, str(document_id))
        if row is None:
            return None
        return await self._to_entity(row)

    async def list_by_user(self, user_id: UUID) -> list[Document]:
        rows = await asyncio.to_thread(self._list_rows_by_user_sync, str(user_id))
        return [await self._to_entity(row) for row in rows]

    async def save_export_result(self, document_id: UUID, export_result: ExportResult) -> None:
        await asyncio.to_thread(
            self._update_fields_sync,
            str(document_id),
            {
                "document_url": export_result.url,
                "export_file_name": export_result.file_name,
                "export_content_type": export_result.content_type,
                "export_storage_path": export_result.storage_path,
            },
        )

    async def get_export_result(self, document_id: UUID) -> ExportResult | None:
        row = await asyncio.to_thread(self._get_row_sync, str(document_id))
        if row is None:
            return None

        if not any(row.get(col) for col in self._EXPORT_COLUMNS):
            return None  # nothing exported (yet)

        return ExportResult(
            url=row.get("document_url"),
            file_bytes=None,  # never persisted — see class docstring
            file_name=row.get("export_file_name"),
            content_type=row.get("export_content_type"),
            storage_path=row.get("export_storage_path"),
        )

    # ── sync helpers (run inside a thread) ──────────────────────────────

    def _save_sync(self, document: Document) -> None:
        self._client.table(self._TABLE).upsert(self._to_row(document)).execute()

    def _get_row_sync(self, document_id: str) -> dict | None:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("id", document_id)
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else None

    def _list_rows_by_user_sync(self, user_id: str) -> list[dict]:
        result = self._client.table(self._TABLE).select("*").eq("user_id", user_id).execute()
        return result.data or []

    def _update_fields_sync(self, document_id: str, fields: dict) -> None:
        self._client.table(self._TABLE).update(fields).eq("id", document_id).execute()

    # ── mapping ──────────────────────────────────────────────────────────

    def _to_row(self, document: Document) -> dict:
        return {
            "id": str(document.id),
            "user_id": str(document.user_id),
            "title": document.title,
            "document_type": document.document_type.value,
            "source_id": str(document.source.id),
            "presentation": _to_jsonable(document.presentation),
            "status": document.status.value,
            "sections": [_to_jsonable(s) for s in document.sections],
            "sources": [_to_jsonable(s) for s in document.sources],
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "error_message": document.error_message,
        }

    async def _to_entity(self, row: dict) -> Document:
        source = await self._sources.get_by_id(UUID(row["source_id"]))
        if source is None:
            raise ValueError(
                f"Document '{row['id']}' references a missing source '{row['source_id']}'."
            )

        return Document(
            id=UUID(row["id"]),
            user_id=UUID(row["user_id"]),
            title=row["title"],
            document_type=DocumentType(row["document_type"]),
            source=source,
            presentation=PresentationInfo(**row["presentation"]),
            status=DocumentStatus(row["status"]),
            sections=[_section_from_dict(s) for s in row["sections"]],
            sources=[SourceReference(**s) for s in row["sources"]],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            error_message=row.get("error_message"),
        )


def _to_jsonable(value) -> dict:
    data = dataclasses.asdict(value)
    return json.loads(json.dumps(data, default=_json_default))


def _json_default(obj):
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _section_from_dict(data: dict) -> APASection:
    data = dict(data)
    data["section_type"] = APASectionType(data["section_type"])
    return APASection(**data)
