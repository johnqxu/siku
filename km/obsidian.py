from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import uuid
from typing import Any

from .errors import config_invalid, obsidian_write_failed, summary_input_invalid


FORBIDDEN_FILENAME_CHARS = set('/\\:*?"<>|')


@dataclass(frozen=True)
class ObsidianNoteContext:
    source_id: str
    normalized_url: str
    original_url: str
    content_type: str
    asset_dir: Path
    canonical_text_path: Path
    domain_path: Path
    summary_path: Path


@dataclass(frozen=True)
class ObsidianWriteResult:
    note_path: Path
    created_at: str
    updated_at: str


def safe_title(title: str) -> str:
    cleaned = "".join(char for char in title if char not in FORBIDDEN_FILENAME_CHARS)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        return "untitled"
    return cleaned[:80]


def note_filename(*, title: str, date_prefix: str, source_id_prefix: str | None = None) -> str:
    suffix = f"-{source_id_prefix}" if source_id_prefix else ""
    return f"{date_prefix}-{safe_title(title)}{suffix}.md"


def validate_summary_for_obsidian(*, context: ObsidianNoteContext, summary_payload: dict[str, Any]) -> None:
    if not isinstance(summary_payload, dict):
        raise summary_input_invalid("summary/summary.json 必须是 JSON object。")
    if summary_payload.get("schema_version") != 1:
        raise summary_input_invalid("summary/summary.json schema_version 无效。")

    source = summary_payload.get("source")
    if not isinstance(source, dict):
        raise summary_input_invalid("summary/summary.json 缺少 source。")
    if source.get("url") not in (context.original_url, context.normalized_url):
        raise summary_input_invalid("summary source.url 与当前来源不一致。")
    expected_paths = {
        "asset_dir": str(context.asset_dir),
        "canonical_text_path": str(context.canonical_text_path),
        "domain_path": str(context.domain_path),
    }
    for key, expected in expected_paths.items():
        if source.get(key) != expected:
            raise summary_input_invalid(f"summary source.{key} 与当前上下文不一致。")

    required_strings = ("domain", "title", "one_sentence_summary", "model_ref", "model")
    for key in required_strings:
        value = summary_payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise summary_input_invalid(f"summary/summary.json 缺少合法 {key}。")
    for key in ("core_points", "key_concepts", "actionable_insights", "questions", "tags"):
        if not isinstance(summary_payload.get(key), list):
            raise summary_input_invalid(f"summary/summary.json 缺少合法 {key}。")
    if not isinstance(summary_payload.get("domain_notes"), dict):
        raise summary_input_invalid("summary/summary.json 缺少合法 domain_notes。")


def load_summary_payload(*, context: ObsidianNoteContext) -> dict[str, Any]:
    try:
        payload = json.loads(context.summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise summary_input_invalid("缺少或无法解析 summary/summary.json。") from exc
    if not isinstance(payload, dict):
        raise summary_input_invalid("summary/summary.json 必须是 JSON object。")
    validate_summary_for_obsidian(context=context, summary_payload=payload)
    return payload


def render_obsidian_note(
    *,
    context: ObsidianNoteContext,
    summary_payload: dict[str, Any],
    created_at: str,
    updated_at: str,
) -> str:
    validate_summary_for_obsidian(context=context, summary_payload=summary_payload)
    frontmatter = render_frontmatter(
        {
            "title": summary_payload["title"],
            "source_id": context.source_id,
            "source_url": context.original_url,
            "content_type": context.content_type,
            "domain": summary_payload["domain"],
            "tags": summary_payload["tags"],
            "created_at": created_at,
            "updated_at": updated_at,
            "asset_dir": str(context.asset_dir),
            "canonical_text": str(context.canonical_text_path),
            "domain_path": str(context.domain_path),
            "summary_path": str(context.summary_path),
            "summary_model_ref": summary_payload["model_ref"],
            "status": "processed",
        }
    )
    lines: list[str] = [
        frontmatter,
        f"# {summary_payload['title']}",
        "",
        "## 一句话摘要",
        str(summary_payload["one_sentence_summary"]),
        "",
        "## 核心观点",
    ]
    lines.extend(f"- {point}" for point in summary_payload["core_points"])
    lines.extend(["", "## 关键概念"])
    for concept in summary_payload["key_concepts"]:
        name = concept.get("name", "")
        explanation = concept.get("explanation", "")
        lines.append(f"- **{name}**：{explanation}")
    lines.extend(["", "## 领域笔记"])
    for field, value in summary_payload["domain_notes"].items():
        lines.extend([f"### {field}", str(value), ""])
    lines.append("## 可操作启发")
    lines.extend(f"- {item}" for item in summary_payload["actionable_insights"])
    lines.extend(["", "## 值得追问的问题"])
    lines.extend(f"- {question}" for question in summary_payload["questions"])
    lines.extend(
        [
            "",
            "## 来源与素材",
            f"- 原始链接：{context.original_url}",
            f"- 素材目录：`{context.asset_dir}`",
            f"- 规范文本：`{context.canonical_text_path}`",
            f"- 领域 JSON：`{context.domain_path}`",
            f"- 总结 JSON：`{context.summary_path}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_frontmatter(payload: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in payload.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_string(str(item))}")
        else:
            lines.append(f"{key}: {yaml_string(str(value))}")
    lines.append("---")
    return "\n".join(lines)


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_note_frontmatter(path: Path) -> dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---\n"):
        return {}
    end = content.find("\n---", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if ": " not in line or line.startswith(" "):
            continue
        key, raw_value = line.split(": ", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value.strip().strip('"')
        if isinstance(value, str):
            fields[key] = value
    return fields


def write_obsidian_note(
    *,
    context: ObsidianNoteContext,
    summary_payload: dict[str, Any],
    vault_path: Path,
    inbox_dir: str,
    now: str,
    date_prefix: str,
) -> ObsidianWriteResult:
    validate_vault(vault_path)
    inbox_path = vault_path / inbox_dir
    try:
        inbox_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise obsidian_write_failed("Obsidian inbox 目录无法创建。") from exc
    if not inbox_path.is_dir():
        raise obsidian_write_failed("Obsidian inbox 路径必须是目录。")

    note_path = resolve_note_path(
        inbox_path=inbox_path,
        title=summary_payload["title"],
        source_id=context.source_id,
        date_prefix=date_prefix,
    )
    existing = read_note_frontmatter(note_path)
    created_at = existing.get("created_at", now) if existing.get("source_id") == context.source_id else now
    content = render_obsidian_note(
        context=context,
        summary_payload=summary_payload,
        created_at=created_at,
        updated_at=now,
    )
    atomic_write_text(note_path, content)
    return ObsidianWriteResult(note_path=note_path, created_at=created_at, updated_at=now)


def validate_vault(vault_path: Path) -> None:
    if not vault_path.exists() or not vault_path.is_dir():
        raise config_invalid("vault_path 必须是已存在的 Obsidian vault 目录。")
    probe = vault_path / f".km-vault-write-test-{uuid.uuid4().hex}.tmp"
    fd: int | None = None
    try:
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        fd = None
        probe.unlink()
    except OSError as exc:
        raise config_invalid("vault_path 不可写。") from exc
    finally:
        if fd is not None:
            os.close(fd)
        try:
            probe.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass


def resolve_note_path(*, inbox_path: Path, title: str, source_id: str, date_prefix: str) -> Path:
    default_path = inbox_path / note_filename(title=title, date_prefix=date_prefix)
    if not default_path.exists():
        return default_path
    default_frontmatter = read_note_frontmatter(default_path)
    if default_frontmatter.get("source_id") == source_id:
        return default_path

    fallback_path = inbox_path / note_filename(
        title=title,
        date_prefix=date_prefix,
        source_id_prefix=source_id[:8],
    )
    if not fallback_path.exists():
        return fallback_path
    fallback_frontmatter = read_note_frontmatter(fallback_path)
    if fallback_frontmatter.get("source_id") == source_id:
        return fallback_path
    raise obsidian_write_failed("Obsidian note 文件名冲突。")


def atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        raise obsidian_write_failed("Obsidian note 写入失败。") from exc
