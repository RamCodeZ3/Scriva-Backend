from abc import ABC, abstractmethod

from domain.value_objects.apa_structure import APASection


class DocumentParserPort(ABC):
    """Driven port that converts an uploaded office document to the AST."""

    @abstractmethod
    async def parse(self, content: bytes) -> list[APASection]:
        raise NotImplementedError
