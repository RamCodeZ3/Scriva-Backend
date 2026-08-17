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

_SUBHEADING_TOKEN = "## "

_SECTION_ORDER = [
    APASectionType.PRESENTATION,
    APASectionType.INDEX,
    APASectionType.INTRODUCTION,
    APASectionType.BODY,
    APASectionType.CONCLUSION,
    APASectionType.SOURCES,
]

_FORMAT_RULES = (
    "CRITICAL OUTPUT RULES — the renderer interprets a small, specific "
    "subset of Markdown and nothing else. Anything outside this subset "
    "breaks formatting, so follow these exactly:\n"
    "1. Write in normal academic prose, in full sentences and paragraphs. "
    "Do NOT use '#', '###', backticks, single-asterisk/underscore italics, "
    "or any Markdown beyond what is explicitly allowed in rules 2-4 below.\n"
    "2. Subtopic headings: when starting a new subtopic inside 'body' "
    "(rarely elsewhere), put that heading alone on its own line, prefixed "
    f"with exactly '{_SUBHEADING_TOKEN}' and nothing else on that line. "
    "Use this sparingly, only for genuine subtopic breaks.\n"
    "3. Emphasis: you may use **bold** for key terms and __underline__ for "
    "titles or terms that require underlining, but only where it is "
    "genuinely useful. Never bold or underline whole sentences, and do not "
    "overuse either.\n"
    "4. Lists: you may use a bullet list (lines starting with '- ') or a "
    "numbered list (lines starting with '1. ', '2. ', etc.), following "
    "APA 7 rules: use bullets ONLY when the items have no meaningful order, "
    "priority, or hierarchy among them (equivalent characteristics, "
    "examples, parallel items); use numbers when the items follow a "
    "sequence of steps, a chronology, or a ranked hierarchy. Every item in "
    "a list must be grammatically parallel with the others (all full "
    "sentences, or all short fragments — not mixed). Lists are the "
    "exception, not the default — most content should stay in ordinary "
    "prose paragraphs, and you should not reach for a list unless the "
    "content is genuinely list-like.\n"
    "5. Paragraphs: keep paragraphs short and centered on a single idea. "
    "Never merge several distinct ideas into one long paragraph — split "
    "them into separate, focused paragraphs instead.\n"
    "6. Titles (document title and every section title) must be short, "
    "original, in your own words, in the source's language, NEVER a URL, "
    "NEVER copied verbatim from source text, at most ~12 words."
)

_SYSTEM_INSTRUCTION = (
    "You are an academic writing assistant. You write complete, well "
    "structured documents strictly following APA 7 formatting rules, in "
    "the same language as the source content.\n\n"
    f"{_FORMAT_RULES}\n"
    "7. If the user's additional notes contain a questionnaire (a list of "
    "questions to answer), address every question explicitly and "
    "completely inside 'body', while still producing all six required "
    "sections normally.\n"
    "8. The 'presentation' section is REQUIRED and must exist, but it is "
    "NOT a summary or abstract of the document's topic. Its 'content' must "
    "restate ONLY the structured presentation data given to you below — "
    "student name, institution, subject/course, professor, student ID (if "
    "provided), and today's date — each on its own line, in the source's "
    "language, exactly as given. Do NOT add a summary of what the document "
    "is about, do NOT add any sentence that isn't one of those fields, and "
    "do NOT omit any of the fields that were provided to you.\n"
    "9. The 'index' section is a short plain-language outline of what each "
    "section covers, written as prose or a simple list of section names — "
    "NEVER invent page numbers, since you have no way of knowing how the "
    "final document will paginate. The renderer builds the authoritative, "
    "paginated table of contents separately from the real headings; treat "
    "this section only as a narrative overview.\n"
    "You always answer with a single JSON object and nothing else — no "
    "markdown fences, no commentary, no preamble."
)

_AUGMENT_SYSTEM_INSTRUCTION = (
    "You are an academic writing assistant. You update an EXISTING APA 7 "
    "document with new source material, deciding per-section whether it "
    "needs to change.\n\n"
    f"{_FORMAT_RULES}\n"
    "7. For every section, decide: if the new material doesn't affect it, "
    'return it with "unchanged": true and nothing else — do NOT repeat '
    "its old text, that wastes tokens. If it does, return the FULL updated "
    "'title' and 'content' for that section.\n"
    "8. If the new material is a genuinely new subtopic not covered yet in "
    "'body', add it as a new subheading block using the token from rule 2, "
    "appended at a sensible point — don't just tack it onto an unrelated "
    "paragraph.\n"
    "9. If the new material complements or extends a topic already present "
    "in 'body', merge it into that existing paragraph/subtopic instead of "
    "duplicating it as a separate block.\n"
    "10. Update 'index', 'sources' and 'conclusion' if the new content "
    "changes what they should say; otherwise mark them unchanged. The "
    "'index' is a narrative overview only — NEVER invent page numbers, the "
    "renderer builds the authoritative table of contents separately.\n"
    "11. 'introduction' is almost never affected by new material — mark it "
    "unchanged unless the new content truly changes the document's overall "
    "scope. 'presentation' must always be present too — mark it unchanged "
    "if the structured presentation data hasn't changed; if it has, regen "
    "it following the same rule as before: only the structured fields "
    "(student name, institution, subject, professor, student ID, date), "
    "one per line, never a summary of the document's topic.\n"
    "You always answer with a single JSON object and nothing else — no "
    "markdown fences, no commentary, no preamble."
)

_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


class GeminiDocumentWriterAdapter(DocumentWriterPort):
    def __init__(
        self, api_key: str, model_name: str = "gemini-3.5-flash"
    ) -> None:
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
        raw_text = await self._generate(
            prompt, system_instruction=_SYSTEM_INSTRUCTION
        )
        return self._parse_response(raw_text)

    async def augment(
        self,
        *,
        existing_sections: list[APASection],
        existing_references: list[SourceReference],
        new_content: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
        additional_notes: str | None = None,
    ) -> tuple[str, list[APASection], list[SourceReference]]:
        prompt = self._build_augment_prompt(
            existing_sections=existing_sections,
            existing_references=existing_references,
            new_content=new_content,
            document_type=document_type,
            presentation=presentation,
            additional_notes=additional_notes,
        )
        raw_text = await self._generate(
            prompt, system_instruction=_AUGMENT_SYSTEM_INSTRUCTION
        )
        return self._parse_augment_response(
            raw_text, existing_sections=existing_sections
        )

    async def _generate(self, prompt: str, *, system_instruction: str) -> str:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            return response.text
        except Exception as exc:
            raise DocumentBuildError(f"Gemini request failed: {exc}") from exc

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
        notes = _clean_notes(additional_notes)
        return f"""
Write a "{document_type.value}" document, following APA 7 rules, based
exclusively on the source material below.

Topic / working title given by the user (use this only as a hint about the
subject — do NOT copy it verbatim, and especially never use it if it is a
URL): "{title}"

Additional notes from the user (extraction guidance, tone, focus, or a
questionnaire to answer inside "body"): {notes}

Required sections, in this exact order: {section_names}.

Presentation/cover page data — the 'presentation' section's content must
restate exactly these fields, one per line, and nothing else: {presentation}

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

Reminder: "content" is plain academic prose. The only Markdown allowed is
**bold**, __underline__, "- " bullet lists, "1. " numbered lists (per the
APA 7 rules above), and a line starting with "{_SUBHEADING_TOKEN}" to
introduce a subtopic heading — used sparingly, and mostly inside "body".

--- SOURCE MATERIAL START ---
{source_content}
--- SOURCE MATERIAL END ---
""".strip()

    def _build_augment_prompt(
        self,
        *,
        existing_sections: list[APASection],
        existing_references: list[SourceReference],
        new_content: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
        additional_notes: str | None,
    ) -> str:
        notes = _clean_notes(additional_notes)
        existing_sections_json = json.dumps(
            [
                {
                    "section_type": s.section_type.value,
                    "title": s.title,
                    "content": s.content,
                }
                for s in existing_sections
            ],
            ensure_ascii=False,
        )
        existing_refs_json = json.dumps(
            [
                {
                    "author": r.author,
                    "year": r.year,
                    "title": r.title,
                    "url": r.url,
                }
                for r in existing_references
            ],
            ensure_ascii=False,
        )
        return f"""
This is an existing "{document_type.value}" APA 7 document you must update
with new source material — not rewrite from scratch.

Existing sections (JSON, one entry per section_type): {existing_sections_json}

Existing references (JSON): {existing_refs_json}

Presentation/cover page data — the 'presentation' section's content must
restate exactly these fields, one per line, and nothing else: {presentation}

User's additional notes for this update: {notes}

New source material to incorporate:
--- NEW MATERIAL START ---
{new_content}
--- NEW MATERIAL END ---

Respond with a single JSON object shaped exactly like this:
{{
  "title": "usually the same title as before, unless it must change",
  "sections": [
    {{"section_type": "presentation", "unchanged": true}},
    {{"section_type": "index", "title": "...", "content": "..."}},
    {{"section_type": "introduction", "unchanged": true}},
    {{"section_type": "body", "title": "...", "content": "..."}},
    {{"section_type": "conclusion", "title": "...", "content": "..."}},
    {{"section_type": "sources", "title": "...", "content": "..."}}
  ],
  "references": [
    {{"author": "...", "year": "...", "title": "...", "url": "..."}}
  ]
}}

Every section_type must appear exactly once, either as "unchanged": true
or with full "title"/"content". "references" must be the complete,
de-duplicated list (old entries plus any genuinely new ones).
""".strip()

    def _parse_response(
        self, raw_text: str
    ) -> tuple[str, list[APASection], list[SourceReference]]:
        data = _decode_json(raw_text)
        title = self._validate_title(data.get("title"), field="title")

        raw_sections = data.get("sections")
        if not raw_sections:
            raise DocumentBuildError("Gemini response has no 'sections'.")

        try:
            sections = [
                APASection(
                    section_type=APASectionType(s["section_type"]),
                    title=self._validate_title(
                        s["title"], field="section title"
                    ),
                    content=s["content"],
                )
                for s in raw_sections
            ]
        except (KeyError, ValueError) as exc:
            raise DocumentBuildError(
                f"Malformed section in Gemini response: {exc}"
            ) from exc

        references = self._parse_references(data)
        return title, sections, references

    def _parse_augment_response(
        self, raw_text: str, *, existing_sections: list[APASection]
    ) -> tuple[str, list[APASection], list[SourceReference]]:
        data = _decode_json(raw_text)
        title = self._validate_title(data.get("title"), field="title")

        raw_sections = data.get("sections")
        if not raw_sections:
            raise DocumentBuildError("Gemini response has no 'sections'.")

        existing_by_type = {s.section_type: s for s in existing_sections}
        sections: list[APASection] = []
        for s in raw_sections:
            try:
                section_type = APASectionType(s["section_type"])
            except (KeyError, ValueError) as exc:
                raise DocumentBuildError(
                    f"Malformed section in Gemini response: {exc}"
                ) from exc

            if s.get("unchanged"):
                existing = existing_by_type.get(section_type)
                if existing is None:
                    raise DocumentBuildError(
                        f"Gemini marked '{section_type.value}' unchanged but no "
                        "prior version exists."
                    )
                sections.append(existing)
                continue

            try:
                sections.append(
                    APASection(
                        section_type=section_type,
                        title=self._validate_title(
                            s["title"], field="section title"
                        ),
                        content=s["content"],
                    )
                )
            except KeyError as exc:
                raise DocumentBuildError(
                    f"Malformed section in Gemini response: {exc}"
                ) from exc

        references = self._parse_references(data)
        return title, sections, references

    def _parse_references(self, data: dict) -> list[SourceReference]:
        try:
            return [
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


def _clean_notes(additional_notes: str | None) -> str:
    return (
        additional_notes.strip()
        if additional_notes and additional_notes.strip()
        else "None"
    )


def _decode_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError as exc:
        raise DocumentBuildError(
            f"Gemini did not return valid JSON: {exc}"
        ) from exc
    return data
