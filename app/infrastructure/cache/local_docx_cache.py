from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from application.ports.docx_cache_port import DocxCachePort
from diskcache import Cache


class LocalDocxCacheService(DocxCachePort):
    """Disk-backed, content-addressed DOCX cache with automatic LRU."""

    def __init__(
        self,
        directory: str | Path = "./storage/cache/docx",
        *,
        size_limit: int = 1024**3,
    ) -> None:
        if size_limit <= 0:
            raise ValueError("size_limit must be greater than zero.")
        cache_directory = Path(directory).expanduser()
        cache_directory.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(
            str(cache_directory),
            size_limit=size_limit,
            eviction_policy="least-recently-used",
            tag_index=True,
        )

    def compute_hash(self, node_tree_dict: dict[str, Any]) -> str:
        canonical_json = json.dumps(
            node_tree_dict,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def get_docx(self, doc_id: str, doc_hash: str) -> bytes | None:
        value = self._cache.get(self._key(doc_id, doc_hash))
        return value if isinstance(value, bytes) else None

    def set_docx(self, doc_id: str, doc_hash: str, docx_bytes: bytes) -> None:
        if not isinstance(docx_bytes, bytes) or not docx_bytes:
            raise ValueError("docx_bytes must be non-empty bytes.")
        self._cache.set(self._key(doc_id, doc_hash), docx_bytes, tag=doc_id)

    def invalidate_doc(self, doc_id: str) -> None:
        self._cache.evict(doc_id)

    def close(self) -> None:
        self._cache.close()

    @staticmethod
    def _key(doc_id: str, doc_hash: str) -> str:
        if not doc_id or not doc_hash:
            raise ValueError("doc_id and doc_hash must be non-empty.")
        return f"{doc_id}:{doc_hash}"
