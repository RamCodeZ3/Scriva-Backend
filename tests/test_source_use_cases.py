from __future__ import annotations

import unittest
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.exceptions import (
    SourceAccessDeniedError,
    SourceNotFoundError,
)
from application.use_cases.get_user_source_use_case import GetUserSourceUseCase
from application.use_cases.list_user_sources_use_case import (
    ListUserSourcesUseCase,
)
from domain.entities.source import Source, SourceStatus, SourceType


class SourceUseCasesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user_id = uuid4()
        self.source = Source(
            id=uuid4(),
            source_type=SourceType.WEB,
            raw="https://example.com/article",
            status=SourceStatus.EXTRACTED,
            user_id=self.user_id,
            content="Complete source content",
            char_count=23,
            created_at=datetime(2026, 9, 3, tzinfo=UTC),
        )
        self.repository = _SourceRepository(self.user_id, [self.source])

    def test_new_source_records_its_owner(self) -> None:
        source = Source.create_auto("Plain text", self.user_id)

        self.assertEqual(source.user_id, self.user_id)

    async def test_lists_sources_without_full_content(self) -> None:
        result = await ListUserSourcesUseCase(self.repository).execute(
            self.user_id, self.user_id
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, self.source.id)
        self.assertFalse(hasattr(result[0], "content"))
        self.assertEqual(result[0].char_count, 23)

    async def test_returns_source_detail_for_owner(self) -> None:
        result = await GetUserSourceUseCase(self.repository).execute(
            self.user_id, self.source.id, self.user_id
        )

        self.assertEqual(result.content, "Complete source content")
        self.assertEqual(result.raw, "https://example.com/article")

    async def test_rejects_access_to_another_users_sources(self) -> None:
        with self.assertRaises(SourceAccessDeniedError):
            await ListUserSourcesUseCase(self.repository).execute(
                self.user_id, uuid4()
            )

    async def test_hides_missing_or_unowned_source_as_not_found(self) -> None:
        with self.assertRaises(SourceNotFoundError):
            await GetUserSourceUseCase(self.repository).execute(
                self.user_id, uuid4(), self.user_id
            )


class _SourceRepository:
    def __init__(self, owner_id: UUID, sources: list[Source]) -> None:
        self.owner_id = owner_id
        self.sources = sources

    async def save(self, source: Source) -> None:
        self.sources.append(source)

    async def get_by_id(self, source_id: UUID) -> Source | None:
        return next(
            (source for source in self.sources if source.id == source_id),
            None,
        )

    async def list_by_user(self, user_id: UUID) -> list[Source]:
        return self.sources if user_id == self.owner_id else []

    async def get_by_id_for_user(
        self, source_id: UUID, user_id: UUID
    ) -> Source | None:
        if user_id != self.owner_id:
            return None
        return await self.get_by_id(source_id)


if __name__ == "__main__":
    unittest.main()
