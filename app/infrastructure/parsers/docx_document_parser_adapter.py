from __future__ import annotations

import asyncio
from io import BytesIO

from application.ports.document_parser_port import DocumentParserPort
from docx import Document as DocxDocument
from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_node import (
    HEADING_1,
    HEADING_2,
    HEADING_3,
    PARAGRAPH,
    TABLE,
    TABLE_CELL,
    TABLE_ROW,
    DocumentNode,
    Mark,
)

_SECTION_ATTR = "{urn:scriva:document}section-type"


class DocxDocumentParserAdapter(DocumentParserPort):
    async def parse(self, content: bytes) -> list[APASection]:
        if not content:
            raise DocumentBuildError("The uploaded DOCX file is empty.")
        try:
            return await asyncio.to_thread(self._parse_sync, content)
        except DocumentBuildError:
            raise
        except Exception as exc:
            raise DocumentBuildError(f"DOCX parsing failed: {exc}") from exc

    def _parse_sync(self, content: bytes) -> list[APASection]:
        docx = DocxDocument(BytesIO(content))
        blocks = list(_iter_blocks(docx))
        sections: list[APASection] = []
        current_type: APASectionType | None = None
        heading: DocumentNode | None = None
        body: list[DocumentNode] = []

        def flush() -> None:
            nonlocal body
            if heading is not None and current_type is not None:
                if not body:
                    body = [_paragraph("")]
                sections.append(APASection(current_type, heading, tuple(body)))

        for kind, item in blocks:
            marked_type = _marked_section_type(item)
            if marked_type is not None and marked_type != current_type:
                flush()
                current_type = marked_type
                heading_text = (
                    "Desarrollo"
                    if marked_type is APASectionType.BODY
                    else (
                        item.text.strip()
                        if kind == "paragraph" and item.text.strip()
                        else marked_type.value.replace("_", " ").title()
                    )
                )
                heading = _block(
                    HEADING_1,
                    heading_text,
                    section_type=marked_type.value,
                )
                body = []
                # A BODY marker is attached to its first real content block.
                if marked_type is not APASectionType.BODY:
                    continue
            if kind == "table":
                if heading is not None:
                    body.append(_table_node(item))
                continue
            paragraph = item
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style else ""
            detected = _section_type(text, style, current_type)
            if detected is not None:
                flush()
                current_type = detected
                heading = _block(HEADING_1, text, section_type=detected.value)
                body = []
                continue
            if heading is None:
                # Content before the first semantic heading is the cover.
                current_type = APASectionType.PRESENTATION
                heading = _block(
                    HEADING_1,
                    "Presentación",
                    section_type=current_type.value,
                )
            body.append(_paragraph_node(paragraph, style))

        flush()
        if not sections:
            raise DocumentBuildError("The DOCX has no readable content.")
        return sections


def _section_type(
    text: str, style: str, current: APASectionType | None
) -> APASectionType | None:
    normalized = text.casefold()
    names = {
        "presentación": APASectionType.PRESENTATION,
        "presentation": APASectionType.PRESENTATION,
        "índice": APASectionType.INDEX,
        "index": APASectionType.INDEX,
        "table of contents": APASectionType.INDEX,
        "introducción": APASectionType.INTRODUCTION,
        "introduction": APASectionType.INTRODUCTION,
        "conclusión": APASectionType.CONCLUSION,
        "conclusion": APASectionType.CONCLUSION,
        "referencias": APASectionType.SOURCES,
        "references": APASectionType.SOURCES,
        "fuentes": APASectionType.SOURCES,
    }
    is_heading = style in {
        "Heading1",
        "Heading 1",
        "APA Heading 1",
        "APA Heading 1 Plain",
    }
    if normalized in names and is_heading:
        return names[normalized]
    if is_heading:
        return (
            APASectionType.BODY
            if current is not None
            else APASectionType.INTRODUCTION
        )
    return None


def _paragraph_node(paragraph, style: str) -> DocumentNode:
    node_type = PARAGRAPH
    if style in {"Heading2", "Heading 2", "APA Heading 2"}:
        node_type = HEADING_2
    elif style in {"Heading3", "Heading 3", "APA Heading 3"}:
        node_type = HEADING_3
    return DocumentNode(type=node_type, children=tuple(_runs(paragraph)))


def _runs(paragraph) -> list[DocumentNode]:
    nodes: list[DocumentNode] = []
    for run in paragraph.runs:
        if not run.text:
            continue
        marks: list[Mark] = []
        if run.bold:
            marks.append(Mark("bold"))
        if run.italic:
            marks.append(Mark("italic"))
        if run.underline:
            marks.append(Mark("underline"))
        nodes.append(DocumentNode(text=run.text, marks=tuple(marks)))
    return nodes or [DocumentNode(text=paragraph.text or " ")]


def _block(
    type_: str, text: str, section_type: str | None = None
) -> DocumentNode:
    return DocumentNode(
        type=type_,
        section_type=section_type,
        children=(DocumentNode(text=text),),
    )


def _paragraph(text: str) -> DocumentNode:
    return _block(PARAGRAPH, text or " ")


def _table_node(table) -> DocumentNode:
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            paragraphs = tuple(
                _paragraph(p.text) for p in cell.paragraphs if p.text.strip()
            )
            cells.append(
                DocumentNode(
                    type=TABLE_CELL, children=paragraphs or (_paragraph(" "),)
                )
            )
        rows.append(DocumentNode(type=TABLE_ROW, children=tuple(cells)))
    return DocumentNode(type=TABLE, children=tuple(rows))


def _iter_blocks(document):
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield "paragraph", Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield "table", Table(child, document)


def _marked_section_type(item) -> APASectionType | None:
    element = getattr(item, "_p", None)
    if element is None:
        element = getattr(item, "_tbl", None)
    value = element.get(_SECTION_ATTR) if element is not None else None
    if value is None:
        return None
    try:
        return APASectionType(value)
    except ValueError:
        return None
