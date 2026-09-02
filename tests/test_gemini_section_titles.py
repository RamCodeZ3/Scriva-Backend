from __future__ import annotations

import unittest

from domain.exceptions import DocumentBuildError
from domain.value_objects.apa_structure import APASectionType
from infrastructure.ai.gemini_document_writer_adapter import (
    GeminiDocumentWriterAdapter,
)


class GeminiSectionTitleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = object.__new__(GeminiDocumentWriterAdapter)

    def test_preserves_content_specific_introduction_title(self) -> None:
        section = self.adapter._build_section(
            _raw_introduction("Retos éticos de la inteligencia artificial"),
            introduction_fallback="Inteligencia artificial y sociedad",
        )

        self.assertEqual(section.section_type, APASectionType.INTRODUCTION)
        self.assertEqual(
            section.title,
            "Retos éticos de la inteligencia artificial",
        )

    def test_replaces_generic_introduction_with_document_title(self) -> None:
        section = self.adapter._build_section(
            _raw_introduction("Introducción"),
            introduction_fallback="Inteligencia artificial y sociedad",
        )

        self.assertEqual(section.title, "Inteligencia artificial y sociedad")

    def test_rejects_generic_title_without_specific_fallback(self) -> None:
        with self.assertRaises(DocumentBuildError):
            self.adapter._build_section(
                _raw_introduction("Introduction"),
                introduction_fallback="Introducción",
            )


def _raw_introduction(title: str) -> dict:
    return {
        "section_type": "introduction",
        "title": title,
        "nodes": [
            {
                "type": "paragraph",
                "styles": {"textAlign": "justify"},
                "children": [{"text": "Contenido introductorio."}],
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
