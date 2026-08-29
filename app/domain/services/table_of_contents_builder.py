from __future__ import annotations

from domain.value_objects.apa_structure import APASection, APASectionType
from domain.value_objects.document_node import (
    HEADING_2,
    DocumentNode,
    page_break_node,
    table_of_contents_node,
    text_node,
)
from domain.value_objects.document_node import HEADING_1 as _HEADING_1

_DEFAULT_INDEX_TITLE = "Índice"

# The index never lists itself or the presentation cover page.
_EXCLUDED_FROM_TOC = frozenset(
    {APASectionType.PRESENTATION, APASectionType.INDEX}
)


def build_index_section(
    sections: list[APASection], *, title: str = _DEFAULT_INDEX_TITLE
) -> APASection:
    """Builds a fresh 'index' APASection from `sections`' own headings.

    `sections` must NOT include a prior 'index' entry — callers are
    expected to filter it out first (the index is always rebuilt, never
    patched), which also means this function is naturally idempotent.
    """
    entries = _collect_entries(sections)

    heading = DocumentNode(
        type=_HEADING_1,
        section_type=APASectionType.INDEX.value,
        children=(text_node(title),),
    )
    toc_node = table_of_contents_node(
        entries=entries, section_type=APASectionType.INDEX.value
    )
    break_node = page_break_node(section_type=APASectionType.INDEX.value)
    return APASection(
        section_type=APASectionType.INDEX,
        heading=heading,
        body_nodes=(toc_node, break_node),
    )


def _collect_entries(sections: list[APASection]) -> list[dict]:
    entries: list[dict] = []
    for section in sections:
        if section.section_type in _EXCLUDED_FROM_TOC:
            continue
        entries.append({"level": 0, "text": section.title})
        for node in section.body_nodes:
            entries.extend(_collect_heading_2_entries(node))
    return entries


def _collect_heading_2_entries(node: DocumentNode) -> list[dict]:
    """heading-2 nodes are flat blocks in this schema — they never nest
    other headings inside them — so a single top-level pass over each
    section's body_nodes is enough; no need to recurse into children."""
    if node.type == HEADING_2:
        return [{"level": 1, "text": node.plain_text()}]
    return []
