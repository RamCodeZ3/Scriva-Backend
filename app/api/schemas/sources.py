from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SourceResponseSchema(BaseModel):
    id: UUID
    type: str
    raw: str
    char_count: int
    created_at: datetime


class SourceDetailResponseSchema(SourceResponseSchema):
    content: str
