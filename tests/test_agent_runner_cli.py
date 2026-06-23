import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from km.agent_runtime import FakeAgentRuntime
from km.config import LlmModelConfig, LlmTasksConfig, SummaryConfig
from km.errors import KmError
from km.__main__ import main


class AgentRunnerTests(unittest.TestCase):
    def make_config(self, root_path):
        return SimpleNamespace(
            vault_path=root_path / "vault",
            inbox_dir="Inbox/Knowledge",
            asset_store_path=root_path / "assets",
            whisper_model_dir="models/whisper",
            whisper_model_size="medium",
            whisper_device="GPU",
            llm_models={
                "agent_model": LlmModelConfig(
                    provider="openai_compatible",
                    base_url="https://api.example.com/v1",
                    model="agent-model",
                    api_key_env="AGENT_KEY",
                    api_key="agent-key",
                ),
                "domain_model": LlmModelConfig(
                    provider="openai_compatible",
                    base_url="https://api.example.com/v1",
                    model="domain-model",
                    api_key_env="DOMAIN_KEY",
                    api_key="domain-key",
                ),
                "summary_model": LlmModelConfig(
                    provider="openai_compatible",
                    base_url="https://api.example.com/v1",
                    model="summary-model",
                    api_key_env="SUMMARY_KEY",
                    api_key="summary-key",
                ),
            },
            llm_tasks=LlmTasksConfig(
                agent_orchestration="agent_model",
                domain_classification="domain_model",
                summary_generation="summary_model",
            ),
            summary=SummaryConfig(max_input_chars=0),
        )

    def test_runner_success_builds_agent_envelope_from_final_state(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            config.vault_path.mkdir()
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(
                    [
                        "route_url",
                        "prepare_source_workspace",
                        "collect_web_article_text",
                        "classify_domain",
                        "generate_summary",
                        "write_obsidian_note",
                        "mark_source_processed",
                    ]
                ),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: StubToolbox(**kwargs, root_path=root_path),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article", "extra": "ignored"})

            self.assertTrue(response["ok"])
            self.assertEqual(response["status"], "processed_ready")
            self.assertEqual(response["orchestrator"], "deep_agents")
            self.assertEqual(response["content_type"], "web_article")
            self.assertEqual(response["source_url"], "https://example.com/article")
            self.assertTrue(response["asset_dir"].endswith("/assets/source"))
            self.assertTrue(response["canonical_text_path"].endswith("/canonical/content.md"))
            self.assertTrue(response["domain_path"].endswith("/summary/domain.json"))
            self.assertTrue(response["summary_path"].endswith("/summary/summary.json"))
            self.assertTrue(response["note_path"].endswith("/vault/Inbox/Python.md"))
            self.assertTrue(response["trace_path"].endswith("/agent/trace.jsonl"))
            self.assertTrue(response["state_path"].endswith("/agent/state.json"))
            self.assertEqual(response["domain"], "编程")
            self.assertEqual(response["title"], "Python 调试实践")
            self.assertTrue(Path(response["trace_path"]).is_file())
            self.assertTrue(Path(response["state_path"]).is_file())
            trace = Path(response["trace_path"]).read_text(encoding="utf-8")
            self.assertIn("run_started", trace)
            self.assertIn("run_finished", trace)

    def test_runner_duplicate_source_returns_skipped_existing_and_stops_after_prepare(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(["route_url", "prepare_source_workspace"]),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: StubToolbox(**kwargs, root_path=root_path, duplicate=True),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertTrue(response["ok"])
            self.assertEqual(response["status"], "skipped_existing")
            self.assertEqual(response["orchestrator"], "deep_agents")
            self.assertEqual(response["note_path"], str(root_path / "vault" / "Inbox" / "Python.md"))
            self.assertTrue(response["trace_path"].endswith("/agent/trace.jsonl"))
            trace = Path(response["trace_path"]).read_text(encoding="utf-8")
            self.assertIn("processed_existing", trace)

    def test_runner_skips_duplicate_planned_tool_after_successful_execution(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            config.vault_path.mkdir()
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(
                    [
                        "route_url",
                        "prepare_source_workspace",
                        "route_url",
                        "collect_web_article_text",
                        "classify_domain",
                        "generate_summary",
                        "write_obsidian_note",
                        "mark_source_processed",
                    ]
                ),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: StubToolbox(**kwargs, root_path=root_path),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertTrue(response["ok"])
            self.assertEqual(response["status"], "processed_ready")
            trace = Path(response["trace_path"]).read_text(encoding="utf-8")
            self.assertNotIn("AGENT_INVALID_TRANSITION", trace)

    def test_runner_retries_retryable_error_once(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            toolbox = RetryToolbox(root_path=root_path)
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(
                    [
                        "route_url",
                        "prepare_source_workspace",
                        "collect_web_article_text",
                        "classify_domain",
                        "generate_summary",
                        "write_obsidian_note",
                        "mark_source_processed",
                    ]
                ),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: toolbox.bind(**kwargs),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertTrue(response["ok"])
            self.assertEqual(response["status"], "processed_ready")
            self.assertEqual(toolbox.collect_attempts, 2)
            trace = Path(response["trace_path"]).read_text(encoding="utf-8")
            self.assertIn('"attempt": 1', trace)
            self.assertIn('"attempt": 2', trace)

    def test_runner_retries_bilibili_transcript_only_when_tool_marks_retryable(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            retryable_toolbox = BilibiliRetryToolbox(root_path=root_path, retryable=True)
            retryable_runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(
                    [
                        "route_url",
                        "prepare_source_workspace",
                        "collect_bilibili_text",
                        "classify_domain",
                        "generate_summary",
                        "write_obsidian_note",
                        "mark_source_processed",
                    ]
                ),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: retryable_toolbox.bind(**kwargs),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            retryable_response = retryable_runner.run({"url": "https://www.bilibili.com/video/BV1xx411c7mD"})

            self.assertTrue(retryable_response["ok"])
            self.assertEqual(retryable_toolbox.collect_attempts, 2)

            non_retryable_toolbox = BilibiliRetryToolbox(root_path=root_path / "second", retryable=False)
            non_retryable_runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(["route_url", "prepare_source_workspace", "collect_bilibili_text"]),
                run_id_factory=lambda: "run-2",
                toolbox_factory=lambda **kwargs: non_retryable_toolbox.bind(**kwargs),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            non_retryable_response = non_retryable_runner.run({"url": "https://www.bilibili.com/video/BV1xx411c7mD"})

            self.assertFalse(non_retryable_response["ok"])
            self.assertEqual(non_retryable_response["error_code"], "BILIBILI_TRANSCRIPT_FAILED")
            self.assertEqual(non_retryable_toolbox.collect_attempts, 1)

    def test_runner_does_not_retry_schema_whisper_write_or_config_errors(self):
        from km.agent_runner import AgentIngestRunner

        for error_code in (
            "LLM_SCHEMA_INVALID",
            "SUMMARY_SCHEMA_INVALID",
            "SUMMARY_INPUT_INVALID",
            "WHISPER_UNAVAILABLE",
            "OBSIDIAN_WRITE_FAILED",
            "INDEX_WRITE_FAILED",
            "CONFIG_INVALID",
        ):
            with self.subTest(error_code=error_code), tempfile.TemporaryDirectory() as tmp:
                root_path = Path(tmp)
                config = self.make_config(root_path)
                toolbox = SingleFailureToolbox(root_path=root_path, error_code=error_code)
                runner = AgentIngestRunner(
                    config=config,
                    runtime=FakeAgentRuntime(["route_url", "prepare_source_workspace", "collect_web_article_text"]),
                    run_id_factory=lambda: "run-1",
                    toolbox_factory=lambda **kwargs: toolbox.bind(**kwargs),
                    skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
                )

                response = runner.run({"url": "https://example.com/article"})

                self.assertFalse(response["ok"])
                self.assertEqual(response["error_code"], error_code)
                self.assertEqual(toolbox.collect_attempts, 1)

    def test_runner_max_tool_steps_returns_orchestration_failed(self):
        from km.agent_runner import AgentIngestRunner, MAX_TOOL_STEPS

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(["route_url"] * (MAX_TOOL_STEPS + 1)),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: StubToolbox(**kwargs, root_path=root_path),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertFalse(response["ok"])
            self.assertEqual(response["error_code"], "AGENT_ORCHESTRATION_FAILED")

    def test_runner_treats_unfinished_intermediate_stage_as_orchestration_failure(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(["route_url", "prepare_source_workspace", "collect_web_article_text"]),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: StubToolbox(**kwargs, root_path=root_path),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertFalse(response["ok"])
            self.assertEqual(response["error_code"], "AGENT_ORCHESTRATION_FAILED")
            self.assertTrue(response["recoverable"])
            self.assertEqual(response["orchestrator"], "deep_agents")

    def test_runner_does_not_retry_invalid_transition(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(["write_obsidian_note"]),
                run_id_factory=lambda: "run-1",
                toolbox_factory=lambda **kwargs: StubToolbox(**kwargs, root_path=root_path),
                skill_loader=lambda: {"url-routing": "只调用受控 tools。"},
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertFalse(response["ok"])
            self.assertEqual(response["error_code"], "AGENT_INVALID_TRANSITION")
            self.assertTrue(response["recoverable"])
            self.assertEqual(response["orchestrator"], "deep_agents")

    def test_runner_missing_skill_returns_agent_skill_missing_before_runtime(self):
        from km.agent_runner import AgentIngestRunner

        with tempfile.TemporaryDirectory() as tmp:
            config = self.make_config(Path(tmp))
            runner = AgentIngestRunner(
                config=config,
                runtime=FakeAgentRuntime(["route_url"]),
                skill_loader=lambda: (_ for _ in ()).throw(KmError("AGENT_SKILL_MISSING", "缺少 skill。", True, 2)),
            )

            response = runner.run({"url": "https://example.com/article"})

            self.assertFalse(response["ok"])
            self.assertEqual(response["error_code"], "AGENT_SKILL_MISSING")
            self.assertNotIn("trace_path", response)


class AgentCliTests(unittest.TestCase):
    def make_config_file(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)
        config_path = root_path / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    f'vault_path = "{root_path / "vault"}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    f'asset_store_path = "{root_path / "assets"}"',
                    "",
                    "[llm.models.agent_model]",
                    'provider = "openai_compatible"',
                    'base_url = "https://api.example.com/v1"',
                    'model = "agent-model"',
                    'api_key_env = "AGENT_KEY"',
                    "",
                    "[llm.tasks]",
                    'agent_orchestration = "agent_model"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return config_path

    def test_agent_ingest_cli_reads_stdin_json_and_writes_single_json_object(self):
        config_path = self.make_config_file()
        fake_response = {
            "ok": True,
            "status": "processed_ready",
            "orchestrator": "deep_agents",
            "trace_path": "/tmp/trace.jsonl",
            "state_path": "/tmp/state.json",
        }
        with (
            mock.patch.dict(os.environ, {"KM_CONFIG": str(config_path), "AGENT_KEY": "key"}, clear=True),
            mock.patch("sys.argv", ["km", "agent-ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article","mode":"ingest","force":true}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.AgentIngestRunner") as runner_class,
        ):
            runner_class.return_value.run.return_value = fake_response
            exit_code = main()

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertEqual(output.count("\n"), 1)
        self.assertEqual(json.loads(output), fake_response)
        runner_class.return_value.run.assert_called_once()
        self.assertEqual(runner_class.return_value.run.call_args.args[0]["url"], "https://example.com/article")

    def test_agent_ingest_cli_runtime_unavailable_returns_exit_2(self):
        config_path = self.make_config_file()
        error_response = {
            "ok": False,
            "error_code": "AGENT_RUNTIME_UNAVAILABLE",
            "message": "Deep Agents runtime 不可用。",
            "recoverable": True,
        }
        with (
            mock.patch.dict(os.environ, {"KM_CONFIG": str(config_path), "AGENT_KEY": "key"}, clear=True),
            mock.patch("sys.argv", ["km", "agent-ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.AgentIngestRunner") as runner_class,
        ):
            runner_class.return_value.run.return_value = error_response
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertEqual(json.loads(output)["error_code"], "AGENT_RUNTIME_UNAVAILABLE")


class StubToolbox:
    def __init__(self, *, state, root_path, duplicate=False, **kwargs):
        from km.agent_state import AgentStateStore, AgentTraceWriter, ToolResult

        self.state = state
        self.root_path = root_path
        self.duplicate = duplicate
        self.ToolResult = ToolResult
        asset_dir = root_path / "assets" / "source"
        self.state_store = AgentStateStore(asset_dir)
        self.trace_writer = AgentTraceWriter(asset_dir, run_id="run-1")

    def as_tools(self):
        return {
            "route_url": self.route_url,
            "prepare_source_workspace": self.prepare_source_workspace,
            "collect_web_article_text": self.collect_web_article_text,
            "classify_domain": self.classify_domain,
            "generate_summary": self.generate_summary,
            "write_obsidian_note": self.write_obsidian_note,
            "mark_source_processed": self.mark_source_processed,
        }

    def route_url(self):
        self.state.normalized_url = "https://example.com/article"
        self.state.content_type = "web_article"
        return self.ToolResult.success(
            tool="route_url",
            status="routed",
            stage_before=self.state.stage,
            stage_after="routed",
            normalized_url="https://example.com/article",
            content_type="web_article",
        )

    def prepare_source_workspace(self):
        asset_dir = self.root_path / "assets" / "source"
        asset_dir.mkdir(parents=True, exist_ok=True)
        self.state.source_id = "source"
        self.state.asset_dir = str(asset_dir)
        if self.duplicate:
            return self.ToolResult.success(
                tool="prepare_source_workspace",
                status="skipped_existing",
                stage_before=self.state.stage,
                stage_after="processed_ready",
                skipped=True,
                skip_reason="processed_existing",
                source_id="source",
                asset_dir=str(asset_dir),
                note_path=str(self.root_path / "vault" / "Inbox" / "Python.md"),
                source_url="https://example.com/article",
                state_path=str(self.state_store.state_path),
                trace_path=str(self.trace_writer.trace_path),
            )
        return self.ToolResult.success(
            tool="prepare_source_workspace",
            status="workspace_ready",
            stage_before=self.state.stage,
            stage_after="workspace_ready",
            source_id="source",
            asset_dir=str(asset_dir),
            state_path=str(self.state_store.state_path),
            trace_path=str(self.trace_writer.trace_path),
        )

    def collect_web_article_text(self):
        path = self.root_path / "assets" / "source" / "canonical" / "content.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 正文", encoding="utf-8")
        return self.ToolResult.success(
            tool="collect_web_article_text",
            status="text_ready",
            stage_before=self.state.stage,
            stage_after="text_ready",
            canonical_text_path=str(path),
        )

    def classify_domain(self):
        path = self.root_path / "assets" / "source" / "summary" / "domain.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"domain":"编程"}', encoding="utf-8")
        return self.ToolResult.success(
            tool="classify_domain",
            status="domain_ready",
            stage_before=self.state.stage,
            stage_after="domain_ready",
            domain_path=str(path),
            domain="编程",
        )

    def generate_summary(self):
        path = self.root_path / "assets" / "source" / "summary" / "summary.json"
        path.write_text('{"domain":"编程","title":"Python 调试实践"}', encoding="utf-8")
        return self.ToolResult.success(
            tool="generate_summary",
            status="summary_ready",
            stage_before=self.state.stage,
            stage_after="summary_ready",
            summary_path=str(path),
            domain="编程",
            title="Python 调试实践",
        )

    def write_obsidian_note(self):
        path = self.root_path / "vault" / "Inbox" / "Python.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Python", encoding="utf-8")
        return self.ToolResult.success(
            tool="write_obsidian_note",
            status="note_ready",
            stage_before=self.state.stage,
            stage_after="note_ready",
            note_path=str(path),
            domain="编程",
            title="Python 调试实践",
        )

    def mark_source_processed(self):
        return self.ToolResult.success(
            tool="mark_source_processed",
            status="processed_ready",
            stage_before=self.state.stage,
            stage_after="processed_ready",
            note_path=str(self.root_path / "vault" / "Inbox" / "Python.md"),
            domain="编程",
            title="Python 调试实践",
        )


class RetryToolbox(StubToolbox):
    def __init__(self, *, root_path):
        self.root_path = root_path
        self.collect_attempts = 0

    def bind(self, **kwargs):
        StubToolbox.__init__(self, root_path=self.root_path, **kwargs)
        return self

    def collect_web_article_text(self):
        self.collect_attempts += 1
        if self.collect_attempts == 1:
            return self.ToolResult.failure(
                tool="collect_web_article_text",
                stage_before=self.state.stage,
                error_code="WEB_FETCH_FAILED",
                message="网页抓取失败。",
                recoverable=True,
                retryable=True,
            )
        return super().collect_web_article_text()


class BilibiliRetryToolbox(StubToolbox):
    def __init__(self, *, root_path, retryable):
        self.root_path = root_path
        self.retryable = retryable
        self.collect_attempts = 0

    def bind(self, **kwargs):
        StubToolbox.__init__(self, root_path=self.root_path, **kwargs)
        return self

    def route_url(self):
        self.state.normalized_url = "https://www.bilibili.com/video/BV1xx411c7mD"
        self.state.content_type = "bilibili_video"
        return self.ToolResult.success(
            tool="route_url",
            status="routed",
            stage_before=self.state.stage,
            stage_after="routed",
            normalized_url="https://www.bilibili.com/video/BV1xx411c7mD",
            content_type="bilibili_video",
        )

    def as_tools(self):
        tools = super().as_tools()
        tools["collect_bilibili_text"] = self.collect_bilibili_text
        return tools

    def collect_bilibili_text(self):
        self.collect_attempts += 1
        if self.collect_attempts == 1:
            return self.ToolResult.failure(
                tool="collect_bilibili_text",
                stage_before=self.state.stage,
                error_code="BILIBILI_TRANSCRIPT_FAILED",
                message="Bilibili 文本生成失败。",
                recoverable=True,
                retryable=self.retryable,
                retry_reason="download_transient" if self.retryable else None,
            )
        path = self.root_path / "assets" / "source" / "canonical" / "transcript.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# 转写", encoding="utf-8")
        return self.ToolResult.success(
            tool="collect_bilibili_text",
            status="text_ready",
            stage_before=self.state.stage,
            stage_after="text_ready",
            canonical_text_path=str(path),
        )


class SingleFailureToolbox(StubToolbox):
    def __init__(self, *, root_path, error_code):
        self.root_path = root_path
        self.error_code = error_code
        self.collect_attempts = 0

    def bind(self, **kwargs):
        StubToolbox.__init__(self, root_path=self.root_path, **kwargs)
        return self

    def collect_web_article_text(self):
        self.collect_attempts += 1
        return self.ToolResult.failure(
            tool="collect_web_article_text",
            stage_before=self.state.stage,
            error_code=self.error_code,
            message=f"{self.error_code} failed",
            recoverable=True,
        )


if __name__ == "__main__":
    unittest.main()
