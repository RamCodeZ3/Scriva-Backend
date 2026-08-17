from dataclasses import dataclass


@dataclass(frozen=True)
class SourceReference:
    """Bibliographic reference formatted for APA 7."""

    author: str
    title: str
    year: int | None = None
    url: str | None = None
    publisher: str | None = None

    def to_apa_string(self) -> str:
        """Returns the reference as a formatted APA 7 string."""
        author = self.author or "Unknown author"
        year = f"({self.year})" if self.year else "(n.d.)"
        publisher = f" {self.publisher}." if self.publisher else ""
        url = f" {self.url}" if self.url else ""
        return f"{author} {year}. {self.title}.{publisher}{url}"
