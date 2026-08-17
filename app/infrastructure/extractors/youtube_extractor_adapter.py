from __future__ import annotations

import asyncio
import re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from domain.exceptions import InvalidSourceError

from application.ports.source_extractor_port import SourceExtractorPort

_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})"
)


class YoutubeExtractorAdapter(SourceExtractorPort):
    def __init__(self, preferred_langs: list[str] | None = None) -> None:
        self._preferred_langs = preferred_langs or ["es", "en"]

    async def extract(self, raw: str) -> str:
        video_id = self._extract_video_id(raw)
        try:
            transcript = await asyncio.to_thread(
                YouTubeTranscriptApi().fetch,
                video_id,
                languages=self._preferred_langs,
            )
        except (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        ) as exc:
            raise InvalidSourceError(
                f"No transcript available for '{raw}': {exc}"
            ) from exc
        except Exception as exc:
            raise InvalidSourceError(
                f"Could not extract transcript from '{raw}': {exc}"
            ) from exc

        text = " ".join(snippet.text for snippet in transcript)
        if not text.strip():
            raise InvalidSourceError(f"Transcript for '{raw}' is empty.")
        return text

    def _extract_video_id(self, raw: str) -> str:
        match = _ID_RE.search(raw)
        if not match:
            raise InvalidSourceError(
                f"Could not parse a YouTube video id from '{raw}'."
            )
        return match.group(1)
