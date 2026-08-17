from dataclasses import dataclass
from enum import Enum


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


@dataclass(frozen=True)
class APASection:
    section_type: APASectionType
    title: str
    content: str

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError(
                f"Section '{self.section_type.value}' must have a title."
            )
        if not self.content.strip():
            raise ValueError(
                f"Section '{self.section_type.value}' cannot be empty."
            )
