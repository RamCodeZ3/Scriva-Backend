from __future__ import annotations

import unittest
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from docx import Document as ReadDocx
from domain.entities.document import Document, DocumentStatus
from domain.services.table_of_contents_builder import build_index_section
from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_node import (
    HEADING_1,
    HEADING_2,
    PARAGRAPH,
    DocumentNode,
    page_break_node,
    text_node,
)
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from infrastructure.export.docx_document_exporter_adapter import (
    DocxDocumentExporterAdapter,
)
from infrastructure.export.pdf_document_exporter_adapter import (
    PdfDocumentExporterAdapter,
)


class ExportTableOfContentsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _document_fixture()

    def test_pdf_layout_exposes_resolved_toc_entries(self) -> None:
        entries = PdfDocumentExporterAdapter().build_toc_entries(self.document)

        self.assertIn("Introducción", _entry_titles(entries))
        self.assertIn("Tema principal", _entry_titles(entries))
        self.assertTrue(all(page_number > 0 for _, _, page_number in entries))
        self.assertIn((1, "Tema principal"), _entry_levels(entries))

    def test_docx_contains_visible_updateable_toc_on_first_render(
        self,
    ) -> None:
        content = DocxDocumentExporterAdapter()._build_sync(self.document)

        with ZipFile(BytesIO(content)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")

        self.assertIn('TOC \\o "1-2"', document_xml)
        self.assertIn('w:dirty="true"', document_xml)
        self.assertNotIn("Actualizar campos", document_xml)

        parsed = ReadDocx(BytesIO(content))
        visible_text = "\n".join(
            paragraph.text for paragraph in parsed.paragraphs
        )
        self.assertIn("Introducción", visible_text)
        self.assertIn("Tema principal", visible_text)


def _entry_titles(entries: list[tuple[int, str, int]]) -> set[str]:
    return {title for _, title, _ in entries}


def _entry_levels(entries: list[tuple[int, str, int]]) -> set[tuple[int, str]]:
    return {(level, title) for level, title, _ in entries}


def _document_fixture() -> Document:
    paragraph = _block(PARAGRAPH, "Document content " * 80)
    subheading = _block(HEADING_2, "Tema principal")
    sections = [
        _section(
            APASectionType.PRESENTATION,
            "Presentación",
            (_block(PARAGRAPH, "Student"), page_break_node()),
        ),
        build_index_section(),
        _section(
            APASectionType.INTRODUCTION,
            "Introducción",
            (paragraph,),
        ),
        _section(
            APASectionType.BODY,
            "Desarrollo",
            (subheading, paragraph),
        ),
        _section(
            APASectionType.CONCLUSION,
            "Conclusión",
            (paragraph, page_break_node()),
        ),
        _section(
            APASectionType.SOURCES,
            "Referencias",
            (_block(PARAGRAPH, "Source placeholder"),),
        ),
    ]
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        user_id=uuid4(),
        title="TOC test",
        document_type=DocumentType.REPORT,
        raw_sources=[],
        presentation=PresentationInfo("Student", "Professor"),
        status=DocumentStatus.DONE,
        sections=sections,
        sources=[],
        created_at=now,
        updated_at=now,
    )


def _section(
    section_type: APASectionType,
    title: str,
    body: tuple[DocumentNode, ...],
) -> APASection:
    return APASection(
        section_type=section_type,
        heading=_block(HEADING_1, title),
        body_nodes=body,
    )


def _block(node_type: str, text: str) -> DocumentNode:
    return DocumentNode(type=node_type, children=(text_node(text),))


if __name__ == "__main__":
    unittest.main()
