from __future__ import annotations

import asyncio
import re

from pytube import YouTube

from domain.exceptions import InvalidSourceError

from application.ports.source_extractor_port import SourceExtractorPort


class YoutubeExtractorAdapter(SourceExtractorPort):
    """
    Extracts metadata (title, author) and the transcript/captions of a
    YouTube video via PyTube.

    NOTE: PyTube's caption support depends on the video actually having
    captions (manual or auto-generated) available for one of the
    preferred languages. If YouTube changes its internal APIs and PyTube
    breaks, `youtube-transcript-api` is a solid drop-in replacement for
    just the transcript part.
    """

    def __init__(self, preferred_langs: list[str] | None = None) -> None:
        self._preferred_langs = preferred_langs or ["en", "a.en", "es", "a.es"]

    async def extract(self, raw: str) -> str:
        try:
            yt = await asyncio.to_thread(YouTube, raw)
            caption = self._pick_caption(yt)
            if caption is None:
                raise InvalidSourceError(f"No captions available for video '{raw}'.")
            srt = await asyncio.to_thread(caption.generate_srt_captions)
        except InvalidSourceError:
            raise
        except Exception as exc:
            raise InvalidSourceError(
                f"Could not extract transcript from '{raw}': {exc}"
            ) from exc

        transcript = _strip_srt(srt)
        if not transcript:
            raise InvalidSourceError(f"Transcript for '{raw}' is empty.")

        header = f"Title: {yt.title}\nAuthor: {yt.author}\n\n"
        return header + transcript

    def _pick_caption(self, yt: YouTube):
        for lang in self._preferred_langs:
            caption = yt.captions.get(lang)
            if caption is not None:
                return caption
        return next(iter(yt.captions.values()), None)


def _strip_srt(srt: str) -> str:
    """Removes sequence numbers and timestamps, keeping only spoken text."""
    text_lines = []
    for line in srt.splitlines():
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        text_lines.append(line)
    text = " ".join(text_lines)
    return re.sub(r"\s+", " ", text).strip()
