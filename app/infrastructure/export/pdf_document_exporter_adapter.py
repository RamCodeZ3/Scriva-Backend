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
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from domain.entities.document import Document
from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASectionType

from application.dtos.export_result import ExportResult
from application.ports.document_exporter_port import DocumentExporterPort

_PAGE_SIZE = letter
_MARGIN = inch
_LEADING = 24


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

    def _build_sync(self, document: Document) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
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
        story += self._build_ai_section(document, APASectionType.PRESENTATION)
        story.append(PageBreak())
        story += self._build_ai_section(document, APASectionType.INDEX)
        story.append(PageBreak())

        for section_type in (
            APASectionType.INTRODUCTION,
            APASectionType.BODY,
            APASectionType.CONCLUSION,
        ):
            story += self._build_ai_section(document, section_type)

        story.append(PageBreak())
        story += self._build_references(document)

        doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
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
            Paragraph(document.title, styles["TitleCover"]),
            Spacer(1, 0.5 * inch),
        ]
        elements += [Paragraph(line, styles["CoverLine"]) for line in lines]
        return elements

    def _build_ai_section(self, document: Document, section_type: APASectionType) -> list:
        section = document.get_section(section_type)
        if section is None:
            return []

        elements: list = [Paragraph(section.title, self._styles["Heading1"])]
        for paragraph in _split_paragraphs(section.content):
            elements.append(Paragraph(paragraph, self._styles["Body"]))
        return elements

    def _build_references(self, document: Document) -> list:
        elements: list = [Paragraph("References", self._styles["Heading1"])]
        for ref in sorted(document.sources, key=lambda r: (r.author or "").lower()):
            elements.append(Paragraph(ref.to_apa_string(), self._styles["Reference"]))
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


def _split_paragraphs(content: str) -> list[str]:
    parts = [p.strip() for p in content.split("\n\n")]
    return [p for p in parts if p]


def _safe_filename(title: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]", "", title).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or "document"


def _write_file(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)
