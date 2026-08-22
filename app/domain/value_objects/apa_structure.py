from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.value_objects.document_node import HEADING_1, DocumentNode


class APASectionType(Enum):
    """Canonical APA 7 section order."""

    PRESENTATION = "presentation"
    INDEX = "index"
    INTRODUCTION = "introduction"
    BODY = "body"
    CONCLUSION = "conclusion"
    SOURCES = "sources"

    @property
    def order(self) -> int:
        return {
            "PRESENTATION": 1,
            "INDEX": 2,
            "INTRODUCTION": 3,
            "BODY": 4,
            "CONCLUSION": 5,
            "SOURCES": 6,
        }[self.name]


APA7_DOCUMENT_STYLES: dict[str, str] = {
    "fontFamily": "Times New Roman, serif",
    "fontSize": "12pt",
}


@dataclass(frozen=True)
class APASection:
    """A logical APA section: its heading node plus the block nodes
    (paragraphs, subheadings, lists) that make up its body, in order."""

    section_type: APASectionType
    heading: DocumentNode
    body_nodes: tuple[DocumentNode, ...] = ()

    def __post_init__(self) -> None:
        if self.heading.type != HEADING_1:
            raise ValueError(
                f"Section '{self.section_type.value}' heading must be a "
                f"'{HEADING_1}' node."
            )
        if not self.heading.plain_text().strip():
            raise ValueError(
                f"Section '{self.section_type.value}' must have a title."
            )
        if not self.body_nodes:
            raise ValueError(
                f"Section '{self.section_type.value}' cannot be empty."
            )

    @property
    def title(self) -> str:
        return self.heading.plain_text()

    @property
    def nodes(self) -> tuple[DocumentNode, ...]:
        """Heading followed by body nodes, in document order."""
        return (self.heading,) + self.body_nodes
