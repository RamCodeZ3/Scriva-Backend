from __future__ import annotations

import asyncio
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from supabase import Client

from application.ports.google_credentials_port import GoogleCredentialsPort


class SupabaseGoogleCredentialsRepository(GoogleCredentialsPort):
    _TABLE = "google_credentials"

    def __init__(self, client: Client, encryption_key: str) -> None:
        self._client = client
        self._fernet = Fernet(encryption_key.encode())

    async def get_refresh_token(self, user_id: UUID) -> str | None:
        row = await asyncio.to_thread(self._get_row_sync, str(user_id))
        if row is None or not row.get("encrypted_refresh_token"):
            return None

        try:
            return self._fernet.decrypt(
                row["encrypted_refresh_token"].encode()
            ).decode()
        except InvalidToken as exc:
            raise ValueError(
                f"Could not decrypt Google credentials for user '{user_id}': "
                f"wrong key or corrupted data."
            ) from exc

    def _get_row_sync(self, user_id: str) -> dict | None:
        result = (
            self._client.table(self._TABLE)
            .select("encrypted_refresh_token")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else None
