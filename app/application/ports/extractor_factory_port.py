from abc import ABC, abstractmethod

from domain.entities.source import SourceType

from application.ports.source_extractor_port import SourceExtractorPort


class ExtractorFactoryPort(ABC):
    """
    Driven port that resolves which SourceExtractorPort implementation
    must be used for a given SourceType. This keeps the use cases fully
    decoupled from Playwright/PyTube/file-system wiring: they just ask
    "give me the extractor for this type" and use it.
    """

    @abstractmethod
    def get_extractor(self, source_type: SourceType) -> SourceExtractorPort:
        """
        Must raise `application.exceptions.UnsupportedSourceTypeError`
        if no adapter is registered for the given type.
        """
        raise NotImplementedError
