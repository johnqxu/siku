from pathlib import Path
import sqlite3
import tempfile
import unittest

from km.errors import KmError
from km.index import IngestIndex


class IngestIndexTests(unittest.TestCase):
    def make_index(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return IngestIndex(Path(temp_dir.name) / "index.sqlite")

    def insert_source(self, index, *, normalized_url, status, original_url="https://source.example/original"):
        with sqlite3.connect(index.path) as connection:
            connection.execute(
                """
                INSERT INTO sources (
                  id, normalized_url, original_url, content_type, domain, title,
                  note_path, asset_dir, created_at, updated_at, status,
                  error_code, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"id-{status}",
                    normalized_url,
                    original_url,
                    "web_article",
                    "编程",
                    "title",
                    "/vault/Inbox/note.md",
                    "/assets/id",
                    "2026-06-14T00:00:00Z",
                    "2026-06-14T00:00:00Z",
                    status,
                    None,
                    None,
                ),
            )

    def test_initialize_creates_sources_schema_indexes_and_user_version(self):
        index = self.make_index()

        index.initialize()
        index.initialize()

        with sqlite3.connect(index.path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(sources)")}
            indexes = {row[1] for row in connection.execute("PRAGMA index_list(sources)")}
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertEqual(
            columns,
            {
                "id",
                "normalized_url",
                "original_url",
                "content_type",
                "domain",
                "title",
                "note_path",
                "asset_dir",
                "created_at",
                "updated_at",
                "status",
                "error_code",
                "error_message",
            },
        )
        self.assertIn("idx_sources_domain", indexes)
        self.assertIn("idx_sources_created_at", indexes)
        self.assertIn("idx_sources_status", indexes)
        self.assertEqual(user_version, 1)

    def test_initialize_preserves_existing_sources(self):
        index = self.make_index()
        index.initialize()
        self.insert_source(index, normalized_url="https://example.com/a", status="processed")

        index.initialize()

        with sqlite3.connect(index.path) as connection:
            count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]

        self.assertEqual(count, 1)

    def test_initialize_rejects_future_schema_version(self):
        index = self.make_index()
        index.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(index.path) as connection:
            connection.execute("PRAGMA user_version = 999")

        with self.assertRaises(KmError) as raised:
            index.initialize()

        self.assertEqual(raised.exception.error_code, "CONFIG_INVALID")

    def test_find_processed_source_returns_original_url_note_and_asset_dir(self):
        index = self.make_index()
        index.initialize()
        self.insert_source(
            index,
            normalized_url="https://example.com/a",
            status="processed",
            original_url="https://EXAMPLE.com/a#fragment",
        )

        duplicate = index.find_processed_source("https://example.com/a")

        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.original_url, "https://EXAMPLE.com/a#fragment")
        self.assertEqual(duplicate.note_path, "/vault/Inbox/note.md")
        self.assertEqual(duplicate.asset_dir, "/assets/id")

    def test_find_processed_source_ignores_non_processed_status(self):
        index = self.make_index()
        index.initialize()
        self.insert_source(index, normalized_url="https://example.com/a", status="failed")

        duplicate = index.find_processed_source("https://example.com/a")

        self.assertIsNone(duplicate)

    def test_mark_processed_inserts_and_updates_source_without_schema_upgrade(self):
        index = self.make_index()
        index.initialize()

        index.mark_processed(
            source_id="source-id",
            normalized_url="https://example.com/a",
            original_url="https://EXAMPLE.com/a#fragment",
            content_type="web_article",
            domain="编程",
            title="Python 调试实践",
            note_path="/vault/Inbox/Python.md",
            asset_dir="/assets/source-id",
            now="2026-06-15T22:10:00+08:00",
        )
        index.mark_processed(
            source_id="source-id",
            normalized_url="https://example.com/a",
            original_url="https://EXAMPLE.com/a#fragment",
            content_type="web_article",
            domain="AI",
            title="更新后的标题",
            note_path="/vault/Inbox/Updated.md",
            asset_dir="/assets/source-id",
            now="2026-06-15T22:30:00+08:00",
        )

        with sqlite3.connect(index.path) as connection:
            row = connection.execute(
                """
                SELECT status, domain, title, note_path, created_at, updated_at, error_code, error_message
                FROM sources
                WHERE normalized_url = ?
                """,
                ("https://example.com/a",),
            ).fetchone()
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            columns = {row[1] for row in connection.execute("PRAGMA table_info(sources)")}

        self.assertEqual(row[0], "processed")
        self.assertEqual(row[1], "AI")
        self.assertEqual(row[2], "更新后的标题")
        self.assertEqual(row[3], "/vault/Inbox/Updated.md")
        self.assertEqual(row[4], "2026-06-15T22:10:00+08:00")
        self.assertEqual(row[5], "2026-06-15T22:30:00+08:00")
        self.assertIsNone(row[6])
        self.assertIsNone(row[7])
        self.assertEqual(user_version, 1)
        self.assertNotIn("summary_path", columns)

    def test_mark_processed_updates_existing_normalized_url_with_different_source_id(self):
        index = self.make_index()
        index.initialize()
        self.insert_source(index, normalized_url="https://example.com/a", status="failed")

        index.mark_processed(
            source_id="new-source-id",
            normalized_url="https://example.com/a",
            original_url="https://EXAMPLE.com/a#fragment",
            content_type="web_article",
            domain="AI",
            title="更新后的标题",
            note_path="/vault/Inbox/Updated.md",
            asset_dir="/assets/new-source-id",
            now="2026-06-15T22:30:00+08:00",
        )

        with sqlite3.connect(index.path) as connection:
            rows = connection.execute(
                """
                SELECT id, status, domain, title, note_path, asset_dir, created_at, updated_at, error_code, error_message
                FROM sources
                WHERE normalized_url = ?
                """,
                ("https://example.com/a",),
            ).fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "id-failed")
        self.assertEqual(rows[0][1], "processed")
        self.assertEqual(rows[0][2], "AI")
        self.assertEqual(rows[0][3], "更新后的标题")
        self.assertEqual(rows[0][4], "/vault/Inbox/Updated.md")
        self.assertEqual(rows[0][5], "/assets/new-source-id")
        self.assertEqual(rows[0][6], "2026-06-14T00:00:00Z")
        self.assertEqual(rows[0][7], "2026-06-15T22:30:00+08:00")
        self.assertIsNone(rows[0][8])
        self.assertIsNone(rows[0][9])

    def test_mark_failed_records_stage_eight_failure_and_does_not_block_retry(self):
        index = self.make_index()
        index.initialize()

        index.mark_failed(
            source_id="source-id",
            normalized_url="https://example.com/a",
            original_url="https://example.com/a",
            content_type="web_article",
            asset_dir="/assets/source-id",
            error_code="OBSIDIAN_WRITE_FAILED",
            error_message="写入失败。",
            now="2026-06-15T22:10:00+08:00",
            domain="AI",
            title="AI Agent",
            note_path="/vault/Inbox/AI.md",
        )

        with sqlite3.connect(index.path) as connection:
            row = connection.execute(
                "SELECT status, error_code, error_message, note_path FROM sources WHERE normalized_url = ?",
                ("https://example.com/a",),
            ).fetchone()

        self.assertEqual(row[0], "failed")
        self.assertEqual(row[1], "OBSIDIAN_WRITE_FAILED")
        self.assertEqual(row[2], "写入失败。")
        self.assertEqual(row[3], "/vault/Inbox/AI.md")
        self.assertIsNone(index.find_processed_source("https://example.com/a"))

    def test_mark_failed_updates_existing_normalized_url_with_different_source_id(self):
        index = self.make_index()
        index.initialize()
        self.insert_source(index, normalized_url="https://example.com/a", status="failed")

        index.mark_failed(
            source_id="new-source-id",
            normalized_url="https://example.com/a",
            original_url="https://EXAMPLE.com/a#fragment",
            content_type="web_article",
            asset_dir="/assets/new-source-id",
            error_code="OBSIDIAN_WRITE_FAILED",
            error_message="写入失败。",
            now="2026-06-15T22:30:00+08:00",
            domain="AI",
            title="AI Agent",
            note_path="/vault/Inbox/AI.md",
        )

        with sqlite3.connect(index.path) as connection:
            rows = connection.execute(
                """
                SELECT id, status, error_code, error_message, asset_dir, created_at, updated_at
                FROM sources
                WHERE normalized_url = ?
                """,
                ("https://example.com/a",),
            ).fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "id-failed")
        self.assertEqual(rows[0][1], "failed")
        self.assertEqual(rows[0][2], "OBSIDIAN_WRITE_FAILED")
        self.assertEqual(rows[0][3], "写入失败。")
        self.assertEqual(rows[0][4], "/assets/new-source-id")
        self.assertEqual(rows[0][5], "2026-06-14T00:00:00Z")
        self.assertEqual(rows[0][6], "2026-06-15T22:30:00+08:00")


if __name__ == "__main__":
    unittest.main()
