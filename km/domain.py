from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Protocol

from .config import LlmModelConfig
from .errors import KmError, llm_request_failed, llm_schema_invalid


TAXONOMY_VERSION = 1
CLASSIFICATION_TEXT_LIMIT = 12000
DOMAIN_TAXONOMY = (
    "AI",
    "编程",
    "产品",
    "商业",
    "学习",
    "心理学",
    "投资",
    "写作",
    "生活",
    "菜谱",
    "其他",
)


DOMAIN_CLASSIFICATION_SYSTEM_PROMPT = "你是一个严格输出 JSON 的中文知识领域分类器。"


class LlmClient(Protocol):
    def complete(self, *, model_config: LlmModelConfig, prompt: str, system_prompt: str | None = None) -> str:
        ...


@dataclass(frozen=True)
class DomainClassificationResponse:
    taxonomy_version: int
    domain: str
    confidence: float
    reason: str
    model_ref: str
    model: str


@dataclass(frozen=True)
class DomainClassificationResult:
    status: str
    domain_path: Path
    domain: str
    taxonomy_version: int
    model_ref: str
    confidence: float
    reason: str


class OpenAiCompatibleLlmClient:
    def __init__(self, *, timeout: float = 30.0, httpx_module=None) -> None:
        self._timeout = timeout
        self._httpx = httpx_module

    def complete(self, *, model_config: LlmModelConfig, prompt: str, system_prompt: str | None = None) -> str:
        httpx_module = self._httpx
        if httpx_module is None:
            try:
                import httpx as httpx_module
            except ModuleNotFoundError as exc:
                raise RuntimeError("缺少 httpx 依赖。") from exc
        timeout = model_config.timeout_seconds if self._timeout == 30.0 else self._timeout
        system_prompt = system_prompt or DOMAIN_CLASSIFICATION_SYSTEM_PROMPT
        response = httpx_module.post(
            f"{model_config.base_url.rstrip('/')}/chat/completions",
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {model_config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": model_config.max_output_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM 响应缺少 content。") from exc
        if not isinstance(content, str):
            raise RuntimeError("LLM 响应 content 必须是字符串。")
        return content


def classify_domain(
    *,
    canonical_text_path: Path,
    asset_dir: Path,
    llm_model: LlmModelConfig,
    model_ref: str,
    llm_client: LlmClient,
) -> DomainClassificationResult:
    canonical_text = canonical_text_path.read_text(encoding="utf-8")
    prompt = build_domain_classification_prompt(canonical_text)
    try:
        raw_response = llm_client.complete(model_config=llm_model, prompt=prompt)
    except KmError:
        raise
    except Exception as exc:
        raise llm_request_failed("LLM 请求失败。") from exc
    parsed = parse_domain_classification_response(
        raw_response,
        model_ref=model_ref,
        model=llm_model.model,
    )

    summary_dir = asset_dir / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    domain_path = summary_dir / "domain.json"
    domain_path.write_text(
        json.dumps(asdict(parsed), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return DomainClassificationResult(
        status="domain_ready",
        domain_path=domain_path,
        domain=parsed.domain,
        taxonomy_version=parsed.taxonomy_version,
        model_ref=parsed.model_ref,
        confidence=parsed.confidence,
        reason=parsed.reason,
    )


def build_domain_classification_prompt(canonical_text: str) -> str:
    taxonomy = "、".join(DOMAIN_TAXONOMY)
    text_for_classification = canonical_text
    truncation_notice = ""
    if len(canonical_text) > CLASSIFICATION_TEXT_LIMIT:
        text_for_classification = canonical_text[:CLASSIFICATION_TEXT_LIMIT]
        truncation_notice = (
            f"注意：规范文本已截断，仅使用前 {CLASSIFICATION_TEXT_LIMIT} 个字符进行领域分类。\n"
        )
    return (
        "请根据下面的规范文本选择一个主领域。\n"
        f"固定领域表：{taxonomy}\n"
        "只能输出 JSON object，字段必须包含 domain、confidence、reason。\n"
        "domain 必须来自固定领域表，只能选一个主领域。\n"
        "如果内容跨领域、证据不足或无法明确判断，请选择「其他」。\n"
        "reason 必须使用中文。\n\n"
        f"{truncation_notice}"
        "规范文本：\n"
        f"{text_for_classification}"
    )


def parse_domain_classification_response(
    raw_response: str,
    *,
    model_ref: str,
    model: str,
) -> DomainClassificationResponse:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise llm_schema_invalid("LLM 返回内容不是合法 JSON。") from exc
    if not isinstance(payload, dict):
        raise llm_schema_invalid("LLM 返回内容必须是 JSON object。")

    domain = payload.get("domain")
    confidence = payload.get("confidence")
    reason = payload.get("reason")
    if not isinstance(domain, str) or not domain.strip():
        raise llm_schema_invalid("LLM 返回内容缺少合法 domain。")
    domain = domain.strip()
    if domain not in DOMAIN_TAXONOMY:
        raise llm_schema_invalid("LLM 返回 domain 不在固定领域表中。")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise llm_schema_invalid("LLM 返回 confidence 必须是数字。")
    if not math.isfinite(float(confidence)):
        raise llm_schema_invalid("LLM 返回 confidence 必须是有限数字。")
    if not isinstance(reason, str) or not reason.strip():
        raise llm_schema_invalid("LLM 返回内容缺少合法 reason。")

    return DomainClassificationResponse(
        taxonomy_version=TAXONOMY_VERSION,
        domain=domain,
        confidence=float(confidence),
        reason=reason.strip(),
        model_ref=model_ref,
        model=model,
    )
