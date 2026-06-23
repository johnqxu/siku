from __future__ import annotations

from pathlib import Path
import uuid
from typing import Callable

from .agent_runtime import DeepAgentsRuntime, build_deep_agents_model
from .agent_state import AgentState, AgentStateGuard, AgentStateStore, AgentTraceWriter, ORCHESTRATOR, ToolResult
from .agent_tools import AgentToolbox
from .errors import KmError, agent_orchestration_failed, agent_skill_missing, config_invalid
from .models import IngestRequest, failure_response


def ensure_agent_orchestration_configured(config) -> None:
    if config.llm_tasks.agent_orchestration is None:
        raise config_invalid("缺少 llm.tasks.agent_orchestration 配置。")


MAX_TOOL_STEPS = 12
RETRYABLE_ERROR_CODES = {"WEB_FETCH_FAILED", "BILIBILI_METADATA_FAILED", "LLM_REQUEST_FAILED"}
REQUIRED_AGENT_SKILLS = (
    "url-routing",
    "bilibili-ingest",
    "web-article-ingest",
    "whisper-transcription",
    "domain-classification",
    "summary-generation",
    "obsidian-write",
)


class AgentIngestRunner:
    def __init__(
        self,
        *,
        config,
        runtime=None,
        run_id_factory: Callable[[], str] | None = None,
        toolbox_factory: Callable[..., AgentToolbox] | None = None,
        skill_loader: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.config = config
        self.runtime = runtime
        self.run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self.toolbox_factory = toolbox_factory or AgentToolbox
        self.skill_loader = skill_loader or load_agent_skills

    def run(self, payload: dict[str, object]) -> dict[str, object]:
        state = AgentState()
        trace_writer: AgentTraceWriter | None = None
        state_store: AgentStateStore | None = None
        try:
            request = IngestRequest.from_payload(payload)
            state.original_url = request.url
            ensure_agent_orchestration_configured(self.config)
            skill_context = self.skill_loader()
            runtime = self.runtime or self.create_runtime(skill_context)
            run_id = self.run_id_factory()
            toolbox = self.toolbox_factory(state=state, config=self.config, run_id=run_id)
            guard = AgentStateGuard(state)
            wrapped_tools = self.wrap_tools(toolbox, guard)
            trace_context = {
                "url": request.url,
                "mode": request.mode,
                "orchestrator": ORCHESTRATOR,
                "skills": sorted(skill_context.keys()),
            }
            result = runtime.run(trace_context, wrapped_tools)
            tool_calls = self.execute_planned_tools(result.tool_calls, wrapped_tools)
            trace_writer = getattr(toolbox, "trace_writer", None)
            state_store = getattr(toolbox, "state_store", None)
            if state_store is None and state.asset_dir:
                state_store = AgentStateStore(Path(state.asset_dir))
            if trace_writer is None and state.asset_dir:
                trace_writer = AgentTraceWriter(Path(state.asset_dir), run_id=run_id)
            if result.final_status not in {"completed", "processed_ready", "skipped_existing"}:
                error = agent_orchestration_failed(result.error or "Agent 编排未完成。")
                return self.fail(error, state, state_store, trace_writer)
            tool_error = last_tool_error(tool_calls)
            if tool_error is not None:
                return self.fail(tool_error, state, state_store, trace_writer)
            if state.stage == "processed_ready":
                if trace_writer is not None:
                    trace_writer.run_finished(status=last_status(tool_calls, state.stage))
                if state_store is not None:
                    state_store.write_state(state)
                return success_response(state, state_store, trace_writer, status=last_status(tool_calls, state.stage))
            error = agent_orchestration_failed("Agent 未推进到完成状态。")
            return self.fail(error, state, state_store, trace_writer)
        except KmError as exc:
            return self.fail(exc, state, state_store, trace_writer)
        except Exception:
            return self.fail(agent_orchestration_failed(), state, state_store, trace_writer)

    def create_runtime(self, skill_context: dict[str, str]):
        model_ref = self.config.llm_tasks.agent_orchestration
        model_config = self.config.llm_models[model_ref]
        instructions = build_agent_instructions(skill_context)
        return DeepAgentsRuntime(model=build_deep_agents_model(model_config), instructions=instructions)

    def wrap_tools(self, toolbox, guard: AgentStateGuard) -> dict[str, Callable[[], dict[str, object]]]:
        raw_tools = toolbox.as_tools()
        step_counter = {"step": 0}

        def make_tool(tool_name: str, tool: Callable[[], ToolResult]) -> Callable[[], dict[str, object]]:
            def wrapped() -> dict[str, object]:
                step_counter["step"] += 1
                if step_counter["step"] > MAX_TOOL_STEPS:
                    error = agent_orchestration_failed("Agent tool 调用超过最大步数。")
                    result = ToolResult.failure(
                        tool=tool_name,
                        stage_before=guard.state.stage,
                        error_code=error.error_code,
                        message=error.message,
                        recoverable=error.recoverable,
                    )
                    self.record_attempt(toolbox, step_counter["step"], result, attempt=1)
                    return result.to_dict()

                result = guard.call(tool_name, tool)
                if tool_name == "prepare_source_workspace":
                    trace_writer = getattr(toolbox, "trace_writer", None)
                    if isinstance(trace_writer, AgentTraceWriter) and not getattr(toolbox, "_run_started_written", False):
                        trace_writer.run_started({"url": guard.state.original_url, "orchestrator": ORCHESTRATOR})
                        setattr(toolbox, "_run_started_written", True)
                self.record_attempt(toolbox, step_counter["step"], result, attempt=1)
                if should_retry(result):
                    retried = guard.call(tool_name, tool)
                    self.record_attempt(toolbox, step_counter["step"], retried, attempt=2)
                    result = retried
                self.write_state_if_ready(toolbox)
                return result.to_dict()

            return wrapped

        return {name: make_tool(name, tool) for name, tool in raw_tools.items()}

    def execute_planned_tools(
        self,
        tool_calls: list[dict[str, object]],
        tools: dict[str, Callable[[], dict[str, object]]],
    ) -> list[dict[str, object]]:
        planned_count = sum(1 for call in tool_calls if call.get("status") == "planned")
        if planned_count > MAX_TOOL_STEPS:
            error = agent_orchestration_failed("Agent tool 调用超过最大步数。")
            return [
                ToolResult.failure(
                    tool="agent_plan",
                    stage_before="planned",
                    error_code=error.error_code,
                    message=error.message,
                    recoverable=error.recoverable,
                ).to_dict()
            ]
        executed: list[dict[str, object]] = []
        completed_tools: set[str] = set()
        for call in tool_calls:
            if call.get("status") != "planned":
                executed.append(call)
                continue
            tool_name = call.get("tool")
            if not isinstance(tool_name, str):
                executed.append(call)
                continue
            if tool_name in completed_tools:
                continue
            tool = tools.get(tool_name)
            if tool is None:
                executed.append(call)
                continue
            result = tool()
            executed.append(result)
            if result.get("ok") is False:
                break
            completed_tools.add(tool_name)
            if result.get("stage_after") == "processed_ready":
                break
        return executed

    def record_attempt(self, toolbox, step: int, result: ToolResult, *, attempt: int) -> None:
        trace_writer = getattr(toolbox, "trace_writer", None)
        if isinstance(trace_writer, AgentTraceWriter):
            trace_writer.tool_attempt(step=step, result=result, attempt=attempt)

    def write_state_if_ready(self, toolbox) -> None:
        state_store = getattr(toolbox, "state_store", None)
        if isinstance(state_store, AgentStateStore):
            state_store.write_state(toolbox.state)

    def fail(
        self,
        error: KmError,
        state: AgentState,
        state_store: AgentStateStore | None,
        trace_writer: AgentTraceWriter | None,
    ) -> dict[str, object]:
        state.error_code = error.error_code
        state.error_message = error.message
        if trace_writer is not None:
            trace_writer.run_failed(error.error_code, error.message)
        if state_store is not None:
            state_store.write_state(state)
        response = failure_response(error)
        response["orchestrator"] = ORCHESTRATOR
        if trace_writer is not None:
            response["trace_path"] = str(trace_writer.trace_path)
        if state_store is not None:
            response["state_path"] = str(state_store.state_path)
        return response


def should_retry(result: ToolResult) -> bool:
    if result.ok:
        return False
    if result.error_code == "BILIBILI_TRANSCRIPT_FAILED":
        return bool(result.retryable)
    return result.error_code in RETRYABLE_ERROR_CODES


def load_agent_skills(root: Path | None = None) -> dict[str, str]:
    project_root = root or Path(__file__).resolve().parents[1]
    skills: dict[str, str] = {}
    for name in REQUIRED_AGENT_SKILLS:
        path = project_root / "skills" / name / "SKILL.md"
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise agent_skill_missing(f"缺少必需 skill：{name}") from exc
        if not content:
            raise agent_skill_missing(f"必需 skill 为空：{name}")
        skills[name] = trim_skill_context(content)
    return skills


def trim_skill_context(content: str) -> str:
    lines = [line.rstrip() for line in content.splitlines()]
    compact = "\n".join(line for line in lines if line.strip())
    return compact[:4000]


def build_agent_instructions(skill_context: dict[str, str]) -> str:
    return "\n\n".join(
        [
            "你是 siku 知识导入 agent。只能按状态机调用受控 Python tools。",
            "不要直接读取完整来源内容、写文件、写 SQLite、写 Obsidian 或直接调用业务 LLM。",
            "合法 tools：route_url、prepare_source_workspace、collect_bilibili_text、collect_web_article_text、classify_domain、generate_summary、write_obsidian_note、mark_source_processed。",
            *[f"## {name}\n{content}" for name, content in skill_context.items()],
        ]
    )


def success_response(
    state: AgentState,
    state_store: AgentStateStore | None,
    trace_writer: AgentTraceWriter | None,
    *,
    status: str,
) -> dict[str, object]:
    response: dict[str, object] = {
        "ok": True,
        "status": status,
        "orchestrator": ORCHESTRATOR,
    }
    if state.content_type is not None:
        response["content_type"] = state.content_type
    if state.original_url is not None:
        response["source_url"] = state.original_url
    if state.asset_dir is not None:
        response["asset_dir"] = state.asset_dir
    for field in ("canonical_text_path", "domain_path", "summary_path", "note_path"):
        value = getattr(state, field)
        if value is not None:
            response[field] = value
    if state_store is not None:
        response["state_path"] = str(state_store.state_path)
    if trace_writer is not None:
        response["trace_path"] = str(trace_writer.trace_path)
    summary_payload = load_summary_payload_from_state(state)
    if summary_payload:
        response["domain"] = summary_payload.get("domain", "")
        response["title"] = summary_payload.get("title", "")
    return response


def load_summary_payload_from_state(state: AgentState) -> dict[str, object]:
    if state.summary_path is None:
        return {}
    try:
        payload = json_path(Path(state.summary_path))
    except Exception:
        return {}
    return payload


def json_path(path: Path) -> dict[str, object]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def last_status(tool_calls: list[dict[str, object]], fallback: str) -> str:
    if not tool_calls:
        return fallback
    status = tool_calls[-1].get("status")
    return status if isinstance(status, str) else fallback


def last_tool_error(tool_calls: list[dict[str, object]]) -> KmError | None:
    for call in reversed(tool_calls):
        if call.get("ok") is not False:
            continue
        error_code = call.get("error_code")
        message = call.get("message")
        recoverable = call.get("recoverable")
        if isinstance(error_code, str) and isinstance(message, str) and isinstance(recoverable, bool):
            return KmError(error_code, message, recoverable, 2 if recoverable else 1)
    return None
