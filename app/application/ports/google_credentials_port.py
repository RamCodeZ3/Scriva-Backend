from abc import ABC, abstractmethod
from uuid import UUID


class GoogleCredentialsPort(ABC):
    @abstractmethod
    async def get_refresh_token(self, user_id: UUID) -> str | None:
        """
        Returns the decrypted refresh_token, or None if the user
        hasn't granted Google Docs/Drive access yet.
        """
        raise NotImplementedError
