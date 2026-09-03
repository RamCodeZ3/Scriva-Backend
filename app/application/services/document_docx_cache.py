from __future__ import annotations

import asyncio

from domain.entities.document import Document

from application.ports.docx_cache_port import DocxCachePort


def document_hash(cache: DocxCachePort, document: Document) -> str:
    return cache.compute_hash(document.to_node_tree())


async def get_cached_docx(
    cache: DocxCachePort, document: Document
) -> bytes | None:
    return await asyncio.to_thread(
        cache.get_docx,
        str(document.id),
        document_hash(cache, document),
    )


async def cache_docx(
    cache: DocxCachePort,
    document: Document,
    docx_bytes: bytes,
    *,
    invalidate_existing: bool = False,
) -> None:
    if invalidate_existing:
        await asyncio.to_thread(cache.invalidate_doc, str(document.id))
    await asyncio.to_thread(
        cache.set_docx,
        str(document.id),
        document_hash(cache, document),
        docx_bytes,
    )


async def invalidate_cached_docx(
    cache: DocxCachePort, document_id: str
) -> None:
    await asyncio.to_thread(cache.invalidate_doc, document_id)
