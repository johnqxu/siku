from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Protocol

from .config import LlmModelConfig, SummaryEvaluationConfig
from .domain import DOMAIN_TAXONOMY, TAXONOMY_VERSION
from .errors import (
    KmError,
    llm_request_failed,
    summary_input_invalid,
    summary_input_too_large,
    summary_schema_invalid,
)


SUMMARY_SCHEMA_VERSION = 1
SUMMARY_STRATEGY = "single_pass"
SUMMARY_SYSTEM_PROMPT = "你是一个严格输出 JSON 的中文知识总结器。"
ALLOWED_TAG_PREFIXES = ("knowledge/", "topic/", "tool/", "source/", "workflow/")
TITLE_FORBIDDEN_CHARS = set('/\\:*?"<>|')

DOMAIN_KEY_BY_DOMAIN = {
    "AI": "ai",
    "编程": "programming",
    "产品": "product",
    "商业": "business",
    "学习": "learning",
    "心理学": "psychology",
    "投资": "investing",
    "写作": "writing",
    "生活": "life",
    "菜谱": "recipe",
    "其他": "other",
}

DOMAIN_NOTE_FIELDS = {
    "AI": ("核心问题", "模型或方法", "工具或系统", "数据或评测", "工作流影响", "能力边界", "可复现说明"),
    "编程": ("问题背景", "技术机制", "工具或框架", "实现细节", "调试与验证", "性能或安全", "适用边界"),
    "产品": ("用户痛点", "使用场景", "产品假设", "关键功能", "工作流影响", "指标或反馈", "风险"),
    "商业": ("商业模式", "目标用户", "价值主张", "增长路径", "成本结构", "竞争与壁垒", "风险"),
    "学习": ("学习目标", "方法步骤", "适用场景", "练习设计", "反馈机制", "常见误区", "复盘方式"),
    "心理学": ("核心概念", "机制解释", "证据或论证", "适用场景", "干预方法", "局限", "伦理风险"),
    "投资": ("核心论点", "关键假设", "资产或标的", "风险因素", "估值或价格", "需要监控的信号", "反方观点"),
    "写作": ("主题", "论证结构", "表达技巧", "素材使用", "叙事节奏", "可复用模式", "修改建议"),
    "生活": ("具体情境", "核心原则", "行动步骤", "工具或资源", "注意事项", "风险", "可持续做法"),
    "菜谱": ("菜品特点", "食材", "步骤", "时间与火候", "技巧说明", "替代方案", "失败排查"),
    "其他": ("主题", "背景", "关键信息", "适用场景", "注意事项", "延伸方向"),
}


class LlmClient(Protocol):
    def complete(self, *, model_config: LlmModelConfig, prompt: str, system_prompt: str | None = None) -> str:
        ...


@dataclass(frozen=True)
class SummaryGenerationResult:
    status: str
    summary_path: Path
    domain_path: Path
    domain: str
    title: str
    summary_model_ref: str
    evaluation_enabled: bool
    evaluation_dir: Path | None = None


def domain_key(domain: str) -> str:
    try:
        return DOMAIN_KEY_BY_DOMAIN[domain]
    except KeyError as exc:
        raise summary_input_invalid("领域不在固定领域表中。") from exc


def generate_summary(
    *,
    canonical_text_path: Path,
    asset_dir: Path,
    source_url: str,
    content_type: str,
    domain_path: Path,
    llm_models: dict[str, LlmModelConfig],
    summary_model_ref: str,
    llm_client: LlmClient,
    max_input_chars: int = 0,
    evaluation: SummaryEvaluationConfig | None = None,
) -> SummaryGenerationResult:
    domain_payload = load_domain_payload(domain_path)
    domain = domain_payload["domain"]
    canonical_text = read_canonical_text(canonical_text_path)
    text_for_summary, truncated = prepare_summary_text(canonical_text, max_input_chars)
    prompt_id = f"summary.{domain_key(domain)}.v1"
    prompt = build_summary_prompt(domain=domain, canonical_text=text_for_summary)

    summary_dir = asset_dir / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "summary.json"

    if evaluation is not None and evaluation.enabled:
        return generate_summary_with_evaluation(
            canonical_text_path=canonical_text_path,
            asset_dir=asset_dir,
            source_url=source_url,
            content_type=content_type,
            domain_path=domain_path,
            domain=domain,
            prompt=prompt,
            prompt_id=prompt_id,
            truncated=truncated,
            max_input_chars=max_input_chars,
            llm_models=llm_models,
            llm_client=llm_client,
            evaluation=evaluation,
            summary_path=summary_path,
        )

    if summary_model_ref not in llm_models:
        raise summary_input_invalid("中文总结模型引用不存在。")
    model_config = llm_models[summary_model_ref]
    parsed = run_single_summary_model(
        model_ref=summary_model_ref,
        model_config=model_config,
        prompt=prompt,
        llm_client=llm_client,
        canonical_text_path=canonical_text_path,
        asset_dir=asset_dir,
        source_url=source_url,
        content_type=content_type,
        domain_path=domain_path,
        domain=domain,
        prompt_id=prompt_id,
        truncated=truncated,
        max_input_chars=max_input_chars,
    )
    atomic_write_json(summary_path, parsed)
    return SummaryGenerationResult(
        status="summary_ready",
        summary_path=summary_path,
        domain_path=domain_path,
        domain=domain,
        title=parsed["title"],
        summary_model_ref=summary_model_ref,
        evaluation_enabled=False,
    )


def generate_summary_with_evaluation(
    *,
    canonical_text_path: Path,
    asset_dir: Path,
    source_url: str,
    content_type: str,
    domain_path: Path,
    domain: str,
    prompt: str,
    prompt_id: str,
    truncated: bool,
    max_input_chars: int,
    llm_models: dict[str, LlmModelConfig],
    llm_client: LlmClient,
    evaluation: SummaryEvaluationConfig,
    summary_path: Path,
) -> SummaryGenerationResult:
    evaluation_dir = asset_dir / "summary" / "evaluations"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    failures: dict[str, KmError] = {}

    def call_model(model_ref: str) -> tuple[str, dict[str, Any] | KmError]:
        model_config = llm_models[model_ref]
        try:
            parsed = run_single_summary_model(
                model_ref=model_ref,
                model_config=model_config,
                prompt=prompt,
                llm_client=llm_client,
                canonical_text_path=canonical_text_path,
                asset_dir=asset_dir,
                source_url=source_url,
                content_type=content_type,
                domain_path=domain_path,
                domain=domain,
                prompt_id=prompt_id,
                truncated=truncated,
                max_input_chars=max_input_chars,
            )
            return model_ref, parsed
        except KmError as exc:
            return model_ref, exc
        except Exception as exc:
            return model_ref, llm_request_failed("LLM 请求失败。")

    with ThreadPoolExecutor(max_workers=len(evaluation.candidate_models)) as executor:
        future_by_ref = {
            executor.submit(call_model, model_ref): model_ref for model_ref in evaluation.candidate_models
        }
        for future in as_completed(future_by_ref):
            model_ref, result = future.result()
            if isinstance(result, KmError):
                failures[model_ref] = result
                atomic_write_json(
                    evaluation_dir / f"{model_ref}.json",
                    failure_record(
                        model_ref=model_ref,
                        model=llm_models[model_ref].model,
                        error=result,
                    ),
                )
            else:
                results[model_ref] = result
                atomic_write_json(evaluation_dir / f"{model_ref}.json", result)

    primary_model = evaluation.primary_model
    if primary_model is None:
        raise summary_input_invalid("评测主模型缺失。")
    if primary_model in failures:
        raise failures[primary_model]
    primary_result = results[primary_model]
    atomic_write_json(summary_path, primary_result)
    return SummaryGenerationResult(
        status="summary_ready",
        summary_path=summary_path,
        domain_path=domain_path,
        domain=domain,
        title=primary_result["title"],
        summary_model_ref=primary_model,
        evaluation_enabled=True,
        evaluation_dir=evaluation_dir,
    )


def run_single_summary_model(
    *,
    model_ref: str,
    model_config: LlmModelConfig,
    prompt: str,
    llm_client: LlmClient,
    canonical_text_path: Path,
    asset_dir: Path,
    source_url: str,
    content_type: str,
    domain_path: Path,
    domain: str,
    prompt_id: str,
    truncated: bool,
    max_input_chars: int,
) -> dict[str, Any]:
    try:
        raw_response = llm_client.complete(
            model_config=model_config,
            prompt=prompt,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
        )
    except KmError:
        raise
    except Exception as exc:
        if is_context_limit_error(exc):
            raise summary_input_too_large("中文总结输入超过模型上下文限制。") from exc
        raise llm_request_failed("LLM 请求失败。") from exc
    return parse_summary_response(
        raw_response,
        domain=domain,
        model_ref=model_ref,
        model=model_config.model,
        source_url=source_url,
        content_type=content_type,
        asset_dir=asset_dir,
        canonical_text_path=canonical_text_path,
        domain_path=domain_path,
        prompt_id=prompt_id,
        truncated=truncated,
        max_input_chars=max_input_chars,
    )


def parse_summary_response(
    raw_response: str,
    *,
    domain: str,
    model_ref: str,
    model: str,
    source_url: str,
    content_type: str,
    asset_dir: Path,
    canonical_text_path: Path,
    domain_path: Path,
    prompt_id: str,
    truncated: bool,
    max_input_chars: int,
) -> dict[str, Any]:
    raw_response = raw_response.strip()
    if raw_response.startswith("```"):
        raise summary_schema_invalid("中文总结必须是纯 JSON object。")
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise summary_schema_invalid("中文总结返回内容不是合法 JSON。") from exc
    if not isinstance(payload, dict):
        raise summary_schema_invalid("中文总结返回内容必须是 JSON object。")

    title = required_non_empty_string(payload, "title")
    if any(char in TITLE_FORBIDDEN_CHARS for char in title):
        raise summary_schema_invalid("title 包含路径非法字符。")
    one_sentence_summary = required_non_empty_string(payload, "one_sentence_summary")
    core_points = required_string_array(payload, "core_points")
    actionable_insights = required_string_array(payload, "actionable_insights")
    questions = required_string_array(payload, "questions")
    tags = validate_tags(payload.get("tags"))
    key_concepts = validate_key_concepts(payload.get("key_concepts"))
    domain_notes = validate_domain_notes(payload.get("domain_notes"), domain=domain)

    if "domain" in payload and payload["domain"] != domain:
        raise summary_schema_invalid("模型输出 domain 与领域分类结果不一致。")

    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "domain": domain,
        "title": title,
        "one_sentence_summary": one_sentence_summary,
        "core_points": core_points,
        "key_concepts": key_concepts,
        "domain_notes": domain_notes,
        "actionable_insights": actionable_insights,
        "questions": questions,
        "tags": tags,
        "source": {
            "url": source_url,
            "content_type": content_type,
            "asset_dir": str(asset_dir),
            "canonical_text_path": str(canonical_text_path),
            "domain_path": str(domain_path),
        },
        "input": {
            "canonical_text_path": str(canonical_text_path),
            "domain_path": str(domain_path),
            "strategy": SUMMARY_STRATEGY,
            "truncated": truncated,
            "max_input_chars": max_input_chars,
        },
        "prompt": {
            "prompt_id": prompt_id,
            "domain": domain,
        },
        "model_ref": model_ref,
        "model": model,
    }


def build_summary_prompt(*, domain: str, canonical_text: str) -> str:
    common = load_prompt_asset(Path("prompts") / "summary" / "common.md")
    domain_template = load_prompt_asset(Path("prompts") / "summary" / "domains" / f"{domain_key(domain)}.md")
    return (
        f"{common}\n\n"
        f"{domain_template}\n\n"
        f"当前主领域：{domain}\n\n"
        "规范文本：\n"
        f"{canonical_text}"
    )


def load_prompt_asset(relative_path: Path) -> str:
    path = Path(__file__).resolve().parents[1] / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise summary_input_invalid(f"缺少 prompt 资产：{relative_path}") from exc


def load_domain_payload(domain_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(domain_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise summary_input_invalid("缺少或无法解析 summary/domain.json。") from exc
    if not isinstance(payload, dict):
        raise summary_input_invalid("summary/domain.json 必须是 JSON object。")
    if payload.get("taxonomy_version") != TAXONOMY_VERSION:
        raise summary_input_invalid("summary/domain.json taxonomy_version 无效。")
    domain = payload.get("domain")
    if not isinstance(domain, str) or domain not in DOMAIN_TAXONOMY:
        raise summary_input_invalid("summary/domain.json domain 不在固定领域表中。")
    return payload


def read_canonical_text(canonical_text_path: Path) -> str:
    try:
        return canonical_text_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise summary_input_invalid("缺少规范文本文件。") from exc


def prepare_summary_text(canonical_text: str, max_input_chars: int) -> tuple[str, bool]:
    if max_input_chars > 0 and len(canonical_text) > max_input_chars:
        return canonical_text[:max_input_chars], True
    return canonical_text, False


def required_non_empty_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise summary_schema_invalid(f"中文总结缺少合法 {key}。")
    return value.strip()


def required_string_array(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise summary_schema_invalid(f"{key} 必须是字符串数组。")
    return [item.strip() for item in value]


def validate_key_concepts(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise summary_schema_invalid("key_concepts 必须是数组。")
    concepts: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise summary_schema_invalid("key_concepts 元素必须是 object。")
        name = item.get("name")
        explanation = item.get("explanation")
        if not isinstance(name, str) or not name.strip() or not isinstance(explanation, str) or not explanation.strip():
            raise summary_schema_invalid("key_concepts 元素必须包含 name 和 explanation。")
        concepts.append({"name": name.strip(), "explanation": explanation.strip()})
    return concepts


def validate_domain_notes(value: Any, *, domain: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise summary_schema_invalid("domain_notes 必须是 object。")
    required_fields = DOMAIN_NOTE_FIELDS[domain]
    notes: dict[str, str] = {}
    for field in required_fields:
        field_value = value.get(field)
        if not isinstance(field_value, str) or not field_value.strip():
            raise summary_schema_invalid("domain_notes 缺少固定字段。")
        notes[field] = field_value.strip()
    return notes


def validate_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise summary_schema_invalid("tags 必须是字符串数组。")
    if len(value) > 5:
        raise summary_schema_invalid("tags 最多 5 个。")
    tags: list[str] = []
    for tag in value:
        if not isinstance(tag, str) or not tag.strip():
            raise summary_schema_invalid("tags 不能包含空值。")
        tag = tag.strip()
        matched_prefix = next((prefix for prefix in ALLOWED_TAG_PREFIXES if tag.startswith(prefix)), None)
        if matched_prefix is None:
            raise summary_schema_invalid("tag 前缀不受支持。")
        if tag == matched_prefix:
            raise summary_schema_invalid("tag 前缀后必须有内容。")
        if tag.count("/") != 1:
            raise summary_schema_invalid("tag 不允许深层层级。")
        tags.append(tag)
    return tags


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def failure_record(*, model_ref: str, model: str, error: KmError) -> dict[str, Any]:
    return {
        "ok": False,
        "model_ref": model_ref,
        "model": model,
        "error_code": error.error_code,
        "message": error.message,
        "recoverable": error.recoverable,
    }


def is_context_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    needles = ("context", "token", "too large", "maximum", "length", "上下文", "超限")
    return any(needle in message for needle in needles)
