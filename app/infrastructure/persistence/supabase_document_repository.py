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

from application.ports.document_repository_port import DocumentRepositoryPort
from application.ports.source_repository_port import SourceRepositoryPort


class SupabaseDocumentRepository(DocumentRepositoryPort):
    """
    Expects a `documents` table:
      id uuid pk, user_id uuid, title text, document_type text,
      source_id uuid (fk -> sources.id), presentation jsonb,
      status text, sections jsonb, sources jsonb,
      created_at timestamptz, updated_at timestamptz,
      error_message text nullable, export_url text nullable

    NOTE: serialization assumes `PresentationInfo`, `APASection` and
    `SourceReference` are plain dataclasses whose fields round-trip
    through `dataclasses.asdict` / `Class(**data)`. If any of them
    isn't a dataclass, or nests something non-JSON-serializable, adjust
    `_to_row` / `_to_entity` accordingly.

    Rebuilding a `Document` also requires its linked `Source`, so this
    adapter depends on a `SourceRepositoryPort` to fetch it.
    """

    _TABLE = "documents"

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

    async def save_export_url(self, document_id: UUID, export_url: str) -> None:
        await asyncio.to_thread(
            self._update_field_sync, str(document_id), "export_url", export_url
        )

    async def get_export_url(self, document_id: UUID) -> str | None:
        row = await asyncio.to_thread(self._get_row_sync, str(document_id))
        return row.get("export_url") if row else None

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

    def _update_field_sync(self, document_id: str, field: str, value) -> None:
        self._client.table(self._TABLE).update({field: value}).eq("id", document_id).execute()

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
