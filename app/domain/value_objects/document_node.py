from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Sequence

from domain.exceptions import DocumentBuildError

HEADING_1 = "heading-1"
HEADING_2 = "heading-2"
PARAGRAPH = "paragraph"
BULLETED_LIST = "bulleted-list"
NUMBERED_LIST = "numbered-list"
LIST_ITEM = "list-item"

BLOCK_TYPES = frozenset(
    {HEADING_1, HEADING_2, PARAGRAPH, BULLETED_LIST, NUMBERED_LIST, LIST_ITEM}
)
LIST_TYPES = frozenset({BULLETED_LIST, NUMBERED_LIST})

MARK_BOLD = "bold"
MARK_UNDERLINE = "underline"
_VALID_MARKS = frozenset({MARK_BOLD, MARK_UNDERLINE})

_auto_id = itertools.count(1)


def _next_id() -> str:
    return f"node-{next(_auto_id)}"


@dataclass(frozen=True)
class DocumentNode:

    type: str | None = None
    text: str | None = None
    id: str | None = None
    section_type: str | None = None
    marks: tuple[str, ...] = ()
    children: tuple["DocumentNode", ...] = ()

    def __post_init__(self) -> None:
        is_leaf = self.text is not None
        is_block = self.type is not None

        if is_leaf == is_block:
            raise DocumentBuildError(
                "A document node must be either a leaf text node ('text') "
                "or a block node ('type'), never both or neither."
            )

        if is_leaf:
            if self.children:
                raise DocumentBuildError(
                    "A leaf text node cannot have 'children'."
                )
            bad_marks = set(self.marks) - _VALID_MARKS
            if bad_marks:
                raise DocumentBuildError(
                    f"Unknown text mark(s): {sorted(bad_marks)}"
                )
            return

        if self.type not in BLOCK_TYPES:
            raise DocumentBuildError(f"Unknown node type: {self.type!r}")
        if not self.children:
            raise DocumentBuildError(
                f"Block node '{self.type}' must have at least one child."
            )
        if self.marks:
            raise DocumentBuildError("Only leaf text nodes may carry 'marks'.")
        if self.type in LIST_TYPES:
            if any(c.type != LIST_ITEM for c in self.children):
                raise DocumentBuildError(
                    f"'{self.type}' children must all be '{LIST_ITEM}' nodes."
                )
        if self.type == LIST_ITEM:
            if any(c.text is None for c in self.children):
                raise DocumentBuildError(
                    "'list-item' children must all be leaf text nodes."
                )

    def plain_text(self) -> str:
        if self.text is not None:
            return self.text
        return "".join(c.plain_text() for c in self.children)

    def to_dict(self) -> dict[str, Any]:
        if self.text is not None:
            out: dict[str, Any] = {"text": self.text}
            if self.marks:
                out["marks"] = list(self.marks)
            return out

        out = {
            "type": self.type,
            "children": [c.to_dict() for c in self.children],
        }
        if self.id:
            out["id"] = self.id
        if self.section_type:
            out["section_type"] = self.section_type
        return out

    @classmethod
    def from_dict(cls, data: Any, *, assign_ids: bool = True) -> "DocumentNode":
        if not isinstance(data, dict):
            raise DocumentBuildError(f"Node must be a JSON object, got: {data!r}")

        if "text" in data:
            text = data["text"]
            if not isinstance(text, str):
                raise DocumentBuildError(
                    f"Leaf 'text' must be a string, got: {text!r}"
                )
            raw_marks = data.get("marks") or []
            return cls(text=text, marks=tuple(raw_marks))

        node_type = data.get("type")
        raw_children = data.get("children")
        if not raw_children:
            raise DocumentBuildError(
                f"Block node '{node_type}' is missing 'children'."
            )

        children = tuple(
            cls.from_dict(c, assign_ids=assign_ids) for c in raw_children
        )
        node_id = data.get("id") or (_next_id() if assign_ids else None)
        return cls(
            type=node_type,
            id=node_id,
            section_type=data.get("section_type"),
            children=children,
        )


def text_node(
    text: str, *, bold: bool = False, underline: bool = False
) -> DocumentNode:
    marks: list[str] = []
    if bold:
        marks.append(MARK_BOLD)
    if underline:
        marks.append(MARK_UNDERLINE)
    return DocumentNode(text=text, marks=tuple(marks))


def block_node(
    node_type: str,
    children: Sequence[DocumentNode],
    *,
    section_type: str | None = None,
    node_id: str | None = None,
) -> DocumentNode:
    return DocumentNode(
        type=node_type,
        children=tuple(children),
        section_type=section_type,
        id=node_id or _next_id(),
    )
