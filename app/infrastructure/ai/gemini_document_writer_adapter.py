from __future__ import annotations

import json
import re

from google import genai
from google.genai import types

from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference

from application.ports.document_writer_port import DocumentWriterPort

_SECTION_ORDER = [
    APASectionType.PRESENTATION,
    APASectionType.INDEX,
    APASectionType.INTRODUCTION,
    APASectionType.BODY,
    APASectionType.CONCLUSION,
    APASectionType.SOURCES,
]

_SUBHEADING_TOKEN = "## "

_SYSTEM_INSTRUCTION = (
    "You are an academic writing assistant. You write complete, well "
    "structured documents strictly following APA 7 formatting rules, in "
    "the same language as the source content.\n\n"
    "CRITICAL OUTPUT RULES — violating these breaks the document renderer, "
    "which treats every field as plain text, not Markdown or HTML:\n"
    "1. Never use Markdown or HTML syntax anywhere: no '#', '##', '###', "
    "no '**bold**', no '*italic*', no '`code`', no '- ' or '* ' bullet "
    "lists, no numbered lists like '1. '. Write everything as normal "
    "academic prose, in full sentences and paragraphs.\n"
    "2. The ONLY exception: inside a section's 'content', when you start a "
    f"new subtopic, put that subtopic's heading alone on its own line, "
    f"prefixed with exactly '{_SUBHEADING_TOKEN}' (two hash characters and "
    "one space) and nothing else on that line — no bold, no numbering, no "
    "trailing punctuation. Use this sparingly, only for genuine subtopic "
    "breaks, and only inside the 'body' section unless another section "
    "truly needs it.\n"
    "3. The document 'title' you generate must be a short, properly "
    "capitalized academic title written in your own words, in the same "
    "language as the source. It must NEVER be a URL, NEVER be copied "
    "verbatim from the source text, and must be at most ~12 words.\n"
    "4. Every section 'title' (e.g. for introduction, body, conclusion) "
    "must likewise be a short heading in your own words, never a URL and "
    "never verbatim source text.\n"
    "5. If the user's additional notes contain a questionnaire (a list of "
    "questions to answer), address every question explicitly and "
    "completely inside the 'body' section, in prose, while still "
    "producing all six required sections normally.\n"
    "You always answer with a single JSON object and nothing else — no "
    "markdown fences, no commentary, no preamble."
)

_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


class GeminiDocumentWriterAdapter(DocumentWriterPort):
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
        additional_notes: str | None = None,
    ) -> tuple[str, list[APASection], list[SourceReference]]:
        prompt = self._build_prompt(
            source_content=source_content,
            title=title,
            document_type=document_type,
            presentation=presentation,
            additional_notes=additional_notes,
        )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            raw_text = response.text
        except Exception as exc:
            raise DocumentBuildError(f"Gemini request failed: {exc}") from exc

        return self._parse_response(raw_text, fallback_title=title)

    def _build_prompt(
        self,
        *,
        source_content: str,
        title: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
        additional_notes: str | None,
    ) -> str:
        section_names = ", ".join(s.value for s in _SECTION_ORDER)
        notes = additional_notes.strip() if additional_notes and additional_notes.strip() else "None"
        return f"""
Write a "{document_type.value}" document, following APA 7 rules, based
exclusively on the source material below.

Topic / working title given by the user (use this only as a hint about the
subject — do NOT copy it verbatim, and especially never use it if it is a
URL): "{title}"

Additional notes from the user (extraction guidance, tone, focus, or a
questionnaire to answer inside "body" — see rule 5): {notes}

Required sections, in this exact order: {section_names}.

Presentation/cover page data: {presentation}

Respond with a single JSON object shaped exactly like this:
{{
  "title": "A short, original academic title you write yourself",
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

Reminder: "content" is plain prose, never Markdown. The only allowed markup
is a line starting with "{_SUBHEADING_TOKEN}" to introduce a subtopic
heading, used sparingly inside "body".

--- SOURCE MATERIAL START ---
{source_content}
--- SOURCE MATERIAL END ---
""".strip()

    def _parse_response(
        self, raw_text: str, *, fallback_title: str
    ) -> tuple[str, list[APASection], list[SourceReference]]:
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()

        try:
            data, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError as exc:
            raise DocumentBuildError(f"Gemini did not return valid JSON: {exc}") from exc

        title = self._validate_title(data.get("title"), field="title")

        raw_sections = data.get("sections")
        if not raw_sections:
            raise DocumentBuildError("Gemini response has no 'sections'.")

        try:
            sections = [
                APASection(
                    section_type=APASectionType(s["section_type"]),
                    title=self._validate_title(s["title"], field="section title"),
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

        return title, sections, references

    def _validate_title(self, value: object, *, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise DocumentBuildError(f"Gemini response has an empty {field}.")
        candidate = value.strip()
        if _URL_PATTERN.search(candidate):
            raise DocumentBuildError(
                f"Gemini returned a {field} that looks like a URL: {candidate!r}"
            )
        if len(candidate) > 200:
            raise DocumentBuildError(
                f"Gemini returned an implausibly long {field} "
                f"({len(candidate)} chars) — looks like copied source text."
            )
        return candidate
