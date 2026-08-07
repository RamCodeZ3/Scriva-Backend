from __future__ import annotations

import asyncio

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class GoogleOAuthTokenProvider:
    """
    Exchanges a stored refresh_token for a short-lived access_token via
    Google's token endpoint. The refresh_token never leaves this
    process except to talk to Google — only the resulting access_token
    goes on to `GoogleDocsExporterAdapter`.
    """

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def get_access_token(self, refresh_token: str) -> str:
        return await asyncio.to_thread(self._refresh_sync, refresh_token)

    def _refresh_sync(self, refresh_token: str) -> str:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=self._client_id,
            client_secret=self._client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise ValueError(f"Could not refresh Google access token: {exc}") from exc

        return credentials.token
