from __future__ import annotations

from uuid import UUID

from application.ports.document_job_dispatcher_port import (
    DocumentJobDispatcherPort,
)
from application.use_cases.process_document_use_case import (
    ProcessDocumentUseCase,
)


class SyncJobDispatcherAdapter(DocumentJobDispatcherPort):
    def __init__(self, process_use_case: ProcessDocumentUseCase) -> None:
        self._process_use_case = process_use_case

    async def dispatch(self, document_id: UUID) -> None:
        try:
            await self._process_use_case.execute(document_id)
        except Exception:
            # ProcessDocumentUseCase already persisted the failure via
            # Document.fail()/Source.mark_failed() before re-raising.
            # Swallow it here so CreateDocumentUseCase can still return
            # a normal {status: "failed", document_url: null} response
            # instead of bubbling up a 500.
            pass
