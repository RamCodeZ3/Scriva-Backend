from abc import ABC, abstractmethod


class SourceExtractorPort(ABC):
    @abstractmethod
    async def extract(self, raw: str) -> str:
        """
        Returns the extracted plain text content, ready to be sent to
        the AI writer. Implementations must raise
        `domain.exceptions.InvalidSourceError` when extraction fails
        (broken link, private video, unreadable file, etc).
        """
        raise NotImplementedError
