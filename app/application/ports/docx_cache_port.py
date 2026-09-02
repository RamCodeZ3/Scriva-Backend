from abc import ABC, abstractmethod
from typing import Any


class DocxCachePort(ABC):
    """Content-addressed cache for compiled DOCX documents."""

    @abstractmethod
    def compute_hash(self, node_tree_dict: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_docx(self, doc_id: str, doc_hash: str) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def set_docx(self, doc_id: str, doc_hash: str, docx_bytes: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def invalidate_doc(self, doc_id: str) -> None:
        raise NotImplementedError
