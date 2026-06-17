from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import KmError, input_invalid


@dataclass(frozen=True)
class IngestRequest:
    url: str
    mode: str = "ingest"

    @classmethod
    def from_payload(cls, payload: Any) -> "IngestRequest":
        if not isinstance(payload, dict):
            raise input_invalid("stdin JSON 必须是对象。")

        url = payload.get("url")
        if not isinstance(url, str) or not url.strip():
            raise input_invalid("缺少必填字段 url。")
        url = url.strip()

        mode = payload.get("mode", "ingest")
        if mode != "ingest":
            raise input_invalid("mode 只允许 ingest。")

        return cls(url=url, mode=mode)


def failure_response(error: KmError) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "error_code": error.error_code,
        "message": error.message,
        "recoverable": error.recoverable,
    }
    note_path = getattr(error, "note_path", None)
    if error.error_code == "INDEX_WRITE_FAILED" and isinstance(note_path, str):
        payload["note_path"] = note_path
    return payload


def skipped_existing_response(note_path: str, asset_dir: str, source_url: str) -> dict[str, object]:
    return {
        "ok": True,
        "status": "skipped_existing",
        "note_path": note_path,
        "asset_dir": asset_dir,
        "source_url": source_url,
    }


def transcript_ready_response(
    *,
    content_type: str,
    source_url: str,
    asset_dir: str,
    canonical_text_path: str,
    asset_manifest: dict[str, str],
) -> dict[str, object]:
    return {
        "ok": True,
        "status": "transcript_ready",
        "content_type": content_type,
        "source_url": source_url,
        "asset_dir": asset_dir,
        "canonical_text_path": canonical_text_path,
        "asset_manifest": asset_manifest,
    }


def content_ready_response(
    *,
    content_type: str,
    source_url: str,
    asset_dir: str,
    canonical_text_path: str,
    asset_manifest: dict[str, str],
    parser_id: str,
    fetch_method: str,
) -> dict[str, object]:
    return {
        "ok": True,
        "status": "content_ready",
        "content_type": content_type,
        "source_url": source_url,
        "asset_dir": asset_dir,
        "canonical_text_path": canonical_text_path,
        "asset_manifest": asset_manifest,
        "parser_id": parser_id,
        "fetch_method": fetch_method,
    }


def domain_ready_response(
    *,
    content_type: str,
    source_url: str,
    asset_dir: str,
    canonical_text_path: str,
    domain_path: str,
    domain: str,
    taxonomy_version: int,
    model_ref: str,
) -> dict[str, object]:
    return {
        "ok": True,
        "status": "domain_ready",
        "content_type": content_type,
        "source_url": source_url,
        "asset_dir": asset_dir,
        "canonical_text_path": canonical_text_path,
        "domain_path": domain_path,
        "domain": domain,
        "taxonomy_version": taxonomy_version,
        "model_ref": model_ref,
    }


def summary_ready_response(
    *,
    content_type: str,
    source_url: str,
    asset_dir: str,
    canonical_text_path: str,
    domain_path: str,
    summary_path: str,
    domain: str,
    title: str,
    summary_model_ref: str,
    evaluation_enabled: bool,
    evaluation_dir: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": True,
        "status": "summary_ready",
        "content_type": content_type,
        "source_url": source_url,
        "asset_dir": asset_dir,
        "canonical_text_path": canonical_text_path,
        "domain_path": domain_path,
        "summary_path": summary_path,
        "domain": domain,
        "title": title,
        "summary_model_ref": summary_model_ref,
        "evaluation_enabled": evaluation_enabled,
    }
    if evaluation_dir is not None:
        payload["evaluation_dir"] = evaluation_dir
    return payload


def processed_ready_response(
    *,
    content_type: str,
    source_url: str,
    asset_dir: str,
    canonical_text_path: str,
    domain_path: str,
    summary_path: str,
    note_path: str,
    domain: str,
    title: str,
) -> dict[str, object]:
    return {
        "ok": True,
        "status": "processed_ready",
        "content_type": content_type,
        "source_url": source_url,
        "asset_dir": asset_dir,
        "canonical_text_path": canonical_text_path,
        "domain_path": domain_path,
        "summary_path": summary_path,
        "note_path": note_path,
        "domain": domain,
        "title": title,
    }
