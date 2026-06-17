import json
from pathlib import Path
import tempfile
import unittest

from km.config import LlmModelConfig
from km.domain import (
    CLASSIFICATION_TEXT_LIMIT,
    OpenAiCompatibleLlmClient,
    build_domain_classification_prompt,
    classify_domain,
    parse_domain_classification_response,
)
from km.errors import KmError


class FakeLlmClient:
    def __init__(self, *, response=None, error=None):
        self.response = response
        self.error = error
        self.last_prompt = ""

    def complete(self, *, model_config, prompt):
        self.last_prompt = prompt
        if self.error is not None:
            raise self.error
        return self.response or ""


class FakeHttpResponse:
    def __init__(self, *, payload=None, error=None):
        self.payload = payload or {}
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class FakeHttpxModule:
    def __init__(self, response):
        self.response = response
        self.last_post = None

    def post(self, url, *, timeout, headers, json):
        self.last_post = {
            "url": url,
            "timeout": timeout,
            "headers": headers,
            "json": json,
        }
        return self.response


class DomainClassificationTests(unittest.TestCase):
    def make_asset_dir_with_text(self, filename="content.md"):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        asset_dir = Path(root.name) / "source"
        canonical_dir = asset_dir / "canonical"
        canonical_dir.mkdir(parents=True)
        canonical_text_path = canonical_dir / filename
        canonical_text_path.write_text("# 标题\n\n这篇文章讨论 Agent 工具调用和模型编排。", encoding="utf-8")
        return asset_dir, canonical_text_path

    def llm_model(self):
        return LlmModelConfig(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            model="deepseek-v4-flash",
            api_key_env="DEEPSEEK_API_KEY",
            api_key="test-key",
        )

    def test_parse_domain_classification_response_accepts_valid_response(self):
        parsed = parse_domain_classification_response(
            '{"domain":"AI","confidence":0.86,"reason":"内容讨论大模型 Agent。"}',
            model_ref="deepseek_flash",
            model="deepseek-v4-flash",
        )

        self.assertEqual(parsed.domain, "AI")
        self.assertEqual(parsed.taxonomy_version, 1)
        self.assertEqual(parsed.confidence, 0.86)
        self.assertEqual(parsed.reason, "内容讨论大模型 Agent。")
        self.assertEqual(parsed.model_ref, "deepseek_flash")
        self.assertEqual(parsed.model, "deepseek-v4-flash")

    def test_parse_domain_classification_response_rejects_non_json(self):
        with self.assertRaises(KmError) as raised:
            parse_domain_classification_response(
                "不是 JSON",
                model_ref="deepseek_flash",
                model="deepseek-v4-flash",
            )

        self.assertEqual(raised.exception.error_code, "LLM_SCHEMA_INVALID")

    def test_parse_domain_classification_response_rejects_missing_field(self):
        with self.assertRaises(KmError) as raised:
            parse_domain_classification_response(
                '{"domain":"AI","confidence":0.86}',
                model_ref="deepseek_flash",
                model="deepseek-v4-flash",
            )

        self.assertEqual(raised.exception.error_code, "LLM_SCHEMA_INVALID")

    def test_parse_domain_classification_response_rejects_unknown_domain(self):
        with self.assertRaises(KmError) as raised:
            parse_domain_classification_response(
                '{"domain":"音乐","confidence":0.86,"reason":"内容讨论音乐。"}',
                model_ref="deepseek_flash",
                model="deepseek-v4-flash",
            )

        self.assertEqual(raised.exception.error_code, "LLM_SCHEMA_INVALID")

    def test_parse_domain_classification_response_rejects_invalid_confidence(self):
        with self.assertRaises(KmError) as raised:
            parse_domain_classification_response(
                '{"domain":"AI","confidence":"high","reason":"内容讨论大模型。"}',
                model_ref="deepseek_flash",
                model="deepseek-v4-flash",
            )

        self.assertEqual(raised.exception.error_code, "LLM_SCHEMA_INVALID")

    def test_parse_domain_classification_response_rejects_non_finite_confidence(self):
        for raw_response in (
            '{"domain":"AI","confidence":NaN,"reason":"内容讨论大模型。"}',
            '{"domain":"AI","confidence":Infinity,"reason":"内容讨论大模型。"}',
            '{"domain":"AI","confidence":-Infinity,"reason":"内容讨论大模型。"}',
        ):
            with self.subTest(raw_response=raw_response):
                with self.assertRaises(KmError) as raised:
                    parse_domain_classification_response(
                        raw_response,
                        model_ref="deepseek_flash",
                        model="deepseek-v4-flash",
                    )

                self.assertEqual(raised.exception.error_code, "LLM_SCHEMA_INVALID")

    def test_domain_classification_prompt_requires_fixed_single_domain_and_chinese_reason(self):
        prompt = build_domain_classification_prompt("这是一段测试文本。")

        self.assertIn("固定领域表", prompt)
        self.assertIn("只能选一个主领域", prompt)
        self.assertIn("reason 必须使用中文", prompt)
        for domain in ("AI", "编程", "产品", "商业", "学习", "心理学", "投资", "写作", "生活", "菜谱", "其他"):
            self.assertIn(domain, prompt)

    def test_domain_classification_prompt_truncates_long_text_with_notice(self):
        long_text = "甲" * CLASSIFICATION_TEXT_LIMIT + "乙" * 100

        prompt = build_domain_classification_prompt(long_text)

        self.assertIn("规范文本已截断", prompt)
        self.assertIn("甲" * CLASSIFICATION_TEXT_LIMIT, prompt)
        self.assertNotIn("乙", prompt)

    def test_classify_domain_writes_domain_json(self):
        asset_dir, canonical_text_path = self.make_asset_dir_with_text()
        llm_client = FakeLlmClient(
            response='{"domain":"AI","confidence":0.86,"reason":"内容主要讨论大模型 Agent。"}'
        )

        result = classify_domain(
            canonical_text_path=canonical_text_path,
            asset_dir=asset_dir,
            llm_model=self.llm_model(),
            model_ref="deepseek_flash",
            llm_client=llm_client,
        )

        self.assertEqual(result.status, "domain_ready")
        self.assertEqual(result.domain, "AI")
        self.assertEqual(result.taxonomy_version, 1)
        self.assertEqual(result.model_ref, "deepseek_flash")
        self.assertTrue(result.domain_path.is_file())
        self.assertFalse((asset_dir / "summary" / "domain.md").exists())
        payload = json.loads(result.domain_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["taxonomy_version"], 1)
        self.assertEqual(payload["domain"], "AI")
        self.assertEqual(payload["confidence"], 0.86)
        self.assertEqual(payload["reason"], "内容主要讨论大模型 Agent。")
        self.assertEqual(payload["model_ref"], "deepseek_flash")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertIn("Agent", llm_client.last_prompt)

    def test_classify_domain_accepts_other_for_low_confidence(self):
        asset_dir, canonical_text_path = self.make_asset_dir_with_text()
        llm_client = FakeLlmClient(
            response='{"domain":"其他","confidence":0.31,"reason":"内容跨多个领域，无法明确判断。"}'
        )

        result = classify_domain(
            canonical_text_path=canonical_text_path,
            asset_dir=asset_dir,
            llm_model=self.llm_model(),
            model_ref="deepseek_flash",
            llm_client=llm_client,
        )

        self.assertEqual(result.domain, "其他")
        self.assertEqual(result.confidence, 0.31)

    def test_classify_domain_maps_llm_request_failure(self):
        asset_dir, canonical_text_path = self.make_asset_dir_with_text()
        llm_client = FakeLlmClient(error=RuntimeError("network"))

        with self.assertRaises(KmError) as raised:
            classify_domain(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                llm_model=self.llm_model(),
                model_ref="deepseek_flash",
                llm_client=llm_client,
            )

        self.assertEqual(raised.exception.error_code, "LLM_REQUEST_FAILED")

    def test_classify_domain_maps_schema_failure(self):
        asset_dir, canonical_text_path = self.make_asset_dir_with_text()
        llm_client = FakeLlmClient(response='{"domain":"未知","confidence":1,"reason":"bad"}')

        with self.assertRaises(KmError) as raised:
            classify_domain(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                llm_model=self.llm_model(),
                model_ref="deepseek_flash",
                llm_client=llm_client,
            )

        self.assertEqual(raised.exception.error_code, "LLM_SCHEMA_INVALID")

    def test_openai_compatible_client_posts_chat_completion_request(self):
        httpx_module = FakeHttpxModule(
            FakeHttpResponse(payload={"choices": [{"message": {"content": '{"domain":"AI"}'}}]})
        )
        client = OpenAiCompatibleLlmClient(timeout=12.0, httpx_module=httpx_module)

        content = client.complete(model_config=self.llm_model(), prompt="分类文本")

        self.assertEqual(content, '{"domain":"AI"}')
        self.assertEqual(httpx_module.last_post["url"], "https://api.example.com/v1/chat/completions")
        self.assertEqual(httpx_module.last_post["timeout"], 12.0)
        self.assertEqual(httpx_module.last_post["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(httpx_module.last_post["json"]["model"], "deepseek-v4-flash")
        self.assertIn("领域分类器", httpx_module.last_post["json"]["messages"][0]["content"])
        self.assertEqual(httpx_module.last_post["json"]["messages"][1]["content"], "分类文本")
        self.assertEqual(httpx_module.last_post["json"]["temperature"], 0)

    def test_openai_compatible_client_accepts_task_specific_system_prompt(self):
        httpx_module = FakeHttpxModule(
            FakeHttpResponse(payload={"choices": [{"message": {"content": '{"title":"ok"}'}}]})
        )
        client = OpenAiCompatibleLlmClient(httpx_module=httpx_module)

        client.complete(
            model_config=self.llm_model(),
            prompt="总结文本",
            system_prompt="你是一个严格输出 JSON 的中文知识总结器。",
        )

        self.assertEqual(
            httpx_module.last_post["json"]["messages"][0]["content"],
            "你是一个严格输出 JSON 的中文知识总结器。",
        )
        self.assertNotIn("领域分类器", httpx_module.last_post["json"]["messages"][0]["content"])

    def test_classify_domain_maps_openai_compatible_http_error(self):
        asset_dir, canonical_text_path = self.make_asset_dir_with_text()
        httpx_module = FakeHttpxModule(FakeHttpResponse(error=RuntimeError("500")))
        client = OpenAiCompatibleLlmClient(httpx_module=httpx_module)

        with self.assertRaises(KmError) as raised:
            classify_domain(
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                llm_model=self.llm_model(),
                model_ref="deepseek_flash",
                llm_client=client,
            )

        self.assertEqual(raised.exception.error_code, "LLM_REQUEST_FAILED")


if __name__ == "__main__":
    unittest.main()
