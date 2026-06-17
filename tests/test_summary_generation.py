import json
from pathlib import Path
import tempfile
import unittest

from km.config import LlmModelConfig
from km.errors import KmError


class FakeLlmClient:
    def __init__(self, responses=None, errors=None):
        self.responses = dict(responses or {})
        self.errors = dict(errors or {})
        self.calls = []

    def complete(self, *, model_config, prompt, system_prompt=None):
        self.calls.append((model_config.model, prompt, system_prompt))
        if model_config.model in self.errors:
            raise self.errors[model_config.model]
        return self.responses.get(model_config.model, "")


class SummaryGenerationTests(unittest.TestCase):
    def import_summary(self):
        try:
            import km.summary as summary
        except ImportError as exc:
            self.fail(f"km.summary module should exist: {exc}")
        return summary

    def llm_model(self, model="deepseek-v4-pro"):
        return LlmModelConfig(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            model=model,
            api_key_env="DEEPSEEK_API_KEY",
            api_key="test-key",
            timeout_seconds=120,
            max_output_tokens=8192,
        )

    def make_asset_dir(self, domain="AI", canonical_text="这是一篇关于 AI Agent 工具系统的文章。"):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        asset_dir = Path(root.name) / "source"
        canonical_dir = asset_dir / "canonical"
        summary_dir = asset_dir / "summary"
        canonical_dir.mkdir(parents=True)
        summary_dir.mkdir(parents=True)
        canonical_text_path = canonical_dir / "content.md"
        canonical_text_path.write_text(canonical_text, encoding="utf-8")
        domain_path = summary_dir / "domain.json"
        domain_path.write_text(
            json.dumps(
                {
                    "taxonomy_version": 1,
                    "domain": domain,
                    "confidence": 0.9,
                    "reason": "内容讨论该领域。",
                    "model_ref": "deepseek_v4_flash",
                    "model": "deepseek-v4-flash",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return asset_dir, canonical_text_path, domain_path

    def valid_model_payload(self, **overrides):
        payload = {
            "schema_version": 999,
            "domain": "AI",
            "title": "AI Agent 工具系统复盘",
            "one_sentence_summary": "文章总结了 AI Agent 工具系统的核心设计。",
            "core_points": ["Agent 需要可靠工具边界。"],
            "key_concepts": [{"name": "Agent", "explanation": "能够调用工具完成任务的系统。"}],
            "domain_notes": {
                "核心问题": "如何组织工具调用。",
                "模型或方法": "Agent 编排。",
                "工具或系统": "受控 Python tools。",
                "数据或评测": "原文未明确说明",
                "工作流影响": "降低人工整理成本。",
                "能力边界": "需要 schema 校验。",
                "可复现说明": "原文未明确说明",
            },
            "actionable_insights": ["先定义受控边界。"],
            "questions": ["如何评估不同模型总结质量？"],
            "tags": ["knowledge/AI", "topic/Agent", "tool/Python"],
            "source": {"url": "bad"},
            "input": {"truncated": True},
            "prompt": {"prompt_id": "bad"},
            "model_ref": "bad",
            "model": "bad",
        }
        payload.update(overrides)
        return json.dumps(payload, ensure_ascii=False)

    def test_prompt_assets_exist_for_all_domains(self):
        root = Path(__file__).resolve().parents[1]
        common = root / "prompts" / "summary" / "common.md"
        domain_files = (
            "ai.md",
            "programming.md",
            "product.md",
            "business.md",
            "learning.md",
            "psychology.md",
            "investing.md",
            "writing.md",
            "life.md",
            "recipe.md",
            "other.md",
        )

        self.assertTrue(common.is_file())
        self.assertIn("纯 JSON object", common.read_text(encoding="utf-8"))
        for filename in domain_files:
            with self.subTest(filename=filename):
                path = root / "prompts" / "summary" / "domains" / filename
                self.assertTrue(path.is_file())

    def test_domain_templates_include_required_domain_notes_fields(self):
        summary = self.import_summary()
        root = Path(__file__).resolve().parents[1]

        for domain, fields in summary.DOMAIN_NOTE_FIELDS.items():
            with self.subTest(domain=domain):
                template = root / "prompts" / "summary" / "domains" / f"{summary.domain_key(domain)}.md"
                content = template.read_text(encoding="utf-8")
                for field in fields:
                    self.assertIn(field, content)

    def test_parse_summary_response_accepts_valid_response_and_overrides_system_fields(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()

        parsed = summary.parse_summary_response(
            self.valid_model_payload(),
            domain="AI",
            model_ref="deepseek_v4_pro",
            model="deepseek-v4-pro",
            source_url="https://example.com/article",
            content_type="web_article",
            asset_dir=asset_dir,
            canonical_text_path=canonical_text_path,
            domain_path=domain_path,
            prompt_id="summary.ai.v1",
            truncated=False,
            max_input_chars=0,
        )

        self.assertEqual(parsed["schema_version"], 1)
        self.assertEqual(parsed["domain"], "AI")
        self.assertEqual(parsed["model_ref"], "deepseek_v4_pro")
        self.assertEqual(parsed["model"], "deepseek-v4-pro")
        self.assertEqual(parsed["source"]["url"], "https://example.com/article")
        self.assertEqual(parsed["source"]["canonical_text_path"], str(canonical_text_path))
        self.assertEqual(parsed["input"]["strategy"], "single_pass")
        self.assertFalse(parsed["input"]["truncated"])
        self.assertEqual(parsed["prompt"]["prompt_id"], "summary.ai.v1")
        self.assertEqual(parsed["questions"], ["如何评估不同模型总结质量？"])

    def test_parse_summary_response_accepts_surrounding_whitespace(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()

        parsed = summary.parse_summary_response(
            "\n  " + self.valid_model_payload() + "\n",
            domain="AI",
            model_ref="deepseek_v4_pro",
            model="deepseek-v4-pro",
            source_url="https://example.com/article",
            content_type="web_article",
            asset_dir=asset_dir,
            canonical_text_path=canonical_text_path,
            domain_path=domain_path,
            prompt_id="summary.ai.v1",
            truncated=False,
            max_input_chars=0,
        )

        self.assertEqual(parsed["title"], "AI Agent 工具系统复盘")

    def test_parse_summary_response_rejects_invalid_shapes(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        invalid_responses = (
            "不是 JSON",
            "```json\n{}\n```",
            "[]",
            self.valid_model_payload(domain="错误领域"),
            self.valid_model_payload(domain_notes={"核心问题": "缺少字段"}),
            self.valid_model_payload(tags=["topic/a/b"]),
            self.valid_model_payload(tags=["topic/"]),
            self.valid_model_payload(title="bad/title"),
            self.valid_model_payload(key_concepts=[{"name": "Agent"}]),
        )

        for raw_response in invalid_responses:
            with self.subTest(raw_response=raw_response[:40]):
                with self.assertRaises(KmError) as raised:
                    summary.parse_summary_response(
                        raw_response,
                        domain="AI",
                        model_ref="deepseek_v4_pro",
                        model="deepseek-v4-pro",
                        source_url="https://example.com/article",
                        content_type="web_article",
                        asset_dir=asset_dir,
                        canonical_text_path=canonical_text_path,
                        domain_path=domain_path,
                        prompt_id="summary.ai.v1",
                        truncated=False,
                        max_input_chars=0,
                    )
                self.assertEqual(raised.exception.error_code, "SUMMARY_SCHEMA_INVALID")

    def test_generate_summary_single_model_writes_summary_json(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        llm_client = FakeLlmClient(responses={"deepseek-v4-pro": self.valid_model_payload()})

        result = summary.generate_summary(
            canonical_text_path=canonical_text_path,
            asset_dir=asset_dir,
            source_url="https://example.com/article",
            content_type="web_article",
            domain_path=domain_path,
            llm_models={"deepseek_v4_pro": self.llm_model("deepseek-v4-pro")},
            summary_model_ref="deepseek_v4_pro",
            llm_client=llm_client,
            max_input_chars=0,
        )

        self.assertEqual(result.status, "summary_ready")
        self.assertFalse(result.evaluation_enabled)
        self.assertEqual(result.summary_model_ref, "deepseek_v4_pro")
        self.assertTrue(result.summary_path.is_file())
        self.assertFalse((asset_dir / "summary" / "evaluations").exists())
        payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["domain"], "AI")
        self.assertEqual(payload["model_ref"], "deepseek_v4_pro")
        self.assertEqual(payload["source"]["url"], "https://example.com/article")
        self.assertNotIn("领域分类器", llm_client.calls[0][2])
        self.assertIn("知识总结器", llm_client.calls[0][2])

    def test_generate_summary_evaluation_writes_candidates_and_uses_primary(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        llm_client = FakeLlmClient(
            responses={
                "deepseek-v4-flash": self.valid_model_payload(title="Flash 结果"),
                "deepseek-v4-pro": self.valid_model_payload(title="Pro 结果"),
            }
        )

        result = summary.generate_summary(
            canonical_text_path=canonical_text_path,
            asset_dir=asset_dir,
            source_url="https://example.com/article",
            content_type="web_article",
            domain_path=domain_path,
            llm_models={
                "deepseek_v4_flash": self.llm_model("deepseek-v4-flash"),
                "deepseek_v4_pro": self.llm_model("deepseek-v4-pro"),
            },
            summary_model_ref="deepseek_v4_pro",
            llm_client=llm_client,
            max_input_chars=0,
            evaluation=summary.SummaryEvaluationConfig(
                enabled=True,
                candidate_models=("deepseek_v4_flash", "deepseek_v4_pro"),
                primary_model="deepseek_v4_pro",
            ),
        )

        self.assertTrue(result.evaluation_enabled)
        self.assertEqual(result.title, "Pro 结果")
        self.assertEqual(result.evaluation_dir, asset_dir / "summary" / "evaluations")
        self.assertTrue((result.evaluation_dir / "deepseek_v4_flash.json").is_file())
        self.assertTrue((result.evaluation_dir / "deepseek_v4_pro.json").is_file())
        payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["title"], "Pro 结果")

    def test_generate_summary_non_primary_failure_still_succeeds(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        llm_client = FakeLlmClient(
            responses={"deepseek-v4-pro": self.valid_model_payload()},
            errors={"deepseek-v4-flash": RuntimeError("network")},
        )

        result = summary.generate_summary(
            canonical_text_path=canonical_text_path,
            asset_dir=asset_dir,
            source_url="https://example.com/article",
            content_type="web_article",
            domain_path=domain_path,
            llm_models={
                "deepseek_v4_flash": self.llm_model("deepseek-v4-flash"),
                "deepseek_v4_pro": self.llm_model("deepseek-v4-pro"),
            },
            summary_model_ref="deepseek_v4_pro",
            llm_client=llm_client,
            max_input_chars=0,
            evaluation=summary.SummaryEvaluationConfig(
                enabled=True,
                candidate_models=("deepseek_v4_flash", "deepseek_v4_pro"),
                primary_model="deepseek_v4_pro",
            ),
        )

        self.assertEqual(result.status, "summary_ready")
        failure = json.loads((result.evaluation_dir / "deepseek_v4_flash.json").read_text(encoding="utf-8"))
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["error_code"], "LLM_REQUEST_FAILED")

    def test_generate_summary_primary_failure_does_not_overwrite_existing_summary(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        existing_summary = asset_dir / "summary" / "summary.json"
        existing_summary.write_text('{"old": true}', encoding="utf-8")
        llm_client = FakeLlmClient(
            responses={"deepseek-v4-flash": self.valid_model_payload(title="Flash 结果")},
            errors={"deepseek-v4-pro": RuntimeError("network")},
        )

        with self.assertRaises(KmError) as raised:
            summary.generate_summary(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                source_url="https://example.com/article",
                content_type="web_article",
                domain_path=domain_path,
                llm_models={
                    "deepseek_v4_flash": self.llm_model("deepseek-v4-flash"),
                    "deepseek_v4_pro": self.llm_model("deepseek-v4-pro"),
                },
                summary_model_ref="deepseek_v4_pro",
                llm_client=llm_client,
                max_input_chars=0,
                evaluation=summary.SummaryEvaluationConfig(
                    enabled=True,
                    candidate_models=("deepseek_v4_flash", "deepseek_v4_pro"),
                    primary_model="deepseek_v4_pro",
                ),
            )

        self.assertEqual(raised.exception.error_code, "LLM_REQUEST_FAILED")
        self.assertEqual(existing_summary.read_text(encoding="utf-8"), '{"old": true}')

    def test_generate_summary_single_model_failure_does_not_overwrite_existing_summary(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        existing_summary = asset_dir / "summary" / "summary.json"
        existing_summary.write_text('{"old": true}', encoding="utf-8")
        llm_client = FakeLlmClient(errors={"deepseek-v4-pro": RuntimeError("network")})

        with self.assertRaises(KmError) as raised:
            summary.generate_summary(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                source_url="https://example.com/article",
                content_type="web_article",
                domain_path=domain_path,
                llm_models={"deepseek_v4_pro": self.llm_model("deepseek-v4-pro")},
                summary_model_ref="deepseek_v4_pro",
                llm_client=llm_client,
                max_input_chars=0,
            )

        self.assertEqual(raised.exception.error_code, "LLM_REQUEST_FAILED")
        self.assertEqual(existing_summary.read_text(encoding="utf-8"), '{"old": true}')

    def test_generate_summary_maps_input_and_context_limit_failures(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        domain_path.unlink()

        with self.assertRaises(KmError) as raised:
            summary.generate_summary(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                source_url="https://example.com/article",
                content_type="web_article",
                domain_path=domain_path,
                llm_models={"deepseek_v4_pro": self.llm_model("deepseek-v4-pro")},
                summary_model_ref="deepseek_v4_pro",
                llm_client=FakeLlmClient(),
                max_input_chars=0,
            )

        self.assertEqual(raised.exception.error_code, "SUMMARY_INPUT_INVALID")

    def test_generate_summary_maps_context_limit_failure(self):
        summary = self.import_summary()
        asset_dir, canonical_text_path, domain_path = self.make_asset_dir()
        llm_client = FakeLlmClient(errors={"deepseek-v4-pro": RuntimeError("maximum context length exceeded")})

        with self.assertRaises(KmError) as raised:
            summary.generate_summary(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                source_url="https://example.com/article",
                content_type="web_article",
                domain_path=domain_path,
                llm_models={"deepseek_v4_pro": self.llm_model("deepseek-v4-pro")},
                summary_model_ref="deepseek_v4_pro",
                llm_client=llm_client,
                max_input_chars=0,
            )

        self.assertEqual(raised.exception.error_code, "SUMMARY_INPUT_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
