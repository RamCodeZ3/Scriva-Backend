from __future__ import annotations

import asyncio
from uuid import UUID

from supabase import Client

from domain.entities.source import Source, SourceStatus, SourceType

from application.ports.source_repository_port import SourceRepositoryPort


class SupabaseSourceRepository(SourceRepositoryPort):
    """
    Maps to the real `sources` table (after the migration):
      id uuid pk, type text, raw text, status text, content text nullable,
      char_count int nullable, error_message text nullable, created_at timestamptz
    """

    _TABLE = "sources"

    def __init__(self, client: Client) -> None:
        self._client = client

    async def save(self, source: Source) -> None:
        await asyncio.to_thread(self._save_sync, source)

    async def get_by_id(self, source_id: UUID) -> Source | None:
        return await asyncio.to_thread(self._get_by_id_sync, source_id)

    # ── sync helpers ─────────────────────────────────────────────────────

    def _save_sync(self, source: Source) -> None:
        self._client.table(self._TABLE).upsert(self._to_row(source)).execute()

    def _get_by_id_sync(self, source_id: UUID) -> Source | None:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq("id", str(source_id))
            .maybe_single()
            .execute()
        )
        return self._to_entity(result.data) if result and result.data else None

    @staticmethod
    def _to_row(source: Source) -> dict:
        return {
            "id": str(source.id),
            "type": source.source_type.value,
            "raw": source.raw,
            "status": source.status.value,
            "content": source.content,
            "char_count": source.char_count,
            "error_message": source.error_message,
        }

    @staticmethod
    def _to_entity(row: dict) -> Source:
        return Source(
            id=UUID(row["id"]),
            source_type=SourceType(row["type"]),
            raw=row["raw"],
            status=SourceStatus(row["status"]),
            content=row.get("content"),
            char_count=row.get("char_count"),
            error_message=row.get("error_message"),
        )
