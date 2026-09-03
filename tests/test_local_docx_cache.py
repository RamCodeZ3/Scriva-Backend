from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from infrastructure.cache.local_docx_cache import LocalDocxCacheService


class LocalDocxCacheServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.cache = LocalDocxCacheService(
            Path(self.temp_directory.name), size_limit=1024**2
        )

    def tearDown(self) -> None:
        self.cache.close()
        self.temp_directory.cleanup()

    def test_hash_is_stable_regardless_of_dictionary_order(self) -> None:
        first = {"children": [{"text": "Hello"}], "meta": {"a": 1}}
        second = {"meta": {"a": 1}, "children": [{"text": "Hello"}]}

        self.assertEqual(
            self.cache.compute_hash(first),
            self.cache.compute_hash(second),
        )

    def test_stores_and_invalidates_all_document_versions(self) -> None:
        self.cache.set_docx("doc-1", "hash-a", b"first")
        self.cache.set_docx("doc-1", "hash-b", b"second")
        self.cache.set_docx("doc-2", "hash-a", b"other")

        self.assertEqual(self.cache.get_docx("doc-1", "hash-a"), b"first")
        self.cache.invalidate_doc("doc-1")

        self.assertIsNone(self.cache.get_docx("doc-1", "hash-a"))
        self.assertIsNone(self.cache.get_docx("doc-1", "hash-b"))
        self.assertEqual(self.cache.get_docx("doc-2", "hash-a"), b"other")

    def test_configures_lru_and_size_limit(self) -> None:
        self.assertEqual(
            self.cache._cache.eviction_policy, "least-recently-used"
        )
        self.assertEqual(self.cache._cache.size_limit, 1024**2)


if __name__ == "__main__":
    unittest.main()
