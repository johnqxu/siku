from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import config_invalid


@dataclass(frozen=True)
class SourcePaths:
    asset_dir: Path
    raw_dir: Path
    canonical_dir: Path
    summary_dir: Path


class AssetStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.index_path = root / "index.sqlite"

    def initialize_source(self, source_id: str) -> SourcePaths:
        self.ensure_root()
        asset_dir = self.root / source_id
        paths = SourcePaths(
            asset_dir=asset_dir,
            raw_dir=asset_dir / "raw",
            canonical_dir=asset_dir / "canonical",
            summary_dir=asset_dir / "summary",
        )
        for directory in (paths.raw_dir, paths.canonical_dir, paths.summary_dir):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise config_invalid("素材仓库来源目录无法创建。") from exc
        return paths

    def ensure_root(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise config_invalid("素材仓库目录无法创建。") from exc

        if not self.root.is_dir():
            raise config_invalid("素材仓库路径必须是目录。")

        probe = self.root / ".km-write-test"
        try:
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            raise config_invalid("素材仓库目录不可写。") from exc
