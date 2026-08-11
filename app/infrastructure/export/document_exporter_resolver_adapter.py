from __future__ import annotations

from uuid import UUID

from application.ports.document_exporter_port import DocumentExporterPort
from application.ports.document_exporter_resolver_port import (
    DocumentExporterResolverPort,
    UnsupportedExportTargetError,
)
from application.ports.google_credentials_port import GoogleCredentialsPort

from infrastructure.auth.google_oauth_token_provider import GoogleOAuthTokenProvider
from infrastructure.export.google_docs_exporter_adapter import GoogleDocsExporterAdapter
from infrastructure.export.pdf_document_exporter_adapter import PdfDocumentExporterAdapter

_GOOGLE = "google"
_PDF = "pdf"
_SUPPORTED = {_GOOGLE, _PDF}


class DocumentExporterResolverAdapter(DocumentExporterResolverPort):
    """
    Picks the exporter for `export_target`. Only pays the cost of a
    Google credential lookup + token refresh when `export_target ==
    "google"` — a request with `export_target="pdf"` (the default)
    never touches `GoogleCredentialsPort` or hits the 403 the old
    `get_google_access_token` dependency used to force on everyone.
    """

    def __init__(
        self,
        pdf_exporter: PdfDocumentExporterAdapter,
        google_credentials_repository: GoogleCredentialsPort,
        google_token_provider: GoogleOAuthTokenProvider,
    ) -> None:
        self._pdf_exporter = pdf_exporter
        self._credentials_repository = google_credentials_repository
        self._token_provider = google_token_provider

    async def resolve(self, export_target: str, user_id: UUID) -> DocumentExporterPort:
        target = (export_target or _PDF).strip().lower()

        if target not in _SUPPORTED:
            raise UnsupportedExportTargetError(
                f"Unsupported export_target '{export_target}'. "
                f"Expected one of: {', '.join(sorted(_SUPPORTED))}."
            )

        if target == _PDF:
            return self._pdf_exporter

        refresh_token = await self._credentials_repository.get_refresh_token(user_id)
        if refresh_token is None:
            raise UnsupportedExportTargetError(
                "export_target='google' requires this account to have "
                "granted Google Docs/Drive access first."
            )

        try:
            access_token = await self._token_provider.get_access_token(refresh_token)
        except ValueError as exc:
            raise UnsupportedExportTargetError(
                f"Could not refresh Google credentials: {exc}"
            ) from exc

        return GoogleDocsExporterAdapter(user_access_token=access_token)
