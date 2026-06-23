from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .errors import agent_invalid_transition


STATE_SCHEMA_VERSION = 1
ORCHESTRATOR = "deep_agents"
TRACE_DENY_KEYS = {
    "api_key",
    "api_key_env",
    "authorization",
    "cookie",
    "env",
    "html",
    "model_output",
    "prompt",
    "raw_response",
    "transcript",
    "content",
}


@dataclass
class AgentState:
    source_id: str | None = None
    original_url: str | None = None
    normalized_url: str | None = None
    content_type: str | None = None
    stage: str = "initialized"
    asset_dir: str | None = None
    canonical_text_path: str | None = None
    domain_path: str | None = None
    summary_path: str | None = None
    note_path: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "orchestrator": ORCHESTRATOR,
            "source_id": self.source_id,
            "original_url": self.original_url,
            "normalized_url": self.normalized_url,
            "content_type": self.content_type,
            "stage": self.stage,
            "asset_dir": self.asset_dir,
            "canonical_text_path": self.canonical_text_path,
            "domain_path": self.domain_path,
            "summary_path": self.summary_path,
            "note_path": self.note_path,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    tool: str
    status: str
    stage_before: str
    stage_after: str
    skipped: bool = False
    skip_reason: str | None = None
    error_code: str | None = None
    message: str | None = None
    recoverable: bool | None = None
    retryable: bool | None = None
    retry_reason: str | None = None
    data: dict[str, object] | None = None

    @classmethod
    def success(
        cls,
        *,
        tool: str,
        status: str,
        stage_before: str,
        stage_after: str,
        skipped: bool = False,
        skip_reason: str | None = None,
        **data: object,
    ) -> "ToolResult":
        return cls(
            ok=True,
            tool=tool,
            status=status,
            stage_before=stage_before,
            stage_after=stage_after,
            skipped=skipped,
            skip_reason=skip_reason,
            data=data,
        )

    @classmethod
    def failure(
        cls,
        *,
        tool: str,
        stage_before: str,
        error_code: str,
        message: str,
        recoverable: bool,
        stage_after: str | None = None,
        retryable: bool | None = None,
        retry_reason: str | None = None,
        **data: object,
    ) -> "ToolResult":
        return cls(
            ok=False,
            tool=tool,
            status="failed",
            stage_before=stage_before,
            stage_after=stage_after or stage_before,
            error_code=error_code,
            message=message,
            recoverable=recoverable,
            retryable=retryable,
            retry_reason=retry_reason,
            data=data,
        )

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "ok": self.ok,
            "tool": self.tool,
            "status": self.status,
            "stage_before": self.stage_before,
            "stage_after": self.stage_after,
            "skipped": self.skipped,
        }
        if self.skip_reason is not None:
            payload["skip_reason"] = self.skip_reason
        if not self.ok:
            payload["error_code"] = self.error_code
            payload["message"] = self.message
            payload["recoverable"] = self.recoverable
        if self.retryable is not None:
            payload["retryable"] = self.retryable
        if self.retry_reason is not None:
            payload["retry_reason"] = self.retry_reason
        if self.data:
            payload.update(self.data)
        return payload


class AgentStateGuard:
    VALID_TRANSITIONS = {
        ("initialized", "route_url"): {"routed"},
        ("routed", "prepare_source_workspace"): {"workspace_ready", "processed_ready"},
        ("workspace_ready", "collect_bilibili_text"): {"text_ready"},
        ("workspace_ready", "collect_web_article_text"): {"text_ready"},
        ("text_ready", "classify_domain"): {"domain_ready"},
        ("domain_ready", "generate_summary"): {"summary_ready"},
        ("summary_ready", "write_obsidian_note"): {"note_ready"},
        ("note_ready", "mark_source_processed"): {"processed_ready"},
    }

    def __init__(self, state: AgentState) -> None:
        self.state = state

    def call(self, tool: str, action: Callable[[], ToolResult]) -> ToolResult:
        stage_before = self.state.stage
        allowed = self.VALID_TRANSITIONS.get((stage_before, tool), set())
        if not allowed:
            error = agent_invalid_transition()
            self.state.error_code = error.error_code
            self.state.error_message = error.message
            return ToolResult.failure(
                tool=tool,
                stage_before=stage_before,
                error_code=error.error_code,
                message=error.message,
                recoverable=error.recoverable,
            )

        result = action()
        if result.ok and result.stage_after in allowed:
            self.state.stage = result.stage_after
            self.state.error_code = None
            self.state.error_message = None
            self._apply_result_data(result)
            return result

        if result.ok:
            error = agent_invalid_transition()
            self.state.error_code = error.error_code
            self.state.error_message = error.message
            return ToolResult.failure(
                tool=tool,
                stage_before=stage_before,
                error_code=error.error_code,
                message=error.message,
                recoverable=error.recoverable,
            )

        self.state.error_code = result.error_code
        self.state.error_message = result.message
        return result

    def _apply_result_data(self, result: ToolResult) -> None:
        if not result.data:
            return
        for field in (
            "source_id",
            "original_url",
            "normalized_url",
            "content_type",
            "asset_dir",
            "canonical_text_path",
            "domain_path",
            "summary_path",
            "note_path",
        ):
            value = result.data.get(field)
            if isinstance(value, str):
                setattr(self.state, field, value)


class AgentStateStore:
    def __init__(self, asset_dir: Path) -> None:
        self.asset_dir = asset_dir
        self.agent_dir = asset_dir / "agent"
        self.state_path = self.agent_dir / "state.json"

    def write_state(self, state: AgentState) -> None:
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        state.updated_at = timestamp()
        tmp_path = self.state_path.with_name(f"{self.state_path.name}.tmp")
        tmp_path.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.state_path)


class AgentTraceWriter:
    def __init__(self, asset_dir: Path, *, run_id: str) -> None:
        self.asset_dir = asset_dir
        self.agent_dir = asset_dir / "agent"
        self.trace_path = self.agent_dir / "trace.jsonl"
        self.run_id = run_id

    def run_started(self, context: dict[str, object]) -> None:
        self.append(
            {
                "event": "run_started",
                "context": sanitize_trace_value(context),
            }
        )

    def tool_attempt(self, *, step: int, result: ToolResult, attempt: int) -> None:
        payload = {
            "event": "tool_attempt",
            "step": step,
            "tool": result.tool,
            "attempt": attempt,
            "stage_before": result.stage_before,
            "stage_after": result.stage_after,
            "status": result.status,
            "skipped": result.skipped,
            "error_code": result.error_code,
            "message": result.message,
        }
        if result.skip_reason is not None:
            payload["skip_reason"] = result.skip_reason
        if result.retryable is not None:
            payload["retryable"] = result.retryable
        if result.retry_reason is not None:
            payload["retry_reason"] = result.retry_reason
        if result.data:
            payload["data"] = sanitize_trace_value(result.data)
        self.append(payload)

    def run_finished(self, status: str) -> None:
        self.append({"event": "run_finished", "status": status})

    def run_failed(self, error_code: str, message: str) -> None:
        self.append({"event": "run_failed", "error_code": error_code, "message": message})

    def append(self, payload: dict[str, object]) -> None:
        self.agent_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": timestamp(),
            "run_id": self.run_id,
            **payload,
        }
        with self.trace_path.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps(event, ensure_ascii=False) + "\n")


def sanitize_trace_value(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in TRACE_DENY_KEYS:
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_trace_value(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_trace_value(item) for item in value[:20]]
    if isinstance(value, str):
        if len(value) > 240:
            return value[:120] + "...[truncated]"
        return value
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
