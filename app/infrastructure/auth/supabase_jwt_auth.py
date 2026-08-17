from __future__ import annotations

import jwt
from jwt import PyJWKClient
from dotenv import load_dotenv

load_dotenv()


class InvalidTokenError(Exception):
    """Raised when the bearer token is missing, malformed, or expired."""


class SupabaseJWTAuth:
    def __init__(
        self,
        project_url: str,
        api_key: str,
        audience: str = "authenticated",
        legacy_secret: str | None = None,
    ) -> None:
        jwks_url = f"{project_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        self._jwks_client = PyJWKClient(
            jwks_url,
            headers={"apikey": api_key},
            cache_keys=True,
        )
        self._audience = audience
        self._legacy_secret = legacy_secret

    def decode(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        # Legacy HS256 tokens aren't resolvable via JWKS (no matching
        # public key) — verify those against the shared secret instead.
        if header.get("alg") == "HS256":
            if not self._legacy_secret:
                raise InvalidTokenError(
                    "Received a legacy HS256 token but no legacy_secret was configured."
                )
            try:
                return jwt.decode(
                    token,
                    self._legacy_secret,
                    algorithms=["HS256"],
                    audience=self._audience,
                )
            except jwt.PyJWTError as exc:
                raise InvalidTokenError(str(exc)) from exc

        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience=self._audience,
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc
