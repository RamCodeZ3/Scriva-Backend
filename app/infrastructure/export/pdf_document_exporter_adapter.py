from __future__ import annotations

import asyncio
import re
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

from domain.entities.document import Document
from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASectionType

from application.dtos.export_result import ExportResult
from application.ports.document_exporter_port import DocumentExporterPort

_PAGE_SIZE = letter
_MARGIN = inch
_LEADING = 24

_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+[.)]\s+(.*)$")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_UNDERLINE_RE = re.compile(r"__(.+?)__")
SUBHEADING_TOKEN="## "


class _ApaDocTemplate(BaseDocTemplate):

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style_name = getattr(flowable.style, "name", "")
        if style_name == "Heading1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
        elif style_name == "Heading2":
            self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


class PdfDocumentExporterAdapter(DocumentExporterPort):
    def __init__(self) -> None:
        self._styles = _build_styles()

    async def export(self, document: Document) -> ExportResult:
        try:
            pdf_bytes = await asyncio.to_thread(self._build_sync, document)
        except Exception as exc:
            raise DocumentBuildError(f"PDF export failed: {exc}") from exc

        return ExportResult(
            url=None,
            file_bytes=pdf_bytes,
            file_name=f"{_safe_filename(document.title)}.pdf",
            content_type="application/pdf",
        )

    def _build_sync(self, document: Document) -> bytes:
        buffer = BytesIO()
        doc = _ApaDocTemplate(
            buffer,
            pagesize=_PAGE_SIZE,
            leftMargin=_MARGIN,
            rightMargin=_MARGIN,
            topMargin=_MARGIN,
            bottomMargin=_MARGIN,
            title=document.title,
        )
        frame = Frame(
            _MARGIN,
            _MARGIN,
            _PAGE_SIZE[0] - 2 * _MARGIN,
            _PAGE_SIZE[1] - 2 * _MARGIN,
            id="normal",
        )
        doc.addPageTemplates(
            [PageTemplate(id="all", frames=[frame], onPage=_draw_page_number)]
        )

        story: list = []
        story += self._build_cover_page(document)
        story.append(PageBreak())
        story += self._build_toc_page()
        story.append(PageBreak())

        for section_type in (
            APASectionType.INTRODUCTION,
            APASectionType.BODY,
            APASectionType.CONCLUSION,
        ):
            story += self._build_section(document, section_type)

        story.append(PageBreak())
        story += self._build_references(document)

        # multiBuild (not build): see _ApaDocTemplate docstring — this is
        # what lets the index show real, adapter-discovered page numbers.
        doc.multiBuild(story)
        return buffer.getvalue()

    def _build_cover_page(self, document: Document) -> list:
        p = document.presentation
        styles = self._styles

        lines = [p.student_name, p.display_institution(), p.display_subject(), p.professor]
        if p.student_id:
            lines.append(f"ID: {p.display_student_id()}")
        lines.append(date.today().strftime("%B %d, %Y"))

        elements: list = [
            Spacer(1, 2.5 * inch),
            Paragraph(_xml_escape(document.title), styles["TitleCover"]),
            Spacer(1, 0.5 * inch),
        ]
        elements += [Paragraph(_xml_escape(line), styles["CoverLine"]) for line in lines]
        return elements

    def _build_toc_page(self) -> list:
        toc = TableOfContents()
        toc.levelStyles = [self._styles["TOCLevel0"], self._styles["TOCLevel1"]]
        toc.dotsMinLevel = 0  # dot leaders on every level, not just sub-entries
        # "Heading1Plain" is intentionally NOT the "Heading1" style, so this
        # heading doesn't register itself as a TOC entry.
        return [Paragraph("Índice", self._styles["Heading1Plain"]), toc]

    def _build_section(self, document: Document, section_type: APASectionType) -> list:
        section = document.get_section(section_type)
        if section is None:
            return []

        elements: list = [
            Paragraph(_inline_markdown(section.title), self._styles["Heading1"])
        ]
        elements += _render_section_content(section.content, self._styles)
        return elements

    def _build_references(self, document: Document) -> list:
        elements: list = [Paragraph("References", self._styles["Heading1"])]
        for ref in sorted(document.sources, key=lambda r: (r.author or "").lower()):
            elements.append(
                Paragraph(_inline_markdown(ref.to_apa_string()), self._styles["Reference"])
            )
        if not document.sources:
            elements.append(Paragraph("No sources were provided.", self._styles["Body"]))
        return elements


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
        "Heading1": ParagraphStyle(
            "Heading1", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_CENTER, spaceBefore=12, spaceAfter=12,
        ),
            "Heading1Plain": ParagraphStyle(
            "Heading1Plain", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_CENTER, spaceBefore=12, spaceAfter=12,
        ),
        # APA 7 level-2 heading: flush left, bold, own line.
        "Heading2": ParagraphStyle(
            "Heading2", fontName="Times-Bold", fontSize=12, leading=_LEADING,
            alignment=TA_LEFT, spaceBefore=12, spaceAfter=6,
        ),
        "Body": ParagraphStyle(
            "Body", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_JUSTIFY, firstLineIndent=0.5 * inch,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_JUSTIFY, leftIndent=0.75 * inch, firstLineIndent=-0.25 * inch,
            spaceAfter=4,
        ),
        "Numbered": ParagraphStyle(
            "Numbered", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_JUSTIFY, leftIndent=0.75 * inch, firstLineIndent=-0.25 * inch,
            spaceAfter=4,
        ),
        "Reference": ParagraphStyle(
            "Reference", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            alignment=TA_LEFT, leftIndent=0.5 * inch, firstLineIndent=-0.5 * inch,
            spaceAfter=12,
        ),
        "TOCLevel0": ParagraphStyle(
            "TOCLevel0", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            leftIndent=0, firstLineIndent=0, spaceAfter=4,
        ),
        "TOCLevel1": ParagraphStyle(
            "TOCLevel1", fontName="Times-Roman", fontSize=12, leading=_LEADING,
            leftIndent=0.3 * inch, firstLineIndent=0, spaceAfter=4,
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


def _inline_markdown(text: str) -> str:
    """Converts the small Markdown subset the writer is allowed to use
    (**bold**, __underline__) into ReportLab's paragraph mini-XML, after
    escaping the raw text so user/AI content can never break the markup."""
    escaped = _xml_escape(text)
    escaped = _BOLD_RE.sub(lambda m: f"<b>{m.group(1)}</b>", escaped)
    escaped = _UNDERLINE_RE.sub(lambda m: f"<u>{m.group(1)}</u>", escaped)
    return escaped


def _render_section_content(content: str, styles: dict) -> list:
    
    elements: list = []
    lines = content.split("\n")
    buffer: list[str] = []
    i = 0

    def flush() -> None:
        if not buffer:
            return
        text = " ".join(s.strip() for s in buffer if s.strip())
        buffer.clear()
        if text:
            elements.append(Paragraph(_inline_markdown(text), styles["Body"]))

    while i < len(lines):
        line = lines[i].strip()

        if not line:
            flush()
            i += 1
            continue

        if line.startswith(SUBHEADING_TOKEN):
            flush()
            heading = line[len(SUBHEADING_TOKEN):].strip()
            elements.append(Paragraph(_inline_markdown(heading), styles["Heading2"]))
            i += 1
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            flush()
            while i < len(lines) and _BULLET_RE.match(lines[i].strip()):
                item_text = _BULLET_RE.match(lines[i].strip()).group(1)
                elements.append(
                    Paragraph(f"•  {_inline_markdown(item_text)}", styles["Bullet"])
                )
                i += 1
            continue

        numbered_match = _NUMBERED_RE.match(line)
        if numbered_match:
            flush()
            n = 1
            while i < len(lines) and _NUMBERED_RE.match(lines[i].strip()):
                item_text = _NUMBERED_RE.match(lines[i].strip()).group(1)
                elements.append(
                    Paragraph(f"{n}.  {_inline_markdown(item_text)}", styles["Numbered"])
                )
                n += 1
                i += 1
            continue

        buffer.append(line)
        i += 1

    flush()
    return elements


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]", "", title).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or "document"
