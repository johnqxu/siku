import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from km.__main__ import main
from km.errors import KmError
from km.index import IngestIndex
from km.url_state import generate_source_id, normalize_url


class CliContractTests(unittest.TestCase):
    def make_env_with_config(self, config_text=None):
        env, _ = self.make_env_and_paths_with_config(config_text)
        return env

    def make_env_and_paths_with_config(self, config_text=None):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)

        if config_text is None:
            config_text = "\n".join(
                [
                    f'vault_path = "{root_path / "vault"}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    f'asset_store_path = "{root_path / "assets"}"',
                    "",
                ]
            )

        config = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        self.addCleanup(lambda path=config.name: os.path.exists(path) and os.unlink(path))
        with config:
            config.write(config_text)

        env = os.environ.copy()
        env["KM_CONFIG"] = config.name
        return env, root_path

    def config_text_with_llm(self, root_path):
        return "\n".join(
            [
                f'vault_path = "{root_path / "vault"}"',
                'inbox_dir = "Inbox/Knowledge"',
                f'asset_store_path = "{root_path / "assets"}"',
                "",
                "[llm.models.deepseek_flash]",
                'provider = "openai_compatible"',
                'base_url = "https://api.deepseek.com/v1"',
                'model = "deepseek-v4-flash"',
                'api_key_env = "DEEPSEEK_API_KEY"',
                "",
                "[llm.models.deepseek_pro]",
                'provider = "openai_compatible"',
                'base_url = "https://api.deepseek.com/v1"',
                'model = "deepseek-v4-pro"',
                'api_key_env = "DEEPSEEK_API_KEY"',
                "",
                "[llm.tasks]",
                'domain_classification = "deepseek_flash"',
                'summary_generation = "deepseek_pro"',
                "",
            ]
        )

    def config_text_with_domain_only_llm(self, root_path):
        return "\n".join(
            [
                f'vault_path = "{root_path / "vault"}"',
                'inbox_dir = "Inbox/Knowledge"',
                f'asset_store_path = "{root_path / "assets"}"',
                "",
                "[llm.models.deepseek_flash]",
                'provider = "openai_compatible"',
                'base_url = "https://api.deepseek.com/v1"',
                'model = "deepseek-v4-flash"',
                'api_key_env = "DEEPSEEK_API_KEY"',
                "",
                "[llm.tasks]",
                'domain_classification = "deepseek_flash"',
                "",
            ]
        )

    def make_env_and_paths_with_llm_config(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)
        env, _ = self.make_env_and_paths_with_config(self.config_text_with_llm(root_path))
        env["DEEPSEEK_API_KEY"] = "test-key"
        return env, root_path

    def write_valid_programming_summary(self, root_path):
        asset_dir = root_path / "assets" / "source"
        canonical_text_path = asset_dir / "canonical" / "content.md"
        domain_path = asset_dir / "summary" / "domain.json"
        summary_path = asset_dir / "summary" / "summary.json"
        canonical_text_path.parent.mkdir(parents=True)
        summary_path.parent.mkdir(parents=True)
        canonical_text_path.write_text("Python 调试实践正文。", encoding="utf-8")
        domain_path.write_text("{}", encoding="utf-8")
        summary_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "domain": "编程",
                    "title": "Python 调试实践",
                    "one_sentence_summary": "这是一篇关于 Python 调试实践的总结。",
                    "core_points": ["先复现问题，再定位根因。"],
                    "key_concepts": [{"name": "断点调试", "explanation": "用于观察运行时状态。"}],
                    "domain_notes": {
                        "问题背景": "需要定位 Python 程序中的异常行为。",
                        "技术机制": "通过日志、断点和最小复现缩小范围。",
                        "工具或框架": "pytest 与调试器。",
                        "实现细节": "保留可重复执行的测试用例。",
                        "调试与验证": "修复后运行相关测试验证。",
                        "性能或安全": "避免在生产日志中泄露敏感信息。",
                        "适用边界": "适用于常规应用调试场景。",
                    },
                    "actionable_insights": ["把失败用例固化成回归测试。"],
                    "questions": ["如何降低复现成本？"],
                    "tags": ["knowledge/python"],
                    "source": {
                        "url": "https://example.com/article",
                        "content_type": "web_article",
                        "asset_dir": str(asset_dir),
                        "canonical_text_path": str(canonical_text_path),
                        "domain_path": str(domain_path),
                    },
                    "input": {
                        "canonical_text_path": str(canonical_text_path),
                        "domain_path": str(domain_path),
                        "strategy": "single_pass",
                        "truncated": False,
                        "max_input_chars": 0,
                    },
                    "prompt": {"prompt_id": "summary.programming.v1", "domain": "编程"},
                    "model_ref": "deepseek_pro",
                    "model": "deepseek-v4-pro",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return asset_dir, canonical_text_path, domain_path, summary_path

    def run_cli(self, payload, env=None):
        return subprocess.run(
            [sys.executable, "-m", "km", "ingest"],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def run_public_cli(self, payload, env=None):
        executable_dir = "Scripts" if os.name == "nt" else "bin"
        script_name = "km.exe" if os.name == "nt" else "km"
        command = Path(sys.prefix) / executable_dir / script_name
        if not command.exists():
            self.fail("km console script missing; run tests with `uv run` after `uv sync`.")

        return subprocess.run(
            [str(command), "ingest"],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def parse_stdout_json(self, result):
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"stdout was not a JSON object: {result.stdout!r}; stderr={result.stderr!r}; {exc}")

    def test_missing_url_returns_input_invalid(self):
        result = self.run_cli("{}")

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        self.assertIn("message", response)
        self.assertFalse(response["recoverable"])

    def test_blank_url_returns_input_invalid(self):
        result = self.run_cli('{"url":"   "}', env=self.make_env_with_config())

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        self.assertFalse(response["recoverable"])

    def test_public_km_command_matches_contract(self):
        result = self.run_public_cli('{"url":"https://www.bilibili.com/read/cv123"}', env=self.make_env_with_config())

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertEqual(result.stderr, "")
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "UNSUPPORTED_URL")

    def test_missing_mode_defaults_to_ingest_and_reaches_business_boundary(self):
        result = self.run_cli('{"url":"https://www.bilibili.com/read/cv123"}', env=self.make_env_with_config())

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "UNSUPPORTED_URL")
        self.assertFalse(response["recoverable"])

    def test_unsupported_url_returns_public_error(self):
        result = self.run_cli('{"url":"https://www.bilibili.com/read/cv123"}', env=self.make_env_with_config())

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "UNSUPPORTED_URL")
        self.assertFalse(response["recoverable"])

    def test_supported_bilibili_video_returns_processed_ready(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://www.bilibili.com/video/BV1xx411c7mD"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_bilibili_transcript") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
            mock.patch("km.__main__.process_obsidian_note", create=True) as process_note,
        ):
            collect.return_value.status = "transcript_ready"
            collect.return_value.content_type = "bilibili_video"
            collect.return_value.source_url = "https://www.bilibili.com/video/BV1xx411c7mD"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/transcript.md"
            collect.return_value.asset_manifest = {
                "metadata": "/tmp/assets/source/raw/metadata.json",
                "canonical_text": "/tmp/assets/source/canonical/transcript.md",
            }
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="AI",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            generate_summary.return_value = SimpleNamespace(
                status="summary_ready",
                summary_path=Path("/tmp/assets/source/summary/summary.json"),
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="AI",
                title="AI Agent 工具系统复盘",
                summary_model_ref="deepseek_pro",
                evaluation_enabled=False,
                evaluation_dir=None,
            )
            process_note.return_value = {
                "ok": True,
                "status": "processed_ready",
                "note_path": "/tmp/vault/Inbox/AI-Agent.md",
                "content_type": "bilibili_video",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "asset_dir": "/tmp/assets/source",
                "canonical_text_path": "/tmp/assets/source/canonical/transcript.md",
                "domain_path": "/tmp/assets/source/summary/domain.json",
                "summary_path": "/tmp/assets/source/summary/summary.json",
                "domain": "AI",
                "title": "AI Agent 工具系统复盘",
            }
            exit_code = main()

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "processed_ready")
        self.assertEqual(response["content_type"], "bilibili_video")
        self.assertEqual(response["canonical_text_path"], "/tmp/assets/source/canonical/transcript.md")
        self.assertEqual(response["domain_path"], "/tmp/assets/source/summary/domain.json")
        self.assertEqual(response["summary_path"], "/tmp/assets/source/summary/summary.json")
        self.assertEqual(response["note_path"], "/tmp/vault/Inbox/AI-Agent.md")
        self.assertEqual(response["domain"], "AI")
        self.assertEqual(response["title"], "AI Agent 工具系统复盘")
        self.assertNotIn("summary_model_ref", response)
        self.assertNotIn("evaluation_enabled", response)
        self.assertNotIn("evaluation_dir", response)
        self.assertNotIn("taxonomy_version", response)
        self.assertNotIn("model_ref", response)
        collect.assert_called_once()
        classify.assert_called_once()
        generate_summary.assert_called_once()
        process_note.assert_called_once()

    def test_supported_web_article_returns_processed_ready(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
            mock.patch("km.__main__.process_obsidian_note", create=True) as process_note,
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            collect.return_value.asset_manifest = {
                "html": "/tmp/assets/source/raw/page.html",
                "metadata": "/tmp/assets/source/raw/metadata.json",
                "canonical_text": "/tmp/assets/source/canonical/content.md",
            }
            collect.return_value.parser_id = "generic_article"
            collect.return_value.fetch_method = "http"
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            generate_summary.return_value = SimpleNamespace(
                status="summary_ready",
                summary_path=Path("/tmp/assets/source/summary/summary.json"),
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                title="Python 调试实践",
                summary_model_ref="deepseek_pro",
                evaluation_enabled=True,
                evaluation_dir=Path("/tmp/assets/source/summary/evaluations"),
            )
            process_note.return_value = {
                "ok": True,
                "status": "processed_ready",
                "note_path": "/tmp/vault/Inbox/Python.md",
                "content_type": "web_article",
                "source_url": "https://example.com/article",
                "asset_dir": "/tmp/assets/source",
                "canonical_text_path": "/tmp/assets/source/canonical/content.md",
                "domain_path": "/tmp/assets/source/summary/domain.json",
                "summary_path": "/tmp/assets/source/summary/summary.json",
                "domain": "编程",
                "title": "Python 调试实践",
            }
            exit_code = main()

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "processed_ready")
        self.assertEqual(response["content_type"], "web_article")
        self.assertEqual(response["canonical_text_path"], "/tmp/assets/source/canonical/content.md")
        self.assertEqual(response["domain_path"], "/tmp/assets/source/summary/domain.json")
        self.assertEqual(response["summary_path"], "/tmp/assets/source/summary/summary.json")
        self.assertEqual(response["note_path"], "/tmp/vault/Inbox/Python.md")
        self.assertEqual(response["domain"], "编程")
        self.assertEqual(response["title"], "Python 调试实践")
        self.assertNotIn("summary_model_ref", response)
        self.assertNotIn("evaluation_enabled", response)
        self.assertNotIn("evaluation_dir", response)
        collect.assert_called_once()
        classify.assert_called_once()
        generate_summary.assert_called_once()
        process_note.assert_called_once()

    def test_web_article_failure_returns_recoverable_error(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch(
                "km.__main__.collect_web_article",
                side_effect=__import__("km.errors").errors.KmError("WEB_PARSE_FAILED", "网页解析失败。", True, 2),
            ),
        ):
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "WEB_PARSE_FAILED")
        self.assertTrue(response["recoverable"])

    def test_web_article_failure_does_not_call_domain_classification(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch(
                "km.__main__.collect_web_article",
                side_effect=KmError("WEB_PARSE_FAILED", "网页解析失败。", True, 2),
            ),
            mock.patch("km.__main__.classify_domain", create=True) as classify,
        ):
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "WEB_PARSE_FAILED")
        classify.assert_not_called()

    def test_domain_classification_request_failure_returns_recoverable_error(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch(
                "km.__main__.classify_domain",
                side_effect=KmError("LLM_REQUEST_FAILED", "LLM 请求失败。", True, 2),
            ),
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "LLM_REQUEST_FAILED")
        self.assertTrue(response["recoverable"])
        generate_summary.assert_not_called()

    def test_domain_classification_schema_failure_returns_recoverable_error(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch(
                "km.__main__.classify_domain",
                side_effect=KmError("LLM_SCHEMA_INVALID", "LLM schema 无效。", True, 2),
            ),
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "LLM_SCHEMA_INVALID")
        self.assertTrue(response["recoverable"])

    def test_supported_url_without_domain_llm_task_returns_config_invalid(self):
        env, _ = self.make_env_and_paths_with_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            exit_code = main()

        self.assertEqual(exit_code, 1)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "CONFIG_INVALID")
        self.assertFalse(response["recoverable"])
        classify.assert_not_called()
        generate_summary.assert_not_called()

    def test_supported_url_without_summary_llm_task_does_not_collect_or_classify(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)
        env, _ = self.make_env_and_paths_with_config(self.config_text_with_domain_only_llm(root_path))
        env["DEEPSEEK_API_KEY"] = "test-key"

        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
        ):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "CONFIG_INVALID")
        collect.assert_not_called()
        classify.assert_not_called()
        generate_summary.assert_not_called()

    def test_successful_pipeline_marks_processed_source(self):
        env, root_path = self.make_env_and_paths_with_llm_config()
        normalized = normalize_url("https://example.com/article")
        asset_dir = root_path / "assets" / "source"
        canonical_text_path = asset_dir / "canonical" / "content.md"
        domain_path = asset_dir / "summary" / "domain.json"
        summary_path = asset_dir / "summary" / "summary.json"
        canonical_text_path.parent.mkdir(parents=True)
        summary_path.parent.mkdir(parents=True)
        (root_path / "vault").mkdir(parents=True)
        canonical_text_path.write_text("Python 调试实践正文。", encoding="utf-8")
        domain_path.write_text("{}", encoding="utf-8")
        summary_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "domain": "编程",
                    "title": "Python 调试实践",
                    "one_sentence_summary": "这是一篇关于 Python 调试实践的总结。",
                    "core_points": ["先复现问题，再定位根因。"],
                    "key_concepts": [{"name": "断点调试", "explanation": "用于观察运行时状态。"}],
                    "domain_notes": {
                        "问题背景": "需要定位 Python 程序中的异常行为。",
                        "技术机制": "通过日志、断点和最小复现缩小范围。",
                        "工具或框架": "pytest 与调试器。",
                        "实现细节": "保留可重复执行的测试用例。",
                        "调试与验证": "修复后运行相关测试验证。",
                        "性能或安全": "避免在生产日志中泄露敏感信息。",
                        "适用边界": "适用于常规应用调试场景。",
                    },
                    "actionable_insights": ["把失败用例固化成回归测试。"],
                    "questions": ["如何降低复现成本？"],
                    "tags": ["knowledge/python"],
                    "source": {
                        "url": "https://example.com/article",
                        "content_type": "web_article",
                        "asset_dir": str(asset_dir),
                        "canonical_text_path": str(canonical_text_path),
                        "domain_path": str(domain_path),
                    },
                    "input": {
                        "canonical_text_path": str(canonical_text_path),
                        "domain_path": str(domain_path),
                        "strategy": "single_pass",
                        "truncated": False,
                        "max_input_chars": 0,
                    },
                    "prompt": {"prompt_id": "summary.programming.v1", "domain": "编程"},
                    "model_ref": "deepseek_pro",
                    "model": "deepseek-v4-pro",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout"),
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = asset_dir
            collect.return_value.canonical_text_path = canonical_text_path
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=domain_path,
                domain="编程",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            generate_summary.return_value = SimpleNamespace(
                status="summary_ready",
                summary_path=summary_path,
                domain_path=domain_path,
                domain="编程",
                title="Python 调试实践",
                summary_model_ref="deepseek_pro",
                evaluation_enabled=False,
                evaluation_dir=None,
            )
            exit_code = main()

        self.assertEqual(exit_code, 0)
        with sqlite3.connect(root_path / "assets" / "index.sqlite") as connection:
            row = connection.execute(
                "SELECT status, domain, note_path FROM sources WHERE normalized_url = ?",
                (normalized.normalized_url,),
            ).fetchone()
        self.assertEqual(row[0], "processed")
        self.assertEqual(row[1], "编程")
        self.assertTrue(row[2].endswith("-Python-调试实践.md"))
        self.assertTrue(Path(row[2]).is_file())

    def test_summary_generation_failure_returns_recoverable_error(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch(
                "km.__main__.generate_summary",
                side_effect=KmError("SUMMARY_SCHEMA_INVALID", "总结 schema 无效。", True, 2),
                create=True,
            ),
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "SUMMARY_SCHEMA_INVALID")
        self.assertTrue(response["recoverable"])

    def test_obsidian_write_failure_returns_recoverable_error(self):
        env, _ = self.make_env_and_paths_with_llm_config()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
            mock.patch(
                "km.__main__.process_obsidian_note",
                side_effect=KmError("OBSIDIAN_WRITE_FAILED", "Obsidian 写入失败。", True, 2),
                create=True,
            ),
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            generate_summary.return_value = SimpleNamespace(
                status="summary_ready",
                summary_path=Path("/tmp/assets/source/summary/summary.json"),
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                title="Python 调试实践",
                summary_model_ref="deepseek_pro",
                evaluation_enabled=False,
                evaluation_dir=None,
            )
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "OBSIDIAN_WRITE_FAILED")
        self.assertTrue(response["recoverable"])
        self.assertNotIn("note_path", response)

    def test_obsidian_write_failure_records_failed_source(self):
        env, root_path = self.make_env_and_paths_with_llm_config()
        normalized = normalize_url("https://example.com/article")
        asset_dir, canonical_text_path, domain_path, summary_path = self.write_valid_programming_summary(root_path)
        vault_path = root_path / "vault"
        vault_path.mkdir(parents=True)
        (vault_path / "Inbox").write_text("不是目录", encoding="utf-8")

        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = asset_dir
            collect.return_value.canonical_text_path = canonical_text_path
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=domain_path,
                domain="编程",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            generate_summary.return_value = SimpleNamespace(
                status="summary_ready",
                summary_path=summary_path,
                domain_path=domain_path,
                domain="编程",
                title="Python 调试实践",
                summary_model_ref="deepseek_pro",
                evaluation_enabled=False,
                evaluation_dir=None,
            )
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "OBSIDIAN_WRITE_FAILED")
        with sqlite3.connect(root_path / "assets" / "index.sqlite") as connection:
            row = connection.execute(
                "SELECT status, error_code, note_path FROM sources WHERE normalized_url = ?",
                (normalized.normalized_url,),
            ).fetchone()
        self.assertEqual(row[0], "failed")
        self.assertEqual(row[1], "OBSIDIAN_WRITE_FAILED")
        self.assertIsNone(row[2])

    def test_index_write_failure_returns_note_path(self):
        env, _ = self.make_env_and_paths_with_llm_config()

        class IndexWriteFailed(KmError):
            @property
            def note_path(self):
                return "/tmp/vault/Inbox/Python.md"

        error = IndexWriteFailed("INDEX_WRITE_FAILED", "SQLite processed 状态写入失败。", True, 2)
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com/article"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.collect_web_article") as collect,
            mock.patch("km.__main__.classify_domain", create=True) as classify,
            mock.patch("km.__main__.generate_summary", create=True) as generate_summary,
            mock.patch("km.__main__.process_obsidian_note", side_effect=error, create=True),
        ):
            collect.return_value.status = "content_ready"
            collect.return_value.content_type = "web_article"
            collect.return_value.source_url = "https://example.com/article"
            collect.return_value.asset_dir = "/tmp/assets/source"
            collect.return_value.canonical_text_path = "/tmp/assets/source/canonical/content.md"
            classify.return_value = SimpleNamespace(
                status="domain_ready",
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                taxonomy_version=1,
                model_ref="deepseek_flash",
            )
            generate_summary.return_value = SimpleNamespace(
                status="summary_ready",
                summary_path=Path("/tmp/assets/source/summary/summary.json"),
                domain_path=Path("/tmp/assets/source/summary/domain.json"),
                domain="编程",
                title="Python 调试实践",
                summary_model_ref="deepseek_pro",
                evaluation_enabled=False,
                evaluation_dir=None,
            )
            exit_code = main()

        self.assertEqual(exit_code, 2)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INDEX_WRITE_FAILED")
        self.assertTrue(response["recoverable"])
        self.assertEqual(response["note_path"], "/tmp/vault/Inbox/Python.md")

    def test_invalid_mode_returns_input_invalid(self):
        result = self.run_cli(
            '{"url":"https://example.com","mode":"dry_run"}',
            env=self.make_env_with_config(),
        )

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")

    def test_missing_config_returns_config_invalid(self):
        env = os.environ.copy()
        env["KM_CONFIG"] = "/tmp/km-config-that-does-not-exist.toml"

        result = self.run_cli('{"url":"https://example.com"}', env=env)

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "CONFIG_INVALID")
        self.assertFalse(response["recoverable"])

    def test_invalid_toml_config_returns_config_invalid(self):
        result = self.run_cli(
            '{"url":"https://example.com"}',
            env=self.make_env_with_config("not valid = ["),
        )

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "CONFIG_INVALID")
        self.assertFalse(response["recoverable"])

    def test_non_http_url_returns_input_invalid(self):
        result = self.run_cli('{"url":"ftp://example.com/file"}', env=self.make_env_with_config())

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")

    def test_valid_request_initializes_local_state_before_unsupported_url(self):
        env, root_path = self.make_env_and_paths_with_config()
        normalized = normalize_url("https://www.bilibili.com/read/cv123")
        source_id = generate_source_id(normalized.normalized_url)

        result = self.run_cli('{"url":"https://www.bilibili.com/read/cv123"}', env=env)

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "UNSUPPORTED_URL")
        asset_root = root_path / "assets"
        self.assertTrue((asset_root / "index.sqlite").is_file())
        self.assertTrue((asset_root / source_id / "raw").is_dir())
        self.assertTrue((asset_root / source_id / "canonical").is_dir())
        self.assertTrue((asset_root / source_id / "summary").is_dir())

    def test_duplicate_processed_source_returns_skipped_existing(self):
        env, root_path = self.make_env_and_paths_with_config()
        asset_root = root_path / "assets"
        index = IngestIndex(asset_root / "index.sqlite")
        index.initialize()
        normalized = normalize_url("https://EXAMPLE.com/article?a=1#fragment")
        source_id = generate_source_id(normalized.normalized_url)
        asset_dir = str(asset_root / source_id)
        with sqlite3.connect(index.path) as connection:
            connection.execute(
                """
                INSERT INTO sources (
                  id, normalized_url, original_url, content_type, domain, title,
                  note_path, asset_dir, created_at, updated_at, status,
                  error_code, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    normalized.normalized_url,
                    "https://EXAMPLE.com/article?a=1#fragment",
                    "web_article",
                    "编程",
                    "title",
                    "/vault/Inbox/Knowledge/title.md",
                    asset_dir,
                    "2026-06-14T00:00:00Z",
                    "2026-06-14T00:00:00Z",
                    "processed",
                    None,
                    None,
                ),
            )

        result = self.run_cli('{"url":"https://EXAMPLE.com/article?a=1#fragment"}', env=env)

        self.assertEqual(result.returncode, 0)
        response = self.parse_stdout_json(result)
        self.assertTrue(response["ok"])
        self.assertEqual(response["status"], "skipped_existing")
        self.assertEqual(response["note_path"], "/vault/Inbox/Knowledge/title.md")
        self.assertEqual(response["asset_dir"], asset_dir)
        self.assertEqual(response["source_url"], "https://EXAMPLE.com/article?a=1#fragment")

    def test_malformed_json_returns_input_invalid(self):
        result = self.run_cli("{")

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        self.assertFalse(response["recoverable"])

    def test_stdout_is_single_json_object_for_valid_request(self):
        result = self.run_cli('{"url":"https://www.bilibili.com/read/cv123"}', env=self.make_env_with_config())

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertEqual(response["error_code"], "UNSUPPORTED_URL")

    def test_diagnostics_do_not_write_to_stdout(self):
        result = self.run_cli('{"url":"https://www.bilibili.com/read/cv123"}', env=self.make_env_with_config())

        self.assertNotIn("Traceback", result.stdout)
        response = self.parse_stdout_json(result)
        self.assertEqual(response["error_code"], "UNSUPPORTED_URL")

    def test_unexpected_exception_still_returns_json_stdout(self):
        with (
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com"}'),
            mock.patch("km.__main__.load_config", side_effect=RuntimeError("boom")),
            mock.patch("sys.stdout") as stdout,
            mock.patch("sys.stderr"),
        ):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()
