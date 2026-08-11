from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from application.ports.document_exporter_port import DocumentExporterPort


class UnsupportedExportTargetError(Exception):
    """
    Raised when `export_target` doesn't match any known destination,
    or matches one the user hasn't set up (e.g. 'google' without a
    linked account).

    NOTE: your `application/exceptions.py` already centralizes sibling
    errors (`UnsupportedSourceTypeError`, `UserNotFoundError`,
    `DocumentNotFoundError`, `SourceNotFoundError`). I couldn't see
    that file's contents, so this class lives here instead — move it
    there and update the two imports (this file and
    `document_exporter_resolver_adapter.py`) if you'd rather keep all
    application exceptions in one place.
    """


class DocumentExporterResolverPort(ABC):
    """
    Driven port that picks the right `DocumentExporterPort` for a given
    request, instead of wiring a single exporter at DI-graph build
    time like the previous `get_document_exporter` dependency did.

    This exists because the two exporters have very different setup
    costs: PDF is stateless and always available, while Google Docs
    needs a per-user access token fetched from a stored refresh_token.
    Resolving lazily — inside `ProcessDocumentUseCase`, once we know
    `document.export_target` — means a request with `export_target=
    "pdf"` never pays for (or fails on) a Google credential lookup it
    doesn't need.
    """

    @abstractmethod
    async def resolve(self, export_target: str, user_id: UUID) -> DocumentExporterPort:
        """
        Raises `UnsupportedExportTargetError` if `export_target` is
        unknown, or if it's 'google' and the user has no linked
        account / the refresh token can't be exchanged.
        """
        raise NotImplementedError
