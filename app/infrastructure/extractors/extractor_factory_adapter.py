from domain.entities.source import SourceType

from application.exceptions import UnsupportedSourceTypeError
from application.ports.extractor_factory_port import ExtractorFactoryPort
from application.ports.source_extractor_port import SourceExtractorPort


class ExtractorFactoryAdapter(ExtractorFactoryPort):
    """
    Simple registry-based factory. Wire it once at startup, e.g.:

        factory = ExtractorFactoryAdapter({
            SourceType.WEB: WebExtractorAdapter(),
            SourceType.YOUTUBE: YoutubeExtractorAdapter(),
            SourceType.FILE: FileExtractorAdapter(),
            SourceType.TEXT: PlainTextExtractorAdapter(),
        })
    """

    def __init__(
        self, extractors: dict[SourceType, SourceExtractorPort]
    ) -> None:
        self._extractors = extractors

    def get_extractor(self, source_type: SourceType) -> SourceExtractorPort:
        extractor = self._extractors.get(source_type)
        if extractor is None:
            raise UnsupportedSourceTypeError(
                f"No extractor registered for source type '{source_type.value}'."
            )
        return extractor
