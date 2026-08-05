class ApplicationError(Exception):
    """Base class for every error raised by the application layer."""


class DocumentNotFoundError(ApplicationError):
    """Raised when a Document id does not exist in the repository."""


class SourceNotFoundError(ApplicationError):
    """Raised when a Source id does not exist in the repository."""


class UserNotFoundError(ApplicationError):
    """Raised when a User id/email does not exist in the repository."""


class UserAlreadyExistsError(ApplicationError):
    """Raised when trying to register a user with an email already in use."""


class UnsupportedSourceTypeError(ApplicationError):
    """Raised when the requested source_type has no registered extractor."""
