from domain.exceptions import InvalidSourceError

from application.ports.source_extractor_port import SourceExtractorPort


class PlainTextExtractorAdapter(SourceExtractorPort):
    """No real extraction needed — the raw input already is the content."""

    async def extract(self, raw: str) -> str:
        content = raw.strip()
        if not content:
            raise InvalidSourceError("Plain text source is empty.")
        return content
