from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Sequence

from domain.exceptions import DocumentBuildError

HEADING_1 = "heading-1"
HEADING_2 = "heading-2"
HEADING_3 = "heading-3"
HEADING_4 = "heading-4"
HEADING_5 = "heading-5"
PARAGRAPH = "paragraph"
BLOCK_QUOTE = "block-quote"
BULLETED_LIST = "bulleted-list"
NUMBERED_LIST = "numbered-list"
LIST_ITEM = "list-item"
IMAGE = "image"

HEADING_TYPES = frozenset(
    {HEADING_1, HEADING_2, HEADING_3, HEADING_4, HEADING_5}
)
LIST_TYPES = frozenset({BULLETED_LIST, NUMBERED_LIST})
# Every block type except "image" is a normal container: it must have
# `children` and may carry `styles`.
CONTAINER_BLOCK_TYPES = HEADING_TYPES | {
    PARAGRAPH,
    BLOCK_QUOTE,
    BULLETED_LIST,
    NUMBERED_LIST,
    LIST_ITEM,
}
BLOCK_TYPES = CONTAINER_BLOCK_TYPES | {IMAGE}

MARK_BOLD = "bold"
MARK_ITALIC = "italic"
MARK_UNDERLINE = "underline"
MARK_STRIKETHROUGH = "strikethrough"
MARK_SCRIPT = "script"
MARK_COLOR = "color"
MARK_HIGHLIGHT = "highlight"
MARK_FONT_FAMILY = "fontFamily"
MARK_FONT_SIZE = "fontSize"
MARK_LINK = "link"
MARK_CODE = "code"

_VALID_MARK_TYPES = frozenset(
    {
        MARK_BOLD,
        MARK_ITALIC,
        MARK_UNDERLINE,
        MARK_STRIKETHROUGH,
        MARK_SCRIPT,
        MARK_COLOR,
        MARK_HIGHLIGHT,
        MARK_FONT_FAMILY,
        MARK_FONT_SIZE,
        MARK_LINK,
        MARK_CODE,
    }
)
# These marks are meaningless without a 'value' (a color, a size, a URL...).
_MARKS_REQUIRING_VALUE = frozenset(
    {
        MARK_SCRIPT,
        MARK_COLOR,
        MARK_HIGHLIGHT,
        MARK_FONT_FAMILY,
        MARK_FONT_SIZE,
        MARK_LINK,
    }
)
_SCRIPT_VALUES = frozenset({"superscript", "subscript"})

_auto_id = itertools.count(1)


def _next_id() -> str:
    return f"node-{next(_auto_id)}"


@dataclass(frozen=True)
class Mark:
    type: str
    value: Any = None

    def __post_init__(self) -> None:
        if self.type not in _VALID_MARK_TYPES:
            raise DocumentBuildError(f"Unknown mark type: {self.type!r}")
        if self.type in _MARKS_REQUIRING_VALUE and self.value is None:
            raise DocumentBuildError(f"Mark '{self.type}' requires a 'value'.")
        if self.type == MARK_SCRIPT and self.value not in _SCRIPT_VALUES:
            raise DocumentBuildError(
                f"'script' mark value must be one of {sorted(_SCRIPT_VALUES)}, "
                f"got: {self.value!r}"
            )
        if self.type == MARK_LINK and not (
            isinstance(self.value, dict) and self.value.get("url")
        ):
            raise DocumentBuildError(
                f"'link' mark value must be an object with a 'url', got: "
                f"{self.value!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type}
        if self.value is not None:
            out["value"] = self.value
        return out

    @classmethod
    def from_dict(cls, data: Any) -> "Mark":
        if isinstance(data, str):
            # Back-compat: accept a bare mark name ("bold") as shorthand
            # for {"type": "bold"}.
            return cls(type=data)
        if not isinstance(data, dict) or "type" not in data:
            raise DocumentBuildError(f"Malformed mark: {data!r}")
        return cls(type=data["type"], value=data.get("value"))


@dataclass(frozen=True)
class DocumentNode:
    type: str | None = None
    text: str | None = None
    id: str | None = None
    section_type: str | None = None
    marks: tuple[Mark, ...] = ()
    children: tuple["DocumentNode", ...] = ()
    styles: dict[str, Any] = field(default_factory=dict)
    src: str | None = None
    alt: str | None = None
    caption: str | None = None

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
            if self.styles:
                raise DocumentBuildError(
                    "A leaf text node cannot have 'styles' — use 'marks'."
                )
            if self.src or self.alt or self.caption:
                raise DocumentBuildError(
                    "'src'/'alt'/'caption' only apply to 'image' nodes."
                )
            return

        if self.type not in BLOCK_TYPES:
            raise DocumentBuildError(f"Unknown node type: {self.type!r}")
        if self.marks:
            raise DocumentBuildError("Only leaf text nodes may carry 'marks'.")
        if not isinstance(self.styles, dict):
            raise DocumentBuildError("'styles' must be a JSON object.")

        if self.type == IMAGE:
            if self.children:
                raise DocumentBuildError(
                    "An 'image' node cannot have 'children'."
                )
            if not self.src:
                raise DocumentBuildError("An 'image' node requires 'src'.")
            return

        if self.src or self.alt or self.caption:
            raise DocumentBuildError(
                "'src'/'alt'/'caption' only apply to 'image' nodes."
            )
        if not self.children:
            raise DocumentBuildError(
                f"Block node '{self.type}' must have at least one child."
            )
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
        if self.type == IMAGE:
            return self.caption or self.alt or ""
        return "".join(c.plain_text() for c in self.children)

    def to_dict(self) -> dict[str, Any]:
        if self.text is not None:
            out: dict[str, Any] = {"text": self.text}
            if self.marks:
                out["marks"] = [m.to_dict() for m in self.marks]
            return out

        out: dict[str, Any] = {"type": self.type}
        if self.id:
            out["id"] = self.id
        if self.section_type:
            out["section_type"] = self.section_type
        if self.styles:
            out["styles"] = dict(self.styles)

        if self.type == IMAGE:
            out["src"] = self.src
            if self.alt:
                out["alt"] = self.alt
            if self.caption:
                out["caption"] = self.caption
            return out

        out["children"] = [c.to_dict() for c in self.children]
        return out

    @classmethod
    def from_dict(
        cls, data: Any, *, assign_ids: bool = True
    ) -> "DocumentNode":
        if not isinstance(data, dict):
            raise DocumentBuildError(
                f"Node must be a JSON object, got: {data!r}"
            )

        if "text" in data:
            text = data["text"]
            if not isinstance(text, str):
                raise DocumentBuildError(
                    f"Leaf 'text' must be a string, got: {text!r}"
                )
            marks = tuple(Mark.from_dict(m) for m in (data.get("marks") or ()))
            return cls(text=text, marks=marks)

        node_type = data.get("type")
        node_id = data.get("id") or (_next_id() if assign_ids else None)
        styles = data.get("styles") or {}
        if not isinstance(styles, dict):
            raise DocumentBuildError(
                f"'styles' must be a JSON object, got: {styles!r}"
            )

        if node_type == IMAGE:
            return cls(
                type=node_type,
                id=node_id,
                section_type=data.get("section_type"),
                styles=styles,
                src=data.get("src"),
                alt=data.get("alt"),
                caption=data.get("caption"),
            )

        raw_children = data.get("children")
        if not raw_children:
            raise DocumentBuildError(
                f"Block node '{node_type}' is missing 'children'."
            )
        children = tuple(
            cls.from_dict(c, assign_ids=assign_ids) for c in raw_children
        )
        return cls(
            type=node_type,
            id=node_id,
            section_type=data.get("section_type"),
            styles=styles,
            children=children,
        )


def text_node(
    text: str, *, marks: Sequence[Mark | str] | None = None
) -> DocumentNode:
    resolved: tuple[Mark, ...] = ()
    if marks:
        resolved = tuple(
            m if isinstance(m, Mark) else Mark(type=m) for m in marks
        )
    return DocumentNode(text=text, marks=resolved)


def block_node(
    node_type: str,
    children: Sequence[DocumentNode],
    *,
    section_type: str | None = None,
    node_id: str | None = None,
    styles: dict[str, Any] | None = None,
) -> DocumentNode:
    return DocumentNode(
        type=node_type,
        children=tuple(children),
        section_type=section_type,
        id=node_id or _next_id(),
        styles=dict(styles or {}),
    )


def image_node(
    src: str,
    *,
    alt: str | None = None,
    caption: str | None = None,
    section_type: str | None = None,
    node_id: str | None = None,
    styles: dict[str, Any] | None = None,
) -> DocumentNode:
    return DocumentNode(
        type=IMAGE,
        id=node_id or _next_id(),
        section_type=section_type,
        styles=dict(styles or {}),
        src=src,
        alt=alt,
        caption=caption,
    )
