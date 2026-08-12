from __future__ import annotations

import asyncio
import os
import re
from datetime import date
from io import BytesIO

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

from domain.entities.document import Document
from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASectionType

from application.dtos.export_result import ExportResult
from application.ports.document_exporter_port import DocumentExporterPort

_PAGE_SIZE = letter
_MARGIN = inch  # APA 7: 1 inch on every side
_LEADING = 24   # 12pt font, double-spaced (2 x 12)

# Must match the GeminiDocumentWriterAdapter's `_SUBHEADING_TOKEN`. A line
# starting with this token inside a section's `content` marks an APA
# level-2 subheading. This is the ONLY markup the AI is instructed to
# produce; everything else below is defensive cleanup for anything that
# slips through anyway (the model does not always follow instructions).
_SUBHEADING_TOKEN = "## "

# Defensive Markdown/HTML stripping. `content` is meant to be plain prose,
# but LLMs habitually emit Markdown regardless of instructions, and
# reportlab's Paragraph renders literal "###", "**", etc. as-is instead of
# formatting them — that literal leakage was the actual visible bug.
_MD_ATX_HEADING_RE = re.compile(r"^#{1,6}\s*")
_MD_STRAY_HASHES_RE = re.compile(r"#{2,6}")
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)")
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MD_BULLET_RE = re.compile(r"^[\-\*\u2022]\s+")
_MD_NUMBERED_RE = re.compile(r"^\d+[.)]\s+")


class PdfDocumentExporterAdapter(DocumentExporterPort):
    
    def __init__(self, storage_dir: str = "storage/documents") -> None:
        self._storage_dir = storage_dir
        os.makedirs(self._storage_dir, exist_ok=True)
        self._styles = _build_styles()

    async def export(self, document: Document) -> ExportResult:
        try:
            pdf_bytes = await asyncio.to_thread(self._build_sync, document)
        except Exception as exc:
            raise DocumentBuildError(f"PDF export failed: {exc}") from exc

        file_name = f"{_safe_filename(document.title)}.pdf"
        storage_path = os.path.join(self._storage_dir, f"{document.id}.pdf")
        await asyncio.to_thread(_write_file, storage_path, pdf_bytes)

        return ExportResult(
            url=None,
            file_bytes=pdf_bytes,
            file_name=file_name,
            content_type="application/pdf",
            storage_path=storage_path,
        )

    # ── Document build (runs in a worker thread — reportlab is sync) ───────

    def _build_sync(self, document: Document) -> bytes:
        buffer = BytesIO()
        doc = _TocAwareDocTemplate(
            buffer,
            pagesize=_PAGE_SIZE,
            leftMargin=_MARGIN,
            rightMargin=_MARGIN,
            topMargin=_MARGIN,
            bottomMargin=_MARGIN,
            title=document.title,
        )

        story: list = []
        story += self._build_cover_page(document)
        story.append(PageBreak())
        story += self._build_index_page()
        story.append(PageBreak())

        for section_type in (
            APASectionType.INTRODUCTION,
            APASectionType.BODY,
            APASectionType.CONCLUSION,
        ):
            story += self._build_ai_section(document, section_type)

        story.append(PageBreak())
        story += self._build_references(document)

        # multiBuild (instead of build) makes the pass needed to resolve
        # real page numbers for the table of contents before the final
        # render.
        doc.multiBuild(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
        return buffer.getvalue()

    def _build_cover_page(self, document: Document) -> list:
        p = document.presentation
        styles = self._styles

        lines = [p.student_name, p.display_institution(), p.subject, p.professor]
        if p.student_id:
            lines.append(f"ID: {p.display_student_id()}")
        lines.append(date.today().strftime("%B %d, %Y"))

        elements: list = [
            Spacer(1, 2.5 * inch),
            Paragraph(_escape(document.title), styles["TitleCover"]),
            Spacer(1, 0.5 * inch),
        ]
        elements += [Paragraph(_escape(line), styles["CoverLine"]) for line in lines]
        return elements

    def _build_index_page(self) -> list:
        toc = TableOfContents()
        toc.dotsMinLevel = 0
        toc.levelStyles = [
            ParagraphStyle(
                "TOCLevel1", fontName="Times-Roman", fontSize=12, leading=_LEADING,
                leftIndent=0, firstLineIndent=0,
            ),
            ParagraphStyle(
                "TOCLevel2", fontName="Times-Roman", fontSize=12, leading=_LEADING,
                leftIndent=0.35 * inch, firstLineIndent=0,
            ),
        ]
        return [
            Paragraph("Índice", self._styles["IndexTitle"]),
            Spacer(1, 0.2 * inch),
            toc,
        ]

    def _build_ai_section(self, document: Document, section_type: APASectionType) -> list:
        section = document.get_section(section_type)
        if section is None:
            # Document.complete() guarantees these are all present, but
            # stay defensive rather than let a bad state raise deep
            # inside a background export step.
            return []

        elements: list = [
            Paragraph(_escape(_clean_markdown(section.title)), self._styles["Heading1"])
        ]
        for block_type, text in _parse_content_blocks(section.content):
            style = self._styles["Heading2"] if block_type == "heading" else self._styles["Body"]
            elements.append(Paragraph(_escape(text), style))
        return elements

    def _build_references(self, document: Document) -> list:
        elements: list = [Paragraph("References", self._styles["Heading1"])]
        for ref in sorted(document.sources, key=lambda r: (r.author or "").lower()):
            elements.append(Paragraph(_escape(ref.to_apa_string()), self._styles["Reference"]))
        if not document.sources:
            elements.append(Paragraph("No sources were provided.", self._styles["Body"]))
        return elements


class _TocAwareDocTemplate(SimpleDocTemplate):
    """
    A SimpleDocTemplate that feeds every level-1/level-2 heading it lays
    out into the document's TableOfContents flowable, so the index shows
    real page numbers instead of a hand-typed listing. Must be built with
    `multiBuild`, not `build`, so headings can be collected on an earlier
    pass before the table of contents itself is drawn.
    """

    def afterFlowable(self, flowable) -> None:
        if not isinstance(flowable, Paragraph):
            return
        style_name = getattr(flowable.style, "name", "")
        if style_name == "Heading1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
        elif style_name == "Heading2":
            self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


def _build_styles() -> dict[str, ParagraphStyle]:
    return {
        "TitleCover": ParagraphStyle(
            "TitleCover", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_CENTER,
        ),
        "CoverLine": ParagraphStyle(
            "CoverLine", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_CENTER,
        ),
        "IndexTitle": ParagraphStyle(
            # Deliberately NOT named "Heading1"/"Heading2" so it is never
            # picked up as a table-of-contents entry for itself.
            "IndexTitle", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_CENTER,
        ),
        # APA 7 level 1: centered, bold.
        "Heading1": ParagraphStyle(
            "Heading1", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_CENTER, spaceBefore=12, spaceAfter=12,
        ),
        # APA 7 level 2: left-aligned, bold.
        "Heading2": ParagraphStyle(
            "Heading2", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_LEFT, spaceBefore=12, spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "Body", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_JUSTIFY, firstLineIndent=0.5 * inch,
        ),
        "Reference": ParagraphStyle(
            "Reference", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_LEFT, leftIndent=0.5 * inch, firstLineIndent=-0.5 * inch,
            spaceAfter=12,
        ),
    }


def _draw_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 12)
    page_num = canvas.getPageNumber()
    canvas.drawRightString(
        _PAGE_SIZE[0] - _MARGIN, _PAGE_SIZE[1] - 0.75 * inch, str(page_num)
    )
    canvas.restoreState()


def _parse_content_blocks(content: str) -> list[tuple[str, str]]:
    
    blocks: list[tuple[str, str]] = []
    for chunk in content.split("\n\n"):
        lines = [line.strip() for line in chunk.strip().splitlines() if line.strip()]
        if not lines:
            continue

        paragraph_lines: list[str] = []
        for line in lines:
            if line.startswith(_SUBHEADING_TOKEN):
                if paragraph_lines:
                    blocks.append(("paragraph", " ".join(paragraph_lines)))
                    paragraph_lines = []
                heading_text = _clean_markdown(line[len(_SUBHEADING_TOKEN):])
                if heading_text:
                    blocks.append(("heading", heading_text))
            else:
               
                cleaned = _clean_markdown(line)
                if cleaned:
                    paragraph_lines.append(cleaned)
        if paragraph_lines:
            blocks.append(("paragraph", " ".join(paragraph_lines)))

    return blocks


def _clean_markdown(text: str) -> str:
    text = _MD_ATX_HEADING_RE.sub("", text)
    text = _MD_BULLET_RE.sub("", text)
    text = _MD_NUMBERED_RE.sub("", text)
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    text = _MD_INLINE_CODE_RE.sub(r"\1", text)
    text = _MD_STRAY_HASHES_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _escape(text: str) -> str:
    """reportlab's Paragraph interprets a small XML/HTML subset, so any
    literal '&', '<', '>' in AI-generated or reference text (e.g.
    "Smith & Jones") must be escaped or it can break rendering."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]", "", title).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or "document"


def _write_file(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
