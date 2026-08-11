from __future__ import annotations

import json

from google import genai
from google.genai import types

from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference

from application.ports.document_writer_port import DocumentWriterPort

# NOTE — assumed value-object shapes (adjust `_parse_response` if yours differ):
#   APASection(section_type: APASectionType, title: str, content: str)
#   SourceReference(author: str, year: str, title: str, url: str | None)

_SECTION_ORDER = [
    APASectionType.PRESENTATION,
    APASectionType.INDEX,
    APASectionType.INTRODUCTION,
    APASectionType.BODY,
    APASectionType.CONCLUSION,
    APASectionType.SOURCES,
]

_SYSTEM_INSTRUCTION = (
    "You are an academic writing assistant. You write complete, well "
    "structured documents strictly following APA 7 formatting rules, in "
    "the same language as the source content. You always answer with a "
    "single JSON object and nothing else — no markdown fences, no "
    "commentary, no preamble."
)


class GeminiDocumentWriterAdapter(DocumentWriterPort):
    """Adapter for `DocumentWriterPort` backed by the official `google-genai` SDK."""

    def __init__(self, api_key: str, model_name: str = "gemini-3.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    async def write(
        self,
        *,
        source_content: str,
        title: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
    ) -> tuple[list[APASection], list[SourceReference]]:
        prompt = self._build_prompt(
            source_content=source_content,
            title=title,
            document_type=document_type,
            presentation=presentation,
        )

        try:
            # Usamos el cliente asíncrono `.aio` de la nueva librería
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text
        except Exception as exc:
            raise DocumentBuildError(f"Gemini request failed: {exc}") from exc

        return self._parse_response(raw_text)

    # ── Prompting ────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        *,
        source_content: str,
        title: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
    ) -> str:
        section_names = ", ".join(s.value for s in _SECTION_ORDER)
        return f"""
Write a "{document_type.value}" document titled "{title}", following APA 7
rules, based exclusively on the source material below.

Required sections, in this exact order: {section_names}.

Presentation/cover page data: {presentation}

Respond with a single JSON object shaped exactly like this:
{{
  "sections": [
    {{"section_type": "presentation", "title": "...", "content": "..."}},
    {{"section_type": "index", "title": "...", "content": "..."}},
    {{"section_type": "introduction", "title": "...", "content": "..."}},
    {{"section_type": "body", "title": "...", "content": "..."}},
    {{"section_type": "conclusion", "title": "...", "content": "..."}},
    {{"section_type": "sources", "title": "...", "content": "..."}}
  ],
  "references": [
    {{"author": "...", "year": "...", "title": "...", "url": "..."}}
  ]
}}

--- SOURCE MATERIAL START ---
{source_content}
--- SOURCE MATERIAL END ---
""".strip()

    # ── Response parsing ────────────────────────────────────────────────

    def _parse_response(
        self, raw_text: str
    ) -> tuple[list[APASection], list[SourceReference]]:
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise DocumentBuildError(f"Gemini did not return valid JSON: {exc}") from exc

        raw_sections = data.get("sections")
        if not raw_sections:
            raise DocumentBuildError("Gemini response has no 'sections'.")

        try:
            sections = [
                APASection(
                    section_type=APASectionType(s["section_type"]),
                    title=s["title"],
                    content=s["content"],
                )
                for s in raw_sections
            ]
        except (KeyError, ValueError) as exc:
            raise DocumentBuildError(f"Malformed section in Gemini response: {exc}") from exc

        try:
            references = [
                SourceReference(
                    author=r.get("author", ""),
                    year=r.get("year", ""),
                    title=r.get("title", ""),
                    url=r.get("url"),
                )
                for r in data.get("references", [])
            ]
        except (KeyError, TypeError) as exc:
            raise DocumentBuildError(
                f"Malformed reference in Gemini response: {exc}"
            ) from exc

        return sections, references
