from __future__ import annotations

from uuid import UUID

from application.ports.document_job_dispatcher_port import DocumentJobDispatcherPort
from application.use_cases.process_document_use_case import ProcessDocumentUseCase


class SyncJobDispatcherAdapter(DocumentJobDispatcherPort):
    """
    Runs the extraction + AI + export pipeline synchronously, in the
    same request, instead of scheduling it in the background.

    Used while there's a single POST /documents endpoint that must
    answer with the final {status, document_url} in one shot. Swap for
    `FastAPIBackgroundJobDispatcher` (or a real queue) once you split
    "create" from "process" and add a status-polling endpoint.

    NOTE: this means the HTTP request stays open for as long as the
    whole pipeline takes (page scraping + Gemini + Google Docs export)
    — make sure your server/proxy timeouts are set accordingly.
    """

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
