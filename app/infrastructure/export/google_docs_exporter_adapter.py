from __future__ import annotations

import asyncio

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from domain.entities.document import Document
from domain.exceptions import DocumentBuildError

from application.ports.document_exporter_port import DocumentExporterPort


class GoogleDocsExporterAdapter(DocumentExporterPort):
    """
    Creates a Google Doc directly in the user's Google Drive account
    using their OAuth 2.0 access token.
    """

    def __init__(self, user_access_token: str) -> None:
        self._credentials = Credentials(token=user_access_token)

    async def export(self, document: Document) -> str:
        return await asyncio.to_thread(self._export_sync, document)

    def _export_sync(self, document: Document) -> str:
        docs_service = build("docs", "v1", credentials=self._credentials)

        try:
            doc = docs_service.documents().create(body={"title": document.title}).execute()
            document_id = doc["documentId"]

            requests = self._build_requests(document)
            if requests:
                docs_service.documents().batchUpdate(
                    documentId=document_id, body={"requests": requests}
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
