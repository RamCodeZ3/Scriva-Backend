from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ExportResult:
    """
    Output of `DocumentExporterPort.export(...)`.

    Two shapes coexist because the two adapters produce fundamentally
    different artifacts:

    - Google Docs: the file lives in the user's own Drive, so there's
      only a shareable `url` (no bytes worth carrying around).
    - PDF (ReportLab): there's no destination account to upload to, so
      the adapter hands back the generated file in memory
      (`file_bytes`) *and* leaves a copy on the server's local disk
      (`storage_path`) for quick inspection — `url` stays None unless
      you later mount `storage_path` behind a static file route.

    Exactly one of `url` / `file_bytes` is expected to be populated in
    practice, but both are optional so the type doesn't promise a
    guarantee no single adapter actually provides.
    """

    url: str | None = None
    file_bytes: bytes | None = None
    file_name: str | None = None
    content_type: str | None = None
    storage_path: str | None = None  # where it was saved server-side, if anywhere
