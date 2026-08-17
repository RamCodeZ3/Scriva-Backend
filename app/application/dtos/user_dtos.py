from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CreateUserInput:
    email: str
    name: str


@dataclass(frozen=True)
class UpdateUserProfileInput:
    name: str


@dataclass(frozen=True)
class UserOutput:
    id: UUID
    email: str
    name: str
    is_premium: bool
