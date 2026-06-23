import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

from km.config import load_config
from km.errors import EXIT_RECOVERABLE_FAILURE, KmError


class SimpleTool:
    def __init__(self, name):
        self.name = name


class SimpleRequest:
    def __init__(self, tools):
        self.tools = tools

    def override(self, *, tools):
        return SimpleRequest(tools)


class AgentConfigTests(unittest.TestCase):
    def write_config(self, config_text):
        config = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        self.addCleanup(lambda path=config.name: os.path.exists(path) and os.unlink(path))
        with config:
            config.write(config_text)
        return config.name

    def valid_paths(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)
        return root_path / "vault", root_path / "assets"

    def restore_named_env(self, name, previous):
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous

    def set_env(self, name, value):
        previous = os.environ.get(name)
        os.environ[name] = value
        self.addCleanup(self.restore_named_env, name, previous)

    def load_with_config(self, config_text):
        config_path = self.write_config(config_text)
        previous = os.environ.get("KM_CONFIG")
        os.environ["KM_CONFIG"] = config_path
        self.addCleanup(self.restore_named_env, "KM_CONFIG", previous)
        return load_config()

    def valid_agent_config_text(self):
        vault_path, asset_store_path = self.valid_paths()
        return "\n".join(
            [
                f'vault_path = "{vault_path}"',
                'inbox_dir = "Inbox/Knowledge"',
                f'asset_store_path = "{asset_store_path}"',
                "",
                "[llm.models.agent_flash]",
                'provider = "openai_compatible"',
                'base_url = "https://api.deepseek.com/v1"',
                'model = "deepseek-v4-flash"',
                'api_key_env = "AGENT_API_KEY"',
                'timeout_seconds = 45',
                'max_output_tokens = 2048',
                "",
                "[llm.models.domain_flash]",
                'provider = "openai_compatible"',
                'base_url = "https://api.deepseek.com/v1"',
                'model = "deepseek-v4-domain"',
                'api_key_env = "DOMAIN_API_KEY"',
                "",
                "[llm.models.summary_pro]",
                'provider = "openai_compatible"',
                'base_url = "https://api.deepseek.com/v1"',
                'model = "deepseek-v4-pro"',
                'api_key_env = "SUMMARY_API_KEY"',
                "",
                "[llm.tasks]",
                'agent_orchestration = "agent_flash"',
                'domain_classification = "domain_flash"',
                'summary_generation = "summary_pro"',
                "",
            ]
        )

    def assert_config_invalid(self, config_text):
        with self.assertRaises(KmError) as raised:
            self.load_with_config(config_text)
        self.assertEqual(raised.exception.error_code, "CONFIG_INVALID")

    def test_load_config_accepts_agent_orchestration_llm_task_model(self):
        self.set_env("AGENT_API_KEY", "agent-key")
        self.set_env("DOMAIN_API_KEY", "domain-key")
        self.set_env("SUMMARY_API_KEY", "summary-key")

        config = self.load_with_config(self.valid_agent_config_text())

        self.assertEqual(config.llm_tasks.agent_orchestration, "agent_flash")
        self.assertEqual(config.llm_tasks.domain_classification, "domain_flash")
        self.assertEqual(config.llm_tasks.summary_generation, "summary_pro")
        agent_model = config.llm_models["agent_flash"]
        self.assertEqual(agent_model.provider, "openai_compatible")
        self.assertEqual(agent_model.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(agent_model.model, "deepseek-v4-flash")
        self.assertEqual(agent_model.api_key_env, "AGENT_API_KEY")
        self.assertEqual(agent_model.api_key, "agent-key")
        self.assertEqual(agent_model.timeout_seconds, 45)
        self.assertEqual(agent_model.max_output_tokens, 2048)
        self.assertEqual(config.llm_models["domain_flash"].model, "deepseek-v4-domain")
        self.assertEqual(config.llm_models["summary_pro"].model, "deepseek-v4-pro")

    def test_agent_orchestration_model_reference_must_exist(self):
        config_text = self.valid_agent_config_text().replace(
            'agent_orchestration = "agent_flash"',
            'agent_orchestration = "missing_model"',
        )
        self.set_env("AGENT_API_KEY", "agent-key")
        self.set_env("DOMAIN_API_KEY", "domain-key")
        self.set_env("SUMMARY_API_KEY", "summary-key")

        self.assert_config_invalid(config_text)

    def test_agent_orchestration_model_requires_valid_model_fields(self):
        config_text = self.valid_agent_config_text().replace(
            'base_url = "https://api.deepseek.com/v1"\nmodel = "deepseek-v4-flash"',
            'model = "deepseek-v4-flash"',
        )
        self.set_env("AGENT_API_KEY", "agent-key")
        self.set_env("DOMAIN_API_KEY", "domain-key")
        self.set_env("SUMMARY_API_KEY", "summary-key")

        self.assert_config_invalid(config_text)

    def test_missing_agent_orchestration_is_rejected_only_for_agent_start(self):
        from km.agent_runner import ensure_agent_orchestration_configured

        self.set_env("DOMAIN_API_KEY", "domain-key")
        self.set_env("SUMMARY_API_KEY", "summary-key")
        config_text = self.valid_agent_config_text().replace(
            'agent_orchestration = "agent_flash"\n',
            "",
        ).replace(
            "[llm.models.agent_flash]\n"
            'provider = "openai_compatible"\n'
            'base_url = "https://api.deepseek.com/v1"\n'
            'model = "deepseek-v4-flash"\n'
            'api_key_env = "AGENT_API_KEY"\n'
            "timeout_seconds = 45\n"
            "max_output_tokens = 2048\n\n",
            "",
        )

        config = self.load_with_config(config_text)

        self.assertIsNone(config.llm_tasks.agent_orchestration)
        self.assertEqual(config.llm_tasks.domain_classification, "domain_flash")
        self.assertEqual(config.llm_tasks.summary_generation, "summary_pro")
        with self.assertRaises(KmError) as raised:
            ensure_agent_orchestration_configured(config)
        self.assertEqual(raised.exception.error_code, "CONFIG_INVALID")


class AgentRuntimeTests(unittest.TestCase):
    def test_agent_error_codes_are_public_recoverable_errors(self):
        from km.errors import (
            agent_invalid_transition,
            agent_orchestration_failed,
            agent_runtime_unavailable,
            agent_skill_missing,
        )

        for factory, expected in (
            (agent_runtime_unavailable, "AGENT_RUNTIME_UNAVAILABLE"),
            (agent_skill_missing, "AGENT_SKILL_MISSING"),
            (agent_invalid_transition, "AGENT_INVALID_TRANSITION"),
            (agent_orchestration_failed, "AGENT_ORCHESTRATION_FAILED"),
        ):
            with self.subTest(expected=expected):
                error = factory()
                self.assertEqual(error.error_code, expected)
                self.assertTrue(error.recoverable)
                self.assertEqual(error.exit_code, EXIT_RECOVERABLE_FAILURE)

    def test_fake_agent_runtime_returns_tool_plan_without_executing_bound_tools(self):
        from km.agent_runtime import FakeAgentRuntime

        calls = []
        runtime = FakeAgentRuntime(tool_plan=["route_url", "prepare_source_workspace"])
        result = runtime.run(
            context={"url": "https://example.com/article"},
            tools={
                "route_url": lambda: calls.append("route_url") or {"ok": True, "tool": "route_url"},
                "prepare_source_workspace": lambda: calls.append("prepare_source_workspace")
                or {"ok": True, "tool": "prepare_source_workspace"},
            },
        )

        self.assertEqual(calls, [])
        self.assertEqual(result.final_status, "completed")
        self.assertEqual([call["tool"] for call in result.tool_calls], ["route_url", "prepare_source_workspace"])
        self.assertEqual([call["status"] for call in result.tool_calls], ["planned", "planned"])
        self.assertIsNone(result.error)

    def test_deep_agents_runtime_uses_single_create_deep_agent_import_boundary(self):
        from km.agent_runtime import DeepAgentsRuntime

        captured = {}
        calls = []

        class FrameworkAgent:
            def invoke(self, payload):
                captured["payload"] = payload
                captured["planned_output"] = captured["kwargs"]["tools"][0].fn()
                return {
                    "tool_calls": [{"tool": "route_url", "ok": True}],
                    "final_status": "completed",
                    "error": None,
                }

        def create_deep_agent(**kwargs):
            captured["kwargs"] = kwargs
            return FrameworkAgent()

        def tool(name, description=None):
            def decorate(fn):
                wrapped = SimpleTool(name)
                wrapped.description = description
                wrapped.fn = fn
                return wrapped

            return decorate

        module = types.ModuleType("deepagents")
        module.create_deep_agent = create_deep_agent
        langchain_core = types.ModuleType("langchain_core")
        langchain_tools = types.ModuleType("langchain_core.tools")
        langchain_tools.tool = tool
        with mock.patch.dict(
            sys.modules,
            {
                "deepagents": module,
                "langchain_core": langchain_core,
                "langchain_core.tools": langchain_tools,
            },
        ):
            runtime = DeepAgentsRuntime(model="deepseek-v4-flash", instructions="按状态机调用受控 tools。")
            result = runtime.run(
                {"url": "https://example.com/article"},
                {"route_url": lambda: calls.append("route_url") or {"ok": True}},
            )

        self.assertEqual(result.final_status, "completed")
        self.assertEqual(result.tool_calls, [{"tool": "route_url", "ok": True}])
        self.assertEqual(calls, [])
        self.assertIn('"status": "planned"', captured["planned_output"])
        self.assertEqual(captured["payload"]["messages"][0]["role"], "user")
        self.assertIn("https://example.com/article", captured["payload"]["messages"][0]["content"])
        self.assertEqual(captured["kwargs"]["model"], "deepseek-v4-flash")
        self.assertEqual(captured["kwargs"]["system_prompt"], "按状态机调用受控 tools。")
        self.assertEqual([tool.name for tool in captured["kwargs"]["tools"]], ["route_url"])
        self.assertEqual(captured["kwargs"]["subagents"], [])

    def test_missing_real_runtime_is_mapped_to_agent_runtime_unavailable(self):
        from km.agent_runtime import DeepAgentsRuntime

        with mock.patch.dict(sys.modules, {"deepagents": None}):
            runtime = DeepAgentsRuntime(model="deepseek-v4-flash", instructions="instructions")
            with self.assertRaises(KmError) as raised:
                runtime.run({}, {})

        self.assertEqual(raised.exception.error_code, "AGENT_RUNTIME_UNAVAILABLE")

    def test_runtime_tool_filter_keeps_only_project_tools(self):
        from km.agent_runtime import ProjectToolFilterMiddleware

        route_tool = SimpleTool("route_url")
        execute_tool = SimpleTool("execute")
        request = SimpleRequest([route_tool, execute_tool])
        middleware = ProjectToolFilterMiddleware({"route_url"})

        response = middleware.wrap_model_call(request, lambda filtered: filtered.tools)

        self.assertEqual(response, [route_tool])

    def test_openai_compatible_agent_model_config_builds_langchain_chat_model(self):
        from km.agent_runtime import build_deep_agents_model
        from km.config import LlmModelConfig

        captured = {}

        class ChatOpenAI:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        module = types.ModuleType("langchain_openai")
        module.ChatOpenAI = ChatOpenAI
        model_config = LlmModelConfig(
            provider="openai_compatible",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-v4-flash",
            api_key_env="AGENT_API_KEY",
            api_key="agent-key",
            timeout_seconds=45,
            max_output_tokens=2048,
        )

        with mock.patch.dict(sys.modules, {"langchain_openai": module}):
            model = build_deep_agents_model(model_config)

        self.assertIsInstance(model, ChatOpenAI)
        self.assertEqual(captured["model"], "deepseek-v4-flash")
        self.assertEqual(captured["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(captured["api_key"], "agent-key")
        self.assertEqual(captured["timeout"], 45)
        self.assertEqual(captured["max_tokens"], 2048)


class AgentSkillLoaderTests(unittest.TestCase):
    def test_loader_reads_required_skills_and_trims_context(self):
        from km.agent_runner import load_agent_skills

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                "url-routing",
                "bilibili-ingest",
                "web-article-ingest",
                "whisper-transcription",
                "domain-classification",
                "summary-generation",
                "obsidian-write",
            ):
                path = root / "skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text(f"# {name}\n\n只调用受控 Python tools。\n" + "正文" * 3000, encoding="utf-8")

            skills = load_agent_skills(root)

        self.assertEqual(set(skills.keys()), {
            "url-routing",
            "bilibili-ingest",
            "web-article-ingest",
            "whisper-transcription",
            "domain-classification",
            "summary-generation",
            "obsidian-write",
        })
        self.assertIn("受控 Python tools", skills["url-routing"])
        self.assertLessEqual(len(skills["url-routing"]), 4000)

    def test_loader_rejects_missing_or_empty_skill(self):
        from km.agent_runner import load_agent_skills

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                "url-routing",
                "bilibili-ingest",
                "web-article-ingest",
                "whisper-transcription",
                "domain-classification",
                "summary-generation",
                "obsidian-write",
            ):
                path = root / "skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text("只调用受控 Python tools。", encoding="utf-8")
            (root / "skills" / "summary-generation" / "SKILL.md").write_text("   ", encoding="utf-8")

            with self.assertRaises(KmError) as raised:
                load_agent_skills(root)

        self.assertEqual(raised.exception.error_code, "AGENT_SKILL_MISSING")


if __name__ == "__main__":
    unittest.main()
