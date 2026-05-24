class DocumentBuildError(Exception):
    """Raised when a Document state transition or build rule is violated."""


class InvalidSourceError(Exception):
    """Raised when the input source cannot be resolved or extracted."""
