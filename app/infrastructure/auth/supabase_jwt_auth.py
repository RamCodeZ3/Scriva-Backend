from __future__ import annotations

import jwt


class InvalidTokenError(Exception):
    """Raised when the bearer token is missing, malformed, or expired."""


class SupabaseJWTAuth:
    """
    Verifies a Supabase Auth JWT and returns its payload.

    Supabase signs access tokens with the project's JWT secret (HS256)
    by default — find it in Project Settings -> API -> JWT Secret.
    The `sub` claim is the Supabase Auth user id (what we call
    `auth_id` in the `users` table).
    """

    def __init__(
        self,
        jwt_secret: str,
        algorithm: str = "HS256",
        audience: str = "authenticated",
    ) -> None:
        self._secret = jwt_secret
        self._algorithm = algorithm
        self._audience = audience

    def decode(self, token: str) -> dict:
        try:
            return jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                audience=self._audience,
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc
