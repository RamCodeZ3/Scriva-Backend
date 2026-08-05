from abc import ABC, abstractmethod


class SourceExtractorPort(ABC):
    """
    Driven port implemented by one adapter per source type:
      - WebExtractorAdapter      -> Playwright
      - YoutubeExtractorAdapter  -> PyTube
      - FileExtractorAdapter     -> local/uploaded file parsing
      - PlainTextExtractorAdapter-> pass-through for raw text

    Each adapter only needs to know how to turn its kind of "raw" input
    into plain text; the use case doesn't care which one it's talking to.
    """

    @abstractmethod
    async def extract(self, raw: str) -> str:
        """
        Returns the extracted plain text content, ready to be sent to
        the AI writer. Implementations must raise
        `domain.exceptions.InvalidSourceError` when extraction fails
        (broken link, private video, unreadable file, etc).
        """
        raise NotImplementedError
