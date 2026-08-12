from abc import ABC, abstractmethod

from domain.value_objects.apa_structure import APASection
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference


class DocumentWriterPort(ABC):
    """
    Driven port for the AI writer. Adapter: GeminiDocumentWriterAdapter.

    Given the plain text extracted from the source, drafts a proper
    academic title plus every required APA 7 section (presentation,
    index, introduction, body, conclusion, sources) and the structured
    list of references used, so the domain's `Document.complete(...)`
    can validate and store them.
    """

    @abstractmethod
    async def write(
        self,
        *,
        source_content: str,
        title: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
    ) -> tuple[str, list[APASection], list[SourceReference]]:
        """
        Returns `(title, sections, references)`. `title` is a fresh,
        AI-written academic title (never the raw `title` argument
        echoed back, never a URL or a verbatim source snippet) — callers
        should use it to (re)set the document's title, not the one they
        passed in.

        Must raise `domain.exceptions.DocumentBuildError` if the model
        fails to produce a usable draft (empty response, malformed
        structure, provider error, etc), including when the generated
        title itself is empty, URL-like, or implausibly long.
        """
        raise NotImplementedError
