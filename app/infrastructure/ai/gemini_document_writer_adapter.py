from __future__ import annotations

import json
import re
from dataclasses import replace as _with_replaced

from google import genai
from google.genai import types

from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_node import (
    BULLETED_LIST,
    HEADING_1,
    HEADING_2,
    LIST_ITEM,
    NUMBERED_LIST,
    PARAGRAPH,
    DocumentNode,
    text_node,
)
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

_NODE_SCHEMA_RULES = (
    "CRITICAL OUTPUT RULES — the renderer understands ONLY a small, "
    "specific tree of JSON node objects. NO Markdown anywhere. Each "
    "section's 'nodes' array is a list of BLOCK nodes. Each block node is "
    "one of:\n"
    f'  - {{"type": "{PARAGRAPH}", "children": [ TEXT, ... ]}} — normal '
    "academic prose, one idea per paragraph.\n"
    f'  - {{"type": "{HEADING_2}", "children": [ TEXT ]}} — a subtopic '
    "heading, used sparingly and mostly inside 'body' for genuine subtopic "
    "breaks. Never inside 'presentation' or 'index'.\n"
    f'  - {{"type": "{BULLETED_LIST}", "children": [ LIST_ITEM, ... ]}} — '
    "use ONLY when items have no meaningful order (parallel examples, "
    "equivalent characteristics).\n"
    f'  - {{"type": "{NUMBERED_LIST}", "children": [ LIST_ITEM, ... ]}} — '
    "use when items are steps, a chronology, or a ranked hierarchy.\n"
    f'  A LIST_ITEM is {{"type": "{LIST_ITEM}", "children": [ TEXT, ... ]}}.\n'
    '  A TEXT node is a leaf: {"text": "..."} or '
    '{"text": "...", "marks": ["bold"]} / ["underline"] — use marks only '
    "where genuinely useful (key terms, titles requiring underlining), "
    "never on whole sentences, never overused.\n"
    "Rules that still apply regardless of node type:\n"
    "- Lists are the exception, not the default: most content must be "
    "'paragraph' nodes. Every item in a list must be grammatically "
    "parallel with the others (all full sentences, or all short "
    "fragments — not mixed).\n"
    "- Keep paragraphs short and centered on a single idea; never merge "
    "several distinct ideas into one 'paragraph' node — split them into "
    "separate paragraph nodes instead.\n"
    "- Titles (document title and every section title) must be short, "
    "original, in your own words, in the source's language, NEVER a URL, "
    "NEVER copied verbatim from source text, at most ~12 words."
)

_SYSTEM_INSTRUCTION = (
    "You are an academic writing assistant. You write complete, well "
    "structured documents strictly following APA 7 formatting rules, in "
    "the same language as the source content, as a JSON node tree instead "
    "of Markdown.\n\n"
    f"{_NODE_SCHEMA_RULES}\n"
    "7. If the user's additional notes contain a questionnaire (a list of "
    "questions to answer), address every question explicitly and "
    "completely inside 'body', while still producing all six required "
    "sections normally.\n"
    "8. The 'presentation' section is REQUIRED and must exist, but it is "
    "NOT a summary or abstract of the document's topic. Its 'nodes' must "
    "restate ONLY the structured presentation data given to you below — "
    "student name, institution, subject/course, professor, student ID (if "
    "provided), and today's date — as separate 'paragraph' nodes (one "
    "field per paragraph), in the source's language, exactly as given. Do "
    "NOT add a summary of what the document is about, do NOT add a field "
    "that wasn't provided to you, and do NOT omit any field that was.\n"
    "9. The 'index' section is a short plain-language outline of what each "
    "section covers, as 'paragraph' nodes or a simple list — NEVER invent "
    "page numbers, since you have no way of knowing how the final document "
    "will paginate. The renderer builds the authoritative, paginated table "
    "of contents separately from the real headings; treat this section "
    "only as a narrative overview.\n"
    "You always answer with a single JSON object and nothing else — no "
    "markdown fences, no commentary, no preamble."
)

_AUGMENT_SYSTEM_INSTRUCTION = (
    "You are an academic writing assistant. You update an EXISTING APA 7 "
    "document (stored as a JSON node tree, not Markdown) with new source "
    "material, deciding per-section whether it needs to change.\n\n"
    f"{_NODE_SCHEMA_RULES}\n"
    "7. For every section, decide: if the new material doesn't affect it, "
    'return it with "unchanged": true and nothing else — do NOT repeat '
    "its old nodes, that wastes tokens. If it does, return the FULL "
    "updated 'title' and 'nodes' for that section.\n"
    "8. If the new material is a genuinely new subtopic not covered yet in "
    "'body', add it as a new 'heading-2' block followed by its 'paragraph' "
    "node(s), appended at a sensible point — don't just tack it onto an "
    "unrelated paragraph.\n"
    "9. If the new material complements or extends a topic already present "
    "in 'body', merge it into that existing paragraph/subtopic's node(s) "
    "instead of duplicating it as a separate block.\n"
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
    "one per paragraph node, never a summary of the document's topic.\n"
    "You always answer with a single JSON object and nothing else — no "
    "markdown fences, no commentary, no preamble."
)

_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)

_RESPONSE_SHAPE_HINT = """
{
  "title": "A short, original academic title you write yourself",
  "sections": [
    {"section_type": "presentation", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "index", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "introduction", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "body", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "conclusion", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "sources", "title": "...", "nodes": [ BLOCK, ... ]}
  ],
  "references": [
    {"author": "...", "year": "...", "title": "...", "url": "..."}
  ]
}
""".strip()

_AUGMENT_RESPONSE_SHAPE_HINT = """
{
  "title": "usually the same title as before, unless it must change",
  "sections": [
    {"section_type": "presentation", "unchanged": true},
    {"section_type": "index", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "introduction", "unchanged": true},
    {"section_type": "body", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "conclusion", "title": "...", "nodes": [ BLOCK, ... ]},
    {"section_type": "sources", "title": "...", "nodes": [ BLOCK, ... ]}
  ],
  "references": [
    {"author": "...", "year": "...", "title": "...", "url": "..."}
  ]
}
""".strip()


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

Presentation/cover page data — the 'presentation' section's nodes must
restate exactly these fields, one per paragraph, and nothing else: {presentation}

Respond with a single JSON object shaped exactly like this:
{_RESPONSE_SHAPE_HINT}

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
                    "nodes": [n.to_dict() for n in s.body_nodes],
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

Presentation/cover page data — the 'presentation' section's nodes must
restate exactly these fields, one per paragraph, and nothing else: {presentation}

User's additional notes for this update: {notes}

New source material to incorporate:
--- NEW MATERIAL START ---
{new_content}
--- NEW MATERIAL END ---

Respond with a single JSON object shaped exactly like this:
{_AUGMENT_RESPONSE_SHAPE_HINT}

Every section_type must appear exactly once, either as "unchanged": true
or with full "title"/"nodes". "references" must be the complete,
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

        sections = [self._build_section(s) for s in raw_sections]
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

            sections.append(self._build_section(s))

        references = self._parse_references(data)
        return title, sections, references

    def _build_section(self, raw: dict) -> APASection:
        try:
            section_type = APASectionType(raw["section_type"])
            title = self._validate_title(raw["title"], field="section title")
            raw_nodes = raw["nodes"]
        except (KeyError, ValueError) as exc:
            raise DocumentBuildError(
                f"Malformed section in Gemini response: {exc}"
            ) from exc

        if not raw_nodes:
            raise DocumentBuildError(
                f"Section '{section_type.value}' has no 'nodes'."
            )

        try:
            body_nodes = tuple(
                _with_replaced(
                    DocumentNode.from_dict(n), section_type=section_type.value
                )
                for n in raw_nodes
            )
        except DocumentBuildError as exc:
            raise DocumentBuildError(
                f"Malformed node in section '{section_type.value}': {exc}"
            ) from exc

        heading = DocumentNode(
            type=HEADING_1,
            section_type=section_type.value,
            children=(text_node(title),),
        )

        return APASection(
            section_type=section_type, heading=heading, body_nodes=body_nodes
        )

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
