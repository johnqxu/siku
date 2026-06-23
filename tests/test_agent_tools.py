import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from km.config import LlmModelConfig, LlmTasksConfig, SummaryConfig
from km.index import IngestIndex
from km.agent_state import AgentState
from km.url_state import generate_source_id, normalize_url


class AgentToolboxTests(unittest.TestCase):
    def make_config(self, root_path):
        return SimpleNamespace(
            vault_path=root_path / "vault",
            inbox_dir="Inbox/Knowledge",
            asset_store_path=root_path / "assets",
            whisper_model_dir="models/whisper",
            whisper_model_size="medium",
            whisper_device="GPU",
            llm_models={
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

    def test_route_url_returns_only_routing_metadata(self):
        from km.agent_tools import AgentToolbox

        state = AgentState(original_url=" HTTPS://Example.com/Article#section ")
        toolbox = AgentToolbox(state=state, config=SimpleNamespace())

        result = toolbox.route_url()
        payload = result.to_dict()

        self.assertTrue(result.ok)
        self.assertEqual(result.stage_before, "initialized")
        self.assertEqual(result.stage_after, "routed")
        self.assertEqual(payload["normalized_url"], "https://example.com/Article")
        self.assertEqual(payload["content_type"], "web_article")
        self.assertNotIn("source_id", payload)
        self.assertNotIn("asset_dir", payload)

    def test_prepare_source_workspace_initializes_asset_index_state_and_trace_paths(self):
        from km.agent_tools import AgentToolbox

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            state = AgentState(
                original_url="https://example.com/article",
                normalized_url="https://example.com/article",
                content_type="web_article",
                stage="routed",
            )
            toolbox = AgentToolbox(state=state, config=config, run_id="run-1")

            result = toolbox.prepare_source_workspace()
            payload = result.to_dict()

            self.assertTrue(result.ok)
            self.assertEqual(result.stage_after, "workspace_ready")
            self.assertEqual(payload["source_id"], generate_source_id("https://example.com/article"))
            self.assertTrue(Path(payload["asset_dir"]).is_dir())
            self.assertTrue((Path(payload["asset_dir"]) / "agent").is_dir())
            self.assertTrue((root_path / "assets" / "index.sqlite").is_file())
            self.assertTrue(payload["state_path"].endswith("/agent/state.json"))
            self.assertTrue(payload["trace_path"].endswith("/agent/trace.jsonl"))

    def test_prepare_source_workspace_skips_processed_duplicate(self):
        from km.agent_tools import AgentToolbox

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            normalized = normalize_url("https://example.com/article").normalized_url
            source_id = generate_source_id(normalized)
            asset_dir = root_path / "assets" / source_id
            index = IngestIndex(root_path / "assets" / "index.sqlite")
            index.initialize()
            index.mark_processed(
                source_id=source_id,
                normalized_url=normalized,
                original_url="https://example.com/article",
                content_type="web_article",
                domain="编程",
                title="Python 调试实践",
                note_path=str(root_path / "vault" / "Inbox" / "Python.md"),
                asset_dir=str(asset_dir),
                now="2026-06-19T12:00:00+08:00",
            )
            state = AgentState(
                original_url="https://example.com/article",
                normalized_url=normalized,
                content_type="web_article",
                stage="routed",
            )
            toolbox = AgentToolbox(state=state, config=config, run_id="run-1")

            result = toolbox.prepare_source_workspace()

            self.assertTrue(result.ok)
            self.assertTrue(result.skipped)
            self.assertEqual(result.status, "skipped_existing")
            self.assertEqual(result.stage_after, "processed_ready")
            self.assertEqual(result.skip_reason, "processed_existing")
            self.assertEqual(result.to_dict()["note_path"], str(root_path / "vault" / "Inbox" / "Python.md"))

    def test_collect_text_tools_call_existing_pipelines_or_reuse_valid_canonical_text(self):
        from km.agent_tools import AgentToolbox

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            asset_dir = root_path / "assets" / "source"
            canonical_path = asset_dir / "canonical" / "content.md"
            canonical_path.parent.mkdir(parents=True)
            canonical_path.write_text("# 已有正文\n\n正文。", encoding="utf-8")
            state = AgentState(
                original_url="https://example.com/article",
                normalized_url="https://example.com/article",
                content_type="web_article",
                stage="workspace_ready",
                asset_dir=str(asset_dir),
            )
            calls = []
            toolbox = AgentToolbox(
                state=state,
                config=config,
                web_collector=lambda **kwargs: calls.append(kwargs) or None,
            )

            reused = toolbox.collect_web_article_text()

            self.assertTrue(reused.ok)
            self.assertTrue(reused.skipped)
            self.assertEqual(reused.stage_after, "text_ready")
            self.assertEqual(reused.to_dict()["canonical_text_path"], str(canonical_path))
            self.assertEqual(calls, [])

            canonical_path.unlink()
            collected = toolbox.collect_web_article_text()

            self.assertTrue(collected.ok)
            self.assertEqual(collected.to_dict()["canonical_text_path"], str(asset_dir / "canonical" / "content.md"))
            self.assertEqual(len(calls), 1)

    def test_collect_bilibili_text_calls_existing_pipeline(self):
        from km.agent_tools import AgentToolbox

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            asset_dir = root_path / "assets" / "source"
            state = AgentState(
                original_url="https://www.bilibili.com/video/BV1xx411c7mD",
                normalized_url="https://www.bilibili.com/video/BV1xx411c7mD",
                content_type="bilibili_video",
                stage="workspace_ready",
                asset_dir=str(asset_dir),
            )
            calls = []
            transcript_path = asset_dir / "canonical" / "transcript.md"
            toolbox = AgentToolbox(
                state=state,
                config=config,
                bilibili_collector=lambda **kwargs: calls.append(kwargs)
                or SimpleNamespace(canonical_text_path=transcript_path),
            )

            result = toolbox.collect_bilibili_text()

            self.assertTrue(result.ok)
            self.assertEqual(result.stage_after, "text_ready")
            self.assertEqual(result.to_dict()["canonical_text_path"], str(transcript_path))
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["source_url"], "https://www.bilibili.com/video/BV1xx411c7mD")

    def test_classify_and_summary_tools_call_business_llms_or_reuse_valid_json(self):
        from km.agent_tools import AgentToolbox

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            asset_dir = root_path / "assets" / "source"
            canonical_path = asset_dir / "canonical" / "content.md"
            domain_path = asset_dir / "summary" / "domain.json"
            summary_path = asset_dir / "summary" / "summary.json"
            canonical_path.parent.mkdir(parents=True)
            summary_path.parent.mkdir(parents=True)
            canonical_path.write_text("# 正文", encoding="utf-8")
            domain_path.write_text(
                json.dumps(
                    {
                        "taxonomy_version": 1,
                        "domain": "AI",
                        "confidence": 0.9,
                        "reason": "讨论 AI。",
                        "model_ref": "domain_model",
                        "model": "domain-model",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "domain": "AI",
                        "title": "AI Agent 工具系统复盘",
                        "source": {
                            "url": "https://example.com/article",
                            "content_type": "web_article",
                            "asset_dir": str(asset_dir),
                            "canonical_text_path": str(canonical_path),
                            "domain_path": str(domain_path),
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            state = AgentState(
                original_url="https://example.com/article",
                normalized_url="https://example.com/article",
                content_type="web_article",
                stage="text_ready",
                asset_dir=str(asset_dir),
                canonical_text_path=str(canonical_path),
            )
            calls = []
            toolbox = AgentToolbox(
                state=state,
                config=config,
                domain_classifier=lambda **kwargs: calls.append(("domain", kwargs)) or None,
                summary_generator=lambda **kwargs: calls.append(("summary", kwargs)) or None,
            )

            domain = toolbox.classify_domain()
            self.assertTrue(domain.ok)
            self.assertTrue(domain.skipped)
            self.assertEqual(domain.stage_after, "domain_ready")
            self.assertEqual(domain.to_dict()["domain"], "AI")

            state.stage = "domain_ready"
            state.domain_path = str(domain_path)
            summary = toolbox.generate_summary()
            self.assertTrue(summary.ok)
            self.assertTrue(summary.skipped)
            self.assertEqual(summary.stage_after, "summary_ready")
            self.assertEqual(summary.to_dict()["title"], "AI Agent 工具系统复盘")
            self.assertEqual(calls, [])

    def test_write_obsidian_note_and_mark_processed_use_controlled_boundaries(self):
        from km.agent_tools import AgentToolbox

        with tempfile.TemporaryDirectory() as tmp:
            root_path = Path(tmp)
            config = self.make_config(root_path)
            config.vault_path.mkdir()
            asset_dir = root_path / "assets" / "source"
            canonical_path = asset_dir / "canonical" / "content.md"
            domain_path = asset_dir / "summary" / "domain.json"
            summary_path = asset_dir / "summary" / "summary.json"
            canonical_path.parent.mkdir(parents=True)
            summary_path.parent.mkdir(parents=True)
            canonical_path.write_text("# 正文", encoding="utf-8")
            domain_path.write_text("{}", encoding="utf-8")
            summary_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "domain": "编程",
                        "title": "Python 调试实践",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            state = AgentState(
                source_id="source",
                original_url="https://example.com/article",
                normalized_url="https://example.com/article",
                content_type="web_article",
                stage="summary_ready",
                asset_dir=str(asset_dir),
                canonical_text_path=str(canonical_path),
                domain_path=str(domain_path),
                summary_path=str(summary_path),
            )
            writer_calls = []
            toolbox = AgentToolbox(
                state=state,
                config=config,
                obsidian_writer=lambda **kwargs: writer_calls.append(kwargs)
                or SimpleNamespace(note_path=root_path / "vault" / "Inbox" / "Python.md"),
                summary_loader=lambda **kwargs: {
                    "schema_version": 1,
                    "domain": "编程",
                    "title": "Python 调试实践",
                },
                now_factory=lambda: "2026-06-19T12:00:00+08:00",
            )

            note = toolbox.write_obsidian_note()
            self.assertTrue(note.ok)
            self.assertEqual(note.stage_after, "note_ready")
            self.assertEqual(note.to_dict()["note_path"], str(root_path / "vault" / "Inbox" / "Python.md"))
            self.assertEqual(len(writer_calls), 1)

            state.stage = "note_ready"
            state.note_path = note.to_dict()["note_path"]
            processed = toolbox.mark_source_processed()
            self.assertTrue(processed.ok)
            self.assertEqual(processed.stage_after, "processed_ready")

            index = IngestIndex(root_path / "assets" / "index.sqlite")
            duplicate = index.find_processed_source("https://example.com/article")
            self.assertIsNotNone(duplicate)
            self.assertEqual(duplicate.note_path, str(root_path / "vault" / "Inbox" / "Python.md"))


if __name__ == "__main__":
    unittest.main()
