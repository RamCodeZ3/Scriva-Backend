from __future__ import annotations

from uuid import UUID

from fastapi import BackgroundTasks

from application.ports.document_job_dispatcher_port import DocumentJobDispatcherPort
from application.use_cases.process_document_use_case import ProcessDocumentUseCase


class FastAPIBackgroundJobDispatcher(DocumentJobDispatcherPort):
    """
    Simplest possible adapter: schedules `ProcessDocumentUseCase` on
    FastAPI's own `BackgroundTasks`, so it runs right after the HTTP
    response is sent. Good to get started; swap for a Celery/SQS/etc.
    adapter once you need retries, multiple workers, or processing that
    survives an API restart.

    Must be constructed per-request (its `BackgroundTasks` instance is
    tied to the current request), typically via a FastAPI dependency:

        def get_job_dispatcher(
            background_tasks: BackgroundTasks,
            process_use_case: ProcessDocumentUseCase = Depends(...),
        ) -> DocumentJobDispatcherPort:
            return FastAPIBackgroundJobDispatcher(background_tasks, process_use_case)
    """

    def __init__(
        self,
        background_tasks: BackgroundTasks,
        process_use_case: ProcessDocumentUseCase,
    ) -> None:
        self._background_tasks = background_tasks
        self._process_use_case = process_use_case

    async def dispatch(self, document_id: UUID) -> None:
        self._background_tasks.add_task(self._run, document_id)

    async def _run(self, document_id: UUID) -> None:
        await self._process_use_case.execute(document_id)
