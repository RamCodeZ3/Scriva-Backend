from abc import ABC, abstractmethod

from domain.value_objects.apa_structure import APASection
from domain.value_objects.document_type import DocumentType
from domain.value_objects.presentation_info import PresentationInfo
from domain.value_objects.source_ref import SourceReference


class DocumentWriterPort(ABC):
    """
    Driven port for the AI writer. Adapter: GeminiDocumentWriterAdapter.

    Given the plain text extracted from the source, drafts every
    required APA 7 section (presentation, index, introduction, body,
    conclusion, sources) plus the structured list of references used,
    so the domain's `Document.complete(...)` can validate and store them.
    """

    @abstractmethod
    async def write(
        self,
        *,
        source_content: str,
        title: str,
        document_type: DocumentType,
        presentation: PresentationInfo,
    ) -> tuple[list[APASection], list[SourceReference]]:
        """
        Must raise `domain.exceptions.DocumentBuildError` if the model
        fails to produce a usable draft (empty response, malformed
        structure, provider error, etc).
        """
        raise NotImplementedError
