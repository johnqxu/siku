from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .agent_state import AgentState, AgentStateStore, AgentTraceWriter, ToolResult
from .asset_store import AssetStore
from .bilibili import YtDlpBilibiliDownloader, collect_bilibili_transcript
from .domain import OpenAiCompatibleLlmClient, classify_domain as classify_domain_pipeline
from .errors import KmError, config_invalid
from .index import IngestIndex
from .obsidian import ObsidianNoteContext, load_summary_payload, write_obsidian_note as write_obsidian_note_pipeline
from .routing import ContentType, route_url as route_url_pipeline
from .summary import generate_summary as generate_summary_pipeline, load_domain_payload
from .url_state import generate_source_id, normalize_url
from .web_article import HttpWebArticleFetcher, collect_web_article
from .whisper import OpenVinoWhisperTranscriber


class AgentToolbox:
    def __init__(
        self,
        *,
        state: AgentState,
        config,
        run_id: str = "run",
        bilibili_collector: Callable[..., Any] | None = None,
        web_collector: Callable[..., Any] | None = None,
        domain_classifier: Callable[..., Any] | None = None,
        summary_generator: Callable[..., Any] | None = None,
        summary_loader: Callable[..., dict[str, Any]] | None = None,
        obsidian_writer: Callable[..., Any] | None = None,
        now_factory: Callable[[], str] | None = None,
    ) -> None:
        self.state = state
        self.config = config
        self.run_id = run_id
        self.bilibili_collector = bilibili_collector or collect_bilibili_transcript
        self.web_collector = web_collector or collect_web_article
        self.domain_classifier = domain_classifier or classify_domain_pipeline
        self.summary_generator = summary_generator or generate_summary_pipeline
        self.summary_loader = summary_loader or load_summary_payload
        self.obsidian_writer = obsidian_writer or write_obsidian_note_pipeline
        self.now_factory = now_factory or default_now
        self.state_store: AgentStateStore | None = None
        self.trace_writer: AgentTraceWriter | None = None

    def as_tools(self) -> dict[str, Callable[[], ToolResult]]:
        return {
            "route_url": self.route_url,
            "prepare_source_workspace": self.prepare_source_workspace,
            "collect_bilibili_text": self.collect_bilibili_text,
            "collect_web_article_text": self.collect_web_article_text,
            "classify_domain": self.classify_domain,
            "generate_summary": self.generate_summary,
            "write_obsidian_note": self.write_obsidian_note,
            "mark_source_processed": self.mark_source_processed,
        }

    def route_url(self) -> ToolResult:
        stage_before = self.state.stage
        try:
            original_url = self.state.original_url or ""
            normalized = normalize_url(original_url)
            route = route_url_pipeline(normalized.normalized_url)
            if route.content_type == ContentType.UNSUPPORTED:
                from .errors import unsupported_url

                raise unsupported_url()
            self.state.original_url = normalized.original_url
            self.state.normalized_url = normalized.normalized_url
            self.state.content_type = str(route.content_type)
            return ToolResult.success(
                tool="route_url",
                status="routed",
                stage_before=stage_before,
                stage_after="routed",
                normalized_url=normalized.normalized_url,
                content_type=str(route.content_type),
            )
        except KmError as exc:
            return failure_from_error("route_url", stage_before, exc)

    def prepare_source_workspace(self) -> ToolResult:
        stage_before = self.state.stage
        try:
            normalized_url = required_state_string(self.state.normalized_url, "normalized_url")
            original_url = required_state_string(self.state.original_url, "original_url")
            content_type = required_state_string(self.state.content_type, "content_type")
            source_id = generate_source_id(normalized_url)
            asset_store = AssetStore(self.config.asset_store_path)
            paths = asset_store.initialize_source(source_id)
            index = IngestIndex(asset_store.index_path)
            index.initialize()
            agent_dir = paths.asset_dir / "agent"
            agent_dir.mkdir(parents=True, exist_ok=True)
            self.state.source_id = source_id
            self.state.asset_dir = str(paths.asset_dir)
            self.state_store = AgentStateStore(paths.asset_dir)
            self.trace_writer = AgentTraceWriter(paths.asset_dir, run_id=self.run_id)

            duplicate = index.find_processed_source(normalized_url)
            if duplicate is not None:
                self.state.note_path = duplicate.note_path
                return ToolResult.success(
                    tool="prepare_source_workspace",
                    status="skipped_existing",
                    stage_before=stage_before,
                    stage_after="processed_ready",
                    skipped=True,
                    skip_reason="processed_existing",
                    source_id=source_id,
                    original_url=duplicate.original_url,
                    normalized_url=normalized_url,
                    content_type=content_type,
                    source_url=duplicate.original_url,
                    asset_dir=duplicate.asset_dir,
                    note_path=duplicate.note_path,
                    state_path=str(self.state_store.state_path),
                    trace_path=str(self.trace_writer.trace_path),
                )

            return ToolResult.success(
                tool="prepare_source_workspace",
                status="workspace_ready",
                stage_before=stage_before,
                stage_after="workspace_ready",
                source_id=source_id,
                original_url=original_url,
                normalized_url=normalized_url,
                content_type=content_type,
                asset_dir=str(paths.asset_dir),
                state_path=str(self.state_store.state_path),
                trace_path=str(self.trace_writer.trace_path),
            )
        except KmError as exc:
            return failure_from_error("prepare_source_workspace", stage_before, exc)

    def collect_bilibili_text(self) -> ToolResult:
        return self._collect_text(
            tool="collect_bilibili_text",
            default_filename="transcript.md",
            collector=lambda asset_dir: self.bilibili_collector(
                source_url=required_state_string(self.state.normalized_url, "normalized_url"),
                asset_dir=asset_dir,
                downloader=YtDlpBilibiliDownloader(),
                transcriber=OpenVinoWhisperTranscriber(
                    model_dir=self.config.whisper_model_dir,
                    model_size=self.config.whisper_model_size,
                    device=self.config.whisper_device,
                ),
            ),
        )

    def collect_web_article_text(self) -> ToolResult:
        return self._collect_text(
            tool="collect_web_article_text",
            default_filename="content.md",
            collector=lambda asset_dir: self.web_collector(
                source_url=required_state_string(self.state.normalized_url, "normalized_url"),
                asset_dir=asset_dir,
                fetcher=HttpWebArticleFetcher(),
            ),
        )

    def _collect_text(
        self,
        *,
        tool: str,
        default_filename: str,
        collector: Callable[[Path], Any],
    ) -> ToolResult:
        stage_before = self.state.stage
        try:
            asset_dir = Path(required_state_string(self.state.asset_dir, "asset_dir"))
            existing_path = asset_dir / "canonical" / default_filename
            if is_valid_text_artifact(existing_path):
                self.state.canonical_text_path = str(existing_path)
                return ToolResult.success(
                    tool=tool,
                    status="text_ready",
                    stage_before=stage_before,
                    stage_after="text_ready",
                    skipped=True,
                    canonical_text_path=str(existing_path),
                    asset_dir=str(asset_dir),
                )
            result = collector(asset_dir)
            canonical_text_path = getattr(result, "canonical_text_path", existing_path)
            self.state.canonical_text_path = str(canonical_text_path)
            return ToolResult.success(
                tool=tool,
                status="text_ready",
                stage_before=stage_before,
                stage_after="text_ready",
                canonical_text_path=str(canonical_text_path),
                asset_dir=str(asset_dir),
            )
        except KmError as exc:
            return failure_from_error(tool, stage_before, exc, retryable=is_retryable_error(exc))

    def classify_domain(self) -> ToolResult:
        stage_before = self.state.stage
        try:
            asset_dir = Path(required_state_string(self.state.asset_dir, "asset_dir"))
            canonical_text_path = Path(required_state_string(self.state.canonical_text_path, "canonical_text_path"))
            domain_path = asset_dir / "summary" / "domain.json"
            existing = load_valid_domain(domain_path)
            if existing is not None:
                self.state.domain_path = str(domain_path)
                return ToolResult.success(
                    tool="classify_domain",
                    status="domain_ready",
                    stage_before=stage_before,
                    stage_after="domain_ready",
                    skipped=True,
                    domain_path=str(domain_path),
                    domain=existing["domain"],
                )
            model_ref = required_task_ref(self.config.llm_tasks.domain_classification, "domain_classification")
            result = self.domain_classifier(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                llm_model=self.config.llm_models[model_ref],
                model_ref=model_ref,
                llm_client=OpenAiCompatibleLlmClient(),
            )
            self.state.domain_path = str(result.domain_path)
            return ToolResult.success(
                tool="classify_domain",
                status="domain_ready",
                stage_before=stage_before,
                stage_after="domain_ready",
                domain_path=str(result.domain_path),
                domain=result.domain,
            )
        except KmError as exc:
            return failure_from_error("classify_domain", stage_before, exc, retryable=is_retryable_error(exc))

    def generate_summary(self) -> ToolResult:
        stage_before = self.state.stage
        try:
            asset_dir = Path(required_state_string(self.state.asset_dir, "asset_dir"))
            canonical_text_path = Path(required_state_string(self.state.canonical_text_path, "canonical_text_path"))
            domain_path = Path(required_state_string(self.state.domain_path, "domain_path"))
            summary_path = asset_dir / "summary" / "summary.json"
            existing = load_valid_summary(summary_path)
            if existing is not None:
                self.state.summary_path = str(summary_path)
                return ToolResult.success(
                    tool="generate_summary",
                    status="summary_ready",
                    stage_before=stage_before,
                    stage_after="summary_ready",
                    skipped=True,
                    summary_path=str(summary_path),
                    domain=string_value(existing.get("domain")),
                    title=string_value(existing.get("title")),
                )
            model_ref = required_task_ref(self.config.llm_tasks.summary_generation, "summary_generation")
            result = self.summary_generator(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                source_url=required_state_string(self.state.normalized_url, "normalized_url"),
                content_type=required_state_string(self.state.content_type, "content_type"),
                domain_path=domain_path,
                llm_models=self.config.llm_models,
                summary_model_ref=model_ref,
                llm_client=OpenAiCompatibleLlmClient(),
                max_input_chars=self.config.summary.max_input_chars,
                evaluation=self.config.summary.evaluation,
            )
            self.state.summary_path = str(result.summary_path)
            return ToolResult.success(
                tool="generate_summary",
                status="summary_ready",
                stage_before=stage_before,
                stage_after="summary_ready",
                summary_path=str(result.summary_path),
                domain=result.domain,
                title=result.title,
            )
        except KmError as exc:
            return failure_from_error("generate_summary", stage_before, exc, retryable=is_retryable_error(exc))

    def write_obsidian_note(self) -> ToolResult:
        stage_before = self.state.stage
        try:
            context = self._obsidian_context()
            summary_payload = self.summary_loader(context=context)
            now = self.now_factory()
            note = self.obsidian_writer(
                context=context,
                summary_payload=summary_payload,
                vault_path=self.config.vault_path,
                inbox_dir=self.config.inbox_dir,
                now=now,
                date_prefix=now[:10],
            )
            note_path = str(note.note_path)
            self.state.note_path = note_path
            return ToolResult.success(
                tool="write_obsidian_note",
                status="note_ready",
                stage_before=stage_before,
                stage_after="note_ready",
                note_path=note_path,
                domain=string_value(summary_payload.get("domain")),
                title=string_value(summary_payload.get("title")),
            )
        except KmError as exc:
            return failure_from_error("write_obsidian_note", stage_before, exc)

    def mark_source_processed(self) -> ToolResult:
        stage_before = self.state.stage
        try:
            context = self._obsidian_context()
            payload = load_json_object(context.summary_path)
            domain = string_value(payload.get("domain"))
            title = string_value(payload.get("title"))
            note_path = required_state_string(self.state.note_path, "note_path")
            index = IngestIndex(AssetStore(self.config.asset_store_path).index_path)
            index.initialize()
            index.mark_processed(
                source_id=required_state_string(self.state.source_id, "source_id"),
                normalized_url=required_state_string(self.state.normalized_url, "normalized_url"),
                original_url=required_state_string(self.state.original_url, "original_url"),
                content_type=required_state_string(self.state.content_type, "content_type"),
                domain=domain,
                title=title,
                note_path=note_path,
                asset_dir=required_state_string(self.state.asset_dir, "asset_dir"),
                now=self.now_factory(),
            )
            return ToolResult.success(
                tool="mark_source_processed",
                status="processed_ready",
                stage_before=stage_before,
                stage_after="processed_ready",
                note_path=note_path,
                domain=domain,
                title=title,
            )
        except KmError as exc:
            return failure_from_error("mark_source_processed", stage_before, exc)

    def _obsidian_context(self) -> ObsidianNoteContext:
        return ObsidianNoteContext(
            source_id=required_state_string(self.state.source_id, "source_id"),
            normalized_url=required_state_string(self.state.normalized_url, "normalized_url"),
            original_url=required_state_string(self.state.original_url, "original_url"),
            content_type=required_state_string(self.state.content_type, "content_type"),
            asset_dir=Path(required_state_string(self.state.asset_dir, "asset_dir")),
            canonical_text_path=Path(required_state_string(self.state.canonical_text_path, "canonical_text_path")),
            domain_path=Path(required_state_string(self.state.domain_path, "domain_path")),
            summary_path=Path(required_state_string(self.state.summary_path, "summary_path")),
        )


def failure_from_error(
    tool: str,
    stage_before: str,
    error: KmError,
    *,
    retryable: bool | None = None,
    retry_reason: str | None = None,
) -> ToolResult:
    return ToolResult.failure(
        tool=tool,
        stage_before=stage_before,
        error_code=error.error_code,
        message=error.message,
        recoverable=error.recoverable,
        retryable=retryable,
        retry_reason=retry_reason,
    )


def required_state_string(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise config_invalid(f"Agent state 缺少 {name}。")
    return value


def required_task_ref(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise config_invalid(f"缺少 llm.tasks.{name} 配置。")
    return value


def is_valid_text_artifact(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def load_valid_domain(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = load_domain_payload(path)
    except KmError:
        return None
    return payload


def load_valid_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = load_json_object(path)
    except KmError:
        return None
    if payload.get("schema_version") != 1:
        return None
    if not isinstance(payload.get("domain"), str) or not isinstance(payload.get("title"), str):
        return None
    return payload


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise config_invalid(f"无法读取 JSON 文件：{path}") from exc
    if not isinstance(payload, dict):
        raise config_invalid(f"JSON 文件必须是 object：{path}")
    return payload


def string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def is_retryable_error(error: KmError) -> bool:
    return error.error_code in {"WEB_FETCH_FAILED", "BILIBILI_METADATA_FAILED", "LLM_REQUEST_FAILED"}


def default_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
