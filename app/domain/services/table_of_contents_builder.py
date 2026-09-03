from __future__ import annotations

from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_node import (
    DocumentNode,
    page_break_node,
    table_of_contents_node,
    text_node,
)
from domain.value_objects.document_node import HEADING_1 as _HEADING_1

_DEFAULT_INDEX_TITLE = "Índice"


def build_index_section(*, title: str = _DEFAULT_INDEX_TITLE) -> APASection:
    """Builds the (always identical in shape) 'index' APASection: a
    heading, a 'table-of-contents' placeholder, and a trailing
    'page-break' so 'introduction' always starts on a fresh page."""
    heading = DocumentNode(
        type=_HEADING_1,
        section_type=APASectionType.INDEX.value,
        children=(text_node(title),),
    )
    toc_node = table_of_contents_node(section_type=APASectionType.INDEX.value)
    break_node = page_break_node(section_type=APASectionType.INDEX.value)
    return APASection(
        section_type=APASectionType.INDEX,
        heading=heading,
        body_nodes=(toc_node, break_node),
    )
