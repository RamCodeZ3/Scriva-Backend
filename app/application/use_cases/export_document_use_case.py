from __future__ import annotations

from application.dtos.document_dtos import ExportDocumentInput
from application.dtos.export_result import ExportResult
from application.exceptions import (
    DocumentAccessDeniedError,
    DocumentNotFoundError,
)
from application.ports.document_exporter_resolver_port import (
    DocumentExporterResolverPort,
)
from application.ports.document_repository_port import DocumentRepositoryPort

from domain.entities.document import DocumentStatus
from domain.exceptions import DocumentBuildError


class ExportDocumentUseCase:
    def __init__(
        self,
        document_repository: DocumentRepositoryPort,
        exporter_resolver: DocumentExporterResolverPort,
    ) -> None:
        self._documents = document_repository
        self._exporter_resolver = exporter_resolver

    async def execute(self, data: ExportDocumentInput) -> ExportResult:
        document = await self._documents.get_by_id(data.document_id)
        if document is None:
            raise DocumentNotFoundError(
                f"Document '{data.document_id}' does not exist."
            )
        if document.user_id != data.user_id:
            raise DocumentAccessDeniedError(
                f"Document '{data.document_id}' does not belong to this account."
            )
        if document.status != DocumentStatus.DONE:
            raise DocumentBuildError(
                f"Cannot export a document in '{document.status.value}' status; "
                "it must be 'done'."
            )

        exporter = await self._exporter_resolver.resolve(
            data.export, data.user_id
        )
        return await exporter.export(document)
