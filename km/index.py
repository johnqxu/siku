from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .errors import config_invalid


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DuplicateSource:
    note_path: str
    asset_dir: str
    original_url: str


class IngestIndex:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.path) as connection:
                version = self.user_version(connection)
                if version > SCHEMA_VERSION:
                    raise config_invalid("SQLite 索引 schema 版本高于当前工具支持版本。")
                self.create_schema(connection)
                if version == 0:
                    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.Error as exc:
            raise config_invalid("SQLite 索引初始化失败。") from exc
        except OSError as exc:
            raise config_invalid("SQLite 索引路径不可用。") from exc

    def find_processed_source(self, normalized_url: str) -> DuplicateSource | None:
        try:
            with sqlite3.connect(self.path) as connection:
                row = connection.execute(
                    """
                    SELECT note_path, asset_dir, original_url
                    FROM sources
                    WHERE normalized_url = ? AND status = 'processed'
                    """,
                    (normalized_url,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise config_invalid("SQLite 重复来源查询失败。") from exc

        if row is None:
            return None
        note_path, asset_dir, original_url = row
        return DuplicateSource(note_path=note_path, asset_dir=asset_dir, original_url=original_url)

    def mark_processed(
        self,
        *,
        source_id: str,
        normalized_url: str,
        original_url: str,
        content_type: str,
        domain: str,
        title: str,
        note_path: str,
        asset_dir: str,
        now: str,
    ) -> None:
        try:
            with sqlite3.connect(self.path) as connection:
                record_id, created_at = self.existing_identity_for_source(
                    connection,
                    source_id=source_id,
                    normalized_url=normalized_url,
                )
                target_id = record_id or source_id
                created_at = created_at or now
                connection.execute(
                    """
                    INSERT INTO sources (
                      id, normalized_url, original_url, content_type, domain, title,
                      note_path, asset_dir, created_at, updated_at, status,
                      error_code, error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', NULL, NULL)
                    ON CONFLICT(id) DO UPDATE SET
                      normalized_url = excluded.normalized_url,
                      original_url = excluded.original_url,
                      content_type = excluded.content_type,
                      domain = excluded.domain,
                      title = excluded.title,
                      note_path = excluded.note_path,
                      asset_dir = excluded.asset_dir,
                      created_at = sources.created_at,
                      updated_at = excluded.updated_at,
                      status = 'processed',
                      error_code = NULL,
                      error_message = NULL
                    """,
                    (
                        target_id,
                        normalized_url,
                        original_url,
                        content_type,
                        domain,
                        title,
                        note_path,
                        asset_dir,
                        created_at,
                        now,
                    ),
                )
        except sqlite3.Error as exc:
            raise config_invalid("SQLite processed 状态写入失败。") from exc

    def mark_failed(
        self,
        *,
        source_id: str,
        normalized_url: str,
        original_url: str,
        content_type: str,
        asset_dir: str,
        error_code: str,
        error_message: str,
        now: str,
        domain: str | None = None,
        title: str | None = None,
        note_path: str | None = None,
    ) -> None:
        try:
            with sqlite3.connect(self.path) as connection:
                record_id, created_at = self.existing_identity_for_source(
                    connection,
                    source_id=source_id,
                    normalized_url=normalized_url,
                )
                target_id = record_id or source_id
                created_at = created_at or now
                connection.execute(
                    """
                    INSERT INTO sources (
                      id, normalized_url, original_url, content_type, domain, title,
                      note_path, asset_dir, created_at, updated_at, status,
                      error_code, error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      normalized_url = excluded.normalized_url,
                      original_url = excluded.original_url,
                      content_type = excluded.content_type,
                      domain = excluded.domain,
                      title = excluded.title,
                      note_path = excluded.note_path,
                      asset_dir = excluded.asset_dir,
                      created_at = sources.created_at,
                      updated_at = excluded.updated_at,
                      status = 'failed',
                      error_code = excluded.error_code,
                      error_message = excluded.error_message
                    """,
                    (
                        target_id,
                        normalized_url,
                        original_url,
                        content_type,
                        domain,
                        title,
                        note_path,
                        asset_dir,
                        created_at,
                        now,
                        error_code,
                        error_message,
                    ),
                )
        except sqlite3.Error as exc:
            raise config_invalid("SQLite failed 状态写入失败。") from exc

    def created_at_for_source(self, connection: sqlite3.Connection, *, source_id: str, normalized_url: str) -> str | None:
        return self.existing_identity_for_source(
            connection,
            source_id=source_id,
            normalized_url=normalized_url,
        )[1]

    def existing_identity_for_source(
        self,
        connection: sqlite3.Connection,
        *,
        source_id: str,
        normalized_url: str,
    ) -> tuple[str | None, str | None]:
        row = connection.execute(
            """
            SELECT id, created_at
            FROM sources
            WHERE id = ? OR normalized_url = ?
            ORDER BY normalized_url = ? DESC, id = ? DESC
            LIMIT 1
            """,
            (source_id, normalized_url, normalized_url, source_id),
        ).fetchone()
        if row is None:
            return None, None
        return row[0], row[1]

    def user_version(self, connection: sqlite3.Connection) -> int:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])

    def create_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
              id TEXT PRIMARY KEY,
              normalized_url TEXT NOT NULL UNIQUE,
              original_url TEXT NOT NULL,
              content_type TEXT NOT NULL,
              domain TEXT,
              title TEXT,
              note_path TEXT,
              asset_dir TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              status TEXT NOT NULL,
              error_code TEXT,
              error_message TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sources_domain ON sources(domain)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources(created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status)")
