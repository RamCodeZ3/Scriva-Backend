from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ExportResult:
    url: str | None = None
    file_bytes: bytes | None = None
    file_name: str | None = None
    content_type: str | None = None
