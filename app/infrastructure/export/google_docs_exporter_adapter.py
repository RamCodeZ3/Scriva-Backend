from __future__ import annotations

import asyncio

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from domain.entities.document import Document
from domain.exceptions import DocumentBuildError

from application.ports.document_exporter_port import DocumentExporterPort

_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleDocsExporterAdapter(DocumentExporterPort):
    """
    Creates a Google Doc from the finished `Document`, writes each APA
    section as a heading + paragraph, and shares it with "anyone with
    the link can view" so `export_url` is immediately usable.

    This gives you a working baseline; refine `_build_requests` with
    the actual APA 7 formatting rules you need (font, margins, spacing,
    page numbers, running head, etc.) via the Docs API's paragraph and
    text style requests.
    """

    def __init__(self, service_account_file: str) -> None:
        self._credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=_SCOPES
        )

    async def export(self, document: Document) -> str:
        return await asyncio.to_thread(self._export_sync, document)

    def _export_sync(self, document: Document) -> str:
        docs_service = build("docs", "v1", credentials=self._credentials)
        drive_service = build("drive", "v3", credentials=self._credentials)

        try:
            doc = docs_service.documents().create(body={"title": document.title}).execute()
            document_id = doc["documentId"]

            requests = self._build_requests(document)
            if requests:
                docs_service.documents().batchUpdate(
                    documentId=document_id, body={"requests": requests}
                ).execute()

            drive_service.permissions().create(
                fileId=document_id,
                body={"role": "reader", "type": "anyone"},
            ).execute()

        except HttpError as exc:
            raise DocumentBuildError(f"Google Docs export failed: {exc}") from exc

        return f"https://docs.google.com/document/d/{document_id}/edit"

    def _build_requests(self, document: Document) -> list[dict]:
        """
        Google Docs' batchUpdate always inserts at a fixed index, so
        sections are written back-to-front (last section first) to end
        up in the right reading order at index 1.
        """
        requests: list[dict] = []
        for section in reversed(document.sections):
            body_text = f"{section.content}\n\n"
            heading_text = f"{section.title}\n"

            requests.append({"insertText": {"location": {"index": 1}, "text": body_text}})
            requests.append({"insertText": {"location": {"index": 1}, "text": heading_text}})
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": 1, "endIndex": 1 + len(heading_text)},
                        "paragraphStyle": {"namedStyleType": "HEADING_1"},
                        "fields": "namedStyleType",
                    }
                }
            )
        return requests
