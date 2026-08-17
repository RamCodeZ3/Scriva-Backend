class ApplicationError(Exception):
    """Base class for every error raised by the application layer."""


class DocumentNotFoundError(ApplicationError):
    pass


class SourceNotFoundError(ApplicationError):
    pass


class UserNotFoundError(ApplicationError):
    pass


class UserAlreadyExistsError(ApplicationError):
    pass


class UnsupportedSourceTypeError(ApplicationError):
    pass


class DocumentAccessDeniedError(ApplicationError):
    """Raised when a document is requested/modified by a user who doesn't own it."""
