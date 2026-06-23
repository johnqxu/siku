import json
from pathlib import Path
import tempfile
import unittest

from km.errors import KmError


class AgentToolResultTests(unittest.TestCase):
    def test_success_failure_and_skip_results_have_uniform_shape(self):
        from km.agent_state import ToolResult

        success = ToolResult.success(
            tool="route_url",
            status="routed",
            stage_before="initialized",
            stage_after="routed",
            content_type="web_article",
            normalized_url="https://example.com/article",
        )
        failure = ToolResult.failure(
            tool="write_obsidian_note",
            stage_before="text_ready",
            error_code="AGENT_INVALID_TRANSITION",
            message="非法状态转换。",
            recoverable=True,
        )
        skipped = ToolResult.success(
            tool="prepare_source_workspace",
            status="skipped_existing",
            stage_before="routed",
            stage_after="processed_ready",
            skipped=True,
            skip_reason="processed_existing",
        )

        self.assertEqual(success.to_dict()["ok"], True)
        self.assertEqual(success.to_dict()["tool"], "route_url")
        self.assertEqual(success.to_dict()["stage_after"], "routed")
        self.assertFalse(success.to_dict()["skipped"])
        self.assertNotIn("stdout", success.to_dict())
        self.assertEqual(failure.to_dict()["ok"], False)
        self.assertEqual(failure.to_dict()["status"], "failed")
        self.assertEqual(failure.to_dict()["stage_after"], "text_ready")
        self.assertEqual(failure.to_dict()["error_code"], "AGENT_INVALID_TRANSITION")
        self.assertTrue(failure.to_dict()["recoverable"])
        self.assertTrue(skipped.to_dict()["skipped"])
        self.assertEqual(skipped.to_dict()["skip_reason"], "processed_existing")


class AgentStateMachineTests(unittest.TestCase):
    def test_guard_allows_full_valid_path(self):
        from km.agent_state import AgentState, AgentStateGuard, ToolResult

        state = AgentState(
            source_id="source-1",
            original_url="https://example.com/article",
            normalized_url="https://example.com/article",
        )
        guard = AgentStateGuard(state)
        calls = []

        for tool, stage_after in (
            ("route_url", "routed"),
            ("prepare_source_workspace", "workspace_ready"),
            ("collect_web_article_text", "text_ready"),
            ("classify_domain", "domain_ready"),
            ("generate_summary", "summary_ready"),
            ("write_obsidian_note", "note_ready"),
            ("mark_source_processed", "processed_ready"),
        ):
            with self.subTest(tool=tool):
                result = guard.call(
                    tool,
                    lambda tool=tool, stage_after=stage_after: calls.append(tool)
                    or ToolResult.success(
                        tool=tool,
                        status=stage_after,
                        stage_before=guard.state.stage,
                        stage_after=stage_after,
                    ),
                )
                self.assertTrue(result.ok)
                self.assertEqual(guard.state.stage, stage_after)

        self.assertEqual(
            calls,
            [
                "route_url",
                "prepare_source_workspace",
                "collect_web_article_text",
                "classify_domain",
                "generate_summary",
                "write_obsidian_note",
                "mark_source_processed",
            ],
        )

    def test_guard_allows_processed_existing_skip_from_routed(self):
        from km.agent_state import AgentState, AgentStateGuard, ToolResult

        state = AgentState(
            source_id="source-1",
            original_url="https://example.com/article",
            normalized_url="https://example.com/article",
            stage="routed",
        )
        guard = AgentStateGuard(state)

        result = guard.call(
            "prepare_source_workspace",
            lambda: ToolResult.success(
                tool="prepare_source_workspace",
                status="skipped_existing",
                stage_before="routed",
                stage_after="processed_ready",
                skipped=True,
                skip_reason="processed_existing",
            ),
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "processed_existing")
        self.assertEqual(guard.state.stage, "processed_ready")

    def test_guard_rejects_invalid_transition_without_side_effect(self):
        from km.agent_state import AgentState, AgentStateGuard

        state = AgentState(
            source_id="source-1",
            original_url="https://example.com/article",
            normalized_url="https://example.com/article",
            stage="text_ready",
        )
        guard = AgentStateGuard(state)
        side_effects = []

        result = guard.call("write_obsidian_note", lambda: side_effects.append("write"))

        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "AGENT_INVALID_TRANSITION")
        self.assertEqual(result.stage_before, "text_ready")
        self.assertEqual(result.stage_after, "text_ready")
        self.assertEqual(guard.state.stage, "text_ready")
        self.assertEqual(side_effects, [])


class AgentStatePersistenceTests(unittest.TestCase):
    def test_state_json_contains_required_fields_and_overwrites_latest_snapshot(self):
        from km.agent_state import AgentState, AgentStateStore

        with tempfile.TemporaryDirectory() as tmp:
            asset_dir = Path(tmp) / "source"
            store = AgentStateStore(asset_dir)
            state = AgentState(
                source_id="source-1",
                original_url="https://example.com/article?secret=not-trace-content",
                normalized_url="https://example.com/article",
                content_type="web_article",
                asset_dir=str(asset_dir),
                canonical_text_path=str(asset_dir / "canonical" / "content.md"),
                stage="text_ready",
                error_code="WEB_FETCH_FAILED",
                error_message="上次抓取失败。",
            )

            store.write_state(state)
            state.stage = "domain_ready"
            state.error_code = None
            state.error_message = None
            state.domain_path = str(asset_dir / "summary" / "domain.json")
            store.write_state(state)

            payload = json.loads((asset_dir / "agent" / "state.json").read_text(encoding="utf-8"))

        for key in (
            "schema_version",
            "orchestrator",
            "source_id",
            "original_url",
            "normalized_url",
            "content_type",
            "stage",
            "asset_dir",
            "canonical_text_path",
            "domain_path",
            "summary_path",
            "note_path",
            "error_code",
            "error_message",
            "updated_at",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["stage"], "domain_ready")
        self.assertIsNone(payload["error_code"])
        self.assertIsNone(payload["error_message"])
        self.assertEqual(payload["orchestrator"], "deep_agents")

    def test_trace_jsonl_is_append_only_json_and_sanitized(self):
        from km.agent_state import AgentTraceWriter, ToolResult

        with tempfile.TemporaryDirectory() as tmp:
            asset_dir = Path(tmp) / "source"
            writer = AgentTraceWriter(asset_dir, run_id="run-1")
            writer.run_started({"url": "https://example.com/article", "api_key": "secret-key"})
            writer.tool_attempt(
                step=1,
                result=ToolResult.failure(
                    tool="collect_web_article_text",
                    stage_before="workspace_ready",
                    error_code="WEB_FETCH_FAILED",
                    message="网页抓取失败。",
                    recoverable=True,
                    html="<html>" + "正文" * 200 + "</html>",
                    prompt="请总结：" + "内容" * 200,
                    model_output="模型输出" * 200,
                    cookie="session=secret",
                    env={"DEEPSEEK_API_KEY": "secret-key"},
                ),
                attempt=1,
            )
            writer.run_failed("WEB_FETCH_FAILED", "网页抓取失败。")
            trace_path = asset_dir / "agent" / "trace.jsonl"
            lines = trace_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 3)
        events = [json.loads(line) for line in lines]
        self.assertEqual([event["event"] for event in events], ["run_started", "tool_attempt", "run_failed"])
        self.assertTrue(all(event["run_id"] == "run-1" for event in events))
        self.assertTrue(all(isinstance(event, dict) for event in events))
        serialized = "\n".join(lines)
        self.assertNotIn("secret-key", serialized)
        self.assertNotIn("session=secret", serialized)
        self.assertNotIn("<html>", serialized)
        self.assertNotIn("请总结", serialized)
        self.assertNotIn("模型输出", serialized)

    def test_trace_tool_attempt_records_skip_reason_and_required_fields(self):
        from km.agent_state import AgentTraceWriter, ToolResult

        with tempfile.TemporaryDirectory() as tmp:
            asset_dir = Path(tmp) / "source"
            writer = AgentTraceWriter(asset_dir, run_id="run-1")
            writer.tool_attempt(
                step=2,
                result=ToolResult.success(
                    tool="prepare_source_workspace",
                    status="skipped_existing",
                    stage_before="routed",
                    stage_after="processed_ready",
                    skipped=True,
                    skip_reason="processed_existing",
                ),
                attempt=1,
            )
            event = json.loads((asset_dir / "agent" / "trace.jsonl").read_text(encoding="utf-8"))

        for key in (
            "timestamp",
            "run_id",
            "step",
            "tool",
            "attempt",
            "stage_before",
            "stage_after",
            "status",
            "skipped",
            "error_code",
            "message",
        ):
            self.assertIn(key, event)
        self.assertEqual(event["skip_reason"], "processed_existing")


if __name__ == "__main__":
    unittest.main()
