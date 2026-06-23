from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable, Protocol

from .errors import KmError, agent_runtime_unavailable


AgentTool = Callable[[], dict[str, object]]


@dataclass(frozen=True)
class AgentRunResult:
    tool_calls: list[dict[str, object]]
    final_status: str
    error: str | None = None


class AgentRuntime(Protocol):
    def run(self, context: dict[str, object], tools: dict[str, AgentTool]) -> AgentRunResult:
        ...


class FakeAgentRuntime:
    def __init__(self, tool_plan: list[str] | tuple[str, ...]) -> None:
        self.tool_plan = tuple(tool_plan)

    def run(self, context: dict[str, object], tools: dict[str, AgentTool]) -> AgentRunResult:
        tool_calls = [planned_tool_call(tool_name) for tool_name in self.tool_plan]
        return AgentRunResult(tool_calls=tool_calls, final_status="completed")


class DeepAgentsRuntime:
    def __init__(self, *, model, instructions: str) -> None:
        self.model = model
        self.instructions = instructions

    def run(self, context: dict[str, object], tools: dict[str, AgentTool]) -> AgentRunResult:
        try:
            from deepagents import create_deep_agent
            from langchain_core.tools import tool as langchain_tool
        except Exception as exc:
            raise agent_runtime_unavailable("Deep Agents runtime 不可导入；请安装 agent extra。") from exc

        try:
            agent_tools = [to_langchain_tool(name, tool_fn, langchain_tool) for name, tool_fn in tools.items()]
            agent = create_deep_agent(
                model=self.model,
                tools=agent_tools,
                system_prompt=self.instructions,
                middleware=[ProjectToolFilterMiddleware(set(tools.keys()))],
                subagents=[],
            )
        except Exception as exc:
            raise agent_runtime_unavailable("Deep Agents runtime 初始化失败。") from exc

        try:
            raw_result = invoke_agent(agent, context)
        except KmError:
            raise
        except Exception as exc:
            raise agent_runtime_unavailable("Deep Agents runtime 执行失败。") from exc

        return coerce_agent_result(raw_result)


def to_langchain_tool(name: str, tool_fn: AgentTool, langchain_tool):
    def wrapped() -> str:
        return json.dumps(planned_tool_call(name), ensure_ascii=False)

    wrapped.__name__ = name
    wrapped.__doc__ = f"请求 siku runner 调用受控 Python tool: {name}。不接受参数，只返回计划 JSON。"
    return langchain_tool(name, description=wrapped.__doc__)(wrapped)


def planned_tool_call(name: str) -> dict[str, object]:
    return {
        "ok": True,
        "tool": name,
        "status": "planned",
    }


def build_deep_agents_model(model_config):
    if model_config.provider != "openai_compatible":
        return model_config.model
    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        raise agent_runtime_unavailable("缺少 langchain-openai；请安装 agent extra。") from exc
    return ChatOpenAI(
        model=model_config.model,
        base_url=model_config.base_url,
        api_key=model_config.api_key,
        timeout=model_config.timeout_seconds,
        max_tokens=model_config.max_output_tokens,
    )


try:
    from langchain.agents.middleware.types import AgentMiddleware
except Exception:  # pragma: no cover - only used when agent extra is absent.
    AgentMiddleware = object


class ProjectToolFilterMiddleware(AgentMiddleware):
    def __init__(self, allowed_tool_names: set[str]) -> None:
        self.allowed_tool_names = allowed_tool_names

    def wrap_model_call(self, request, handler):
        request = request.override(
            tools=[
                candidate
                for candidate in request.tools
                if tool_name(candidate) in self.allowed_tool_names
            ]
        )
        return handler(request)


def tool_name(candidate: Any) -> str | None:
    if isinstance(candidate, dict):
        value = candidate.get("name")
        return value if isinstance(value, str) else None
    value = getattr(candidate, "name", None)
    return value if isinstance(value, str) else None


def invoke_agent(agent, context: dict[str, object]):
    if hasattr(agent, "invoke"):
        return agent.invoke({"messages": [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]})
    if hasattr(agent, "run"):
        return agent.run(context)
    raise RuntimeError("Deep Agents runtime 缺少 invoke/run 方法。")


def coerce_agent_result(raw_result) -> AgentRunResult:
    if isinstance(raw_result, AgentRunResult):
        return raw_result
    if isinstance(raw_result, dict):
        direct_tool_calls = raw_result.get("tool_calls")
        if isinstance(direct_tool_calls, list):
            tool_calls = [call for call in direct_tool_calls if isinstance(call, dict)]
        else:
            tool_calls = tool_calls_from_messages(raw_result.get("messages"))
        final_status = raw_result.get("final_status", "completed")
        if not isinstance(final_status, str):
            final_status = "completed"
        error = raw_result.get("error")
        return AgentRunResult(
            tool_calls=tool_calls,
            final_status=final_status,
            error=error if isinstance(error, str) else None,
        )
    return AgentRunResult(tool_calls=[], final_status="completed")


def tool_calls_from_messages(messages: object) -> list[dict[str, object]]:
    if not isinstance(messages, list):
        return []
    calls: list[dict[str, object]] = []
    for message in messages:
        content = getattr(message, "content", None)
        name = getattr(message, "name", None)
        if not isinstance(content, str):
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            if isinstance(name, str) and "tool" not in payload:
                payload["tool"] = name
            calls.append(payload)
    return calls
