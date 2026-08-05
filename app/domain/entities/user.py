from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from domain.exceptions import UserDomainError


@dataclass
class User:
    id: UUID
    email: str
    name: str
    is_premium: bool
    created_at: datetime
    updated_at: datetime

    # ── Factory Method ────────────────────────────────────────────────────────

    @classmethod
    def create(cls, email: str, name: str) -> "User":
        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean:
            raise UserDomainError("The email address provided is invalid.")
        
        name_clean = name.strip()
        if not name_clean:
            raise UserDomainError("The username cannot be left blank.")

        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            email=email_clean,
            name=name_clean,
            is_premium=False,
            created_at=now,
            updated_at=now,
        )

    # ── Domain Business Actions ───────────────────────────────────────────────

    def update_profile(self, name: str) -> None:
        name_clean = name.strip()
        if not name_clean:
            raise UserDomainError("The username cannot be left blank.")
        self.name = name_clean
        self._touch()

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _touch(self) -> None:
        self.updated_at = datetime.utcnow()
