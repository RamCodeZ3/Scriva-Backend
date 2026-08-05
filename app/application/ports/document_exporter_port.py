from abc import ABC, abstractmethod

from domain.entities.document import Document


class DocumentExporterPort(ABC):
    """
    Driven port for turning a finished Document into a real file.
    Adapter: GoogleDocsExporterAdapter (creates the doc, applies the
    APA layout/styles, and shares it).
    """

    @abstractmethod
    async def export(self, document: Document) -> str:
        """Returns the shareable link to the exported document."""
        raise NotImplementedError
