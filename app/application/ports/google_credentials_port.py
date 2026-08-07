from abc import ABC, abstractmethod
from uuid import UUID


class GoogleCredentialsPort(ABC):
    """
    Read-only from this service's perspective: the Google OAuth consent
    screen and the first refresh_token write happen in the other
    backend (the one that owns Supabase user registration). This port
    only resolves the stored, decrypted refresh_token for a user so
    this service can exchange it for a working access_token.
    """

    @abstractmethod
    async def get_refresh_token(self, user_id: UUID) -> str | None:
        """
        Returns the decrypted refresh_token, or None if the user
        hasn't granted Google Docs/Drive access yet.
        """
        raise NotImplementedError
