from abc import ABC, abstractmethod

from domain.entities.source import SourceType

from application.ports.source_extractor_port import SourceExtractorPort


class ExtractorFactoryPort(ABC):
    @abstractmethod
    def get_extractor(self, source_type: SourceType) -> SourceExtractorPort:
        """
        Must raise `application.exceptions.UnsupportedSourceTypeError`
        if no adapter is registered for the given type.
        """
        raise NotImplementedError
