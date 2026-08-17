from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from supabase import Client

from domain.entities.user import User

from application.ports.user_repository_port import UserRepositoryPort


class SupabaseUserRepository(UserRepositoryPort):
    _TABLE = "users"

    def __init__(self, client: Client) -> None:
        self._client = client

    async def save(self, user: User) -> None:
        await asyncio.to_thread(self._save_sync, user)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await asyncio.to_thread(
            self._get_by_column_sync, "id", str(user_id)
        )

    async def get_by_email(self, email: str) -> User | None:
        return await asyncio.to_thread(
            self._get_by_column_sync, "email", email.strip().lower()
        )

    def _save_sync(self, user: User) -> None:
        self._client.table(self._TABLE).upsert(self._to_row(user)).execute()

    def _get_by_column_sync(self, column: str, value: str) -> User | None:
        result = (
            self._client.table(self._TABLE)
            .select("*")
            .eq(column, value)
            .maybe_single()
            .execute()
        )
        return self._to_entity(result.data) if result and result.data else None

    @staticmethod
    def _to_row(user: User) -> dict:
        return {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.name,
            "is_premium": user.is_premium,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }

    @staticmethod
    def _to_entity(row: dict) -> User:
        return User(
            id=UUID(row["id"]),
            email=row["email"],
            name=row["display_name"],
            is_premium=row["is_premium"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
