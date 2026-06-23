from __future__ import annotations

from dataclasses import dataclass
import os
import re
import tomllib
from pathlib import Path
from typing import Any

from .errors import config_invalid


@dataclass(frozen=True)
class KmConfig:
    vault_path: Path
    inbox_dir: str
    asset_store_path: Path
    whisper_model_dir: str
    whisper_model_size: str
    whisper_device: str
    llm_models: dict[str, "LlmModelConfig"]
    llm_tasks: "LlmTasksConfig"
    summary: "SummaryConfig"


@dataclass(frozen=True)
class LlmModelConfig:
    provider: str
    base_url: str
    model: str
    api_key_env: str
    api_key: str
    timeout_seconds: float = 120.0
    max_output_tokens: int = 8192


@dataclass(frozen=True)
class LlmTasksConfig:
    agent_orchestration: str | None = None
    domain_classification: str | None = None
    summary_generation: str | None = None


@dataclass(frozen=True)
class SummaryEvaluationConfig:
    enabled: bool = False
    candidate_models: tuple[str, ...] = ()
    primary_model: str | None = None


@dataclass(frozen=True)
class SummaryConfig:
    max_input_chars: int = 0
    evaluation: SummaryEvaluationConfig = SummaryEvaluationConfig()


def config_path_from_env() -> Path:
    return Path(os.environ.get("KM_CONFIG", "~/.config/km/config.toml")).expanduser()


def load_config() -> KmConfig:
    config_path = config_path_from_env()
    try:
        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)
    except OSError as exc:
        raise config_invalid("配置文件缺失或无法读取。") from exc
    except tomllib.TOMLDecodeError as exc:
        raise config_invalid("配置文件不是合法 TOML。") from exc

    if not isinstance(config, dict):
        raise config_invalid("配置文件根节点必须是 TOML object。")

    return parse_config(config)


def parse_config(config: dict[str, Any]) -> KmConfig:
    vault_path = required_string(config, "vault_path")
    inbox_dir = required_string(config, "inbox_dir")
    asset_store_path = required_string(config, "asset_store_path")
    whisper = config.get("whisper", {})
    if whisper is None:
        whisper = {}
    if not isinstance(whisper, dict):
        raise config_invalid("配置字段 whisper 必须是 TOML object。")
    whisper_model_dir = optional_string(whisper, "model_dir", "models/whisper")
    whisper_model_size = optional_string(whisper, "model_size", "medium")
    whisper_device = optional_string(whisper, "device", "GPU")
    if whisper_device == "CPU":
        raise config_invalid("whisper.device 不允许为 CPU；阶段四要求 Intel GPU。")
    summary = parse_summary_config(config.get("summary", {}))
    llm_models, llm_tasks = parse_llm_config(config.get("llm", {}), summary=summary)

    inbox_path = Path(inbox_dir)
    if inbox_path.is_absolute() or ".." in inbox_path.parts:
        raise config_invalid("inbox_dir 必须是 vault 内相对路径。")

    vault = Path(vault_path).expanduser()
    asset_store = Path(asset_store_path).expanduser()
    if path_is_same_or_inside(asset_store, vault):
        raise config_invalid("asset_store_path 必须位于 Obsidian vault 外部。")

    return KmConfig(
        vault_path=vault,
        inbox_dir=inbox_dir,
        asset_store_path=asset_store,
        whisper_model_dir=whisper_model_dir,
        whisper_model_size=whisper_model_size,
        whisper_device=whisper_device,
        llm_models=llm_models,
        llm_tasks=llm_tasks,
        summary=summary,
    )


def parse_llm_config(raw_llm: Any, *, summary: SummaryConfig | None = None) -> tuple[dict[str, LlmModelConfig], LlmTasksConfig]:
    if raw_llm is None:
        raw_llm = {}
    if not isinstance(raw_llm, dict):
        raise config_invalid("配置字段 llm 必须是 TOML object。")

    raw_models = raw_llm.get("models", {})
    raw_tasks = raw_llm.get("tasks", {})
    if raw_models is None:
        raw_models = {}
    if raw_tasks is None:
        raw_tasks = {}
    if not isinstance(raw_models, dict):
        raise config_invalid("配置字段 llm.models 必须是 TOML object。")
    if not isinstance(raw_tasks, dict):
        raise config_invalid("配置字段 llm.tasks 必须是 TOML object。")

    agent_orchestration = parse_optional_model_ref(
        raw_tasks,
        "agent_orchestration",
        raw_models,
        "llm.tasks.agent_orchestration",
    )
    domain_classification = parse_optional_model_ref(
        raw_tasks,
        "domain_classification",
        raw_models,
        "llm.tasks.domain_classification",
    )
    summary_generation = parse_optional_model_ref(
        raw_tasks,
        "summary_generation",
        raw_models,
        "llm.tasks.summary_generation",
    )

    referenced_models = {
        ref
        for ref in (agent_orchestration, domain_classification, summary_generation)
        if ref is not None
    }
    if summary is not None and summary.evaluation.enabled:
        for ref in summary.evaluation.candidate_models:
            if ref not in raw_models:
                raise config_invalid("summary.evaluation.candidate_models 引用的模型不存在。")
            referenced_models.add(ref)
        primary = summary.evaluation.primary_model
        if primary is None or primary not in summary.evaluation.candidate_models:
            raise config_invalid("summary.evaluation.primary_model 必须包含在 candidate_models 中。")
        referenced_models.add(primary)

    models: dict[str, LlmModelConfig] = {}
    for name, raw_model in raw_models.items():
        if not isinstance(name, str) or not name.strip():
            raise config_invalid("llm.models 的模型引用名必须是非空字符串。")
        if not isinstance(raw_model, dict):
            raise config_invalid(f"配置字段 llm.models.{name} 必须是 TOML object。")
        if name in referenced_models:
            models[name] = parse_llm_model_config(name, raw_model)

    return models, LlmTasksConfig(
        agent_orchestration=agent_orchestration,
        domain_classification=domain_classification,
        summary_generation=summary_generation,
    )


def parse_llm_model_config(name: str, raw_model: dict[str, Any]) -> LlmModelConfig:
    provider = required_nested_string(raw_model, "provider", f"llm.models.{name}.provider")
    base_url = required_nested_string(raw_model, "base_url", f"llm.models.{name}.base_url")
    model = required_nested_string(raw_model, "model", f"llm.models.{name}.model")
    api_key_env = required_nested_string(raw_model, "api_key_env", f"llm.models.{name}.api_key_env")
    if provider != "openai_compatible":
        raise config_invalid("阶段六只支持 provider = openai_compatible。")
    timeout_seconds = optional_positive_number(raw_model, "timeout_seconds", 120.0, f"llm.models.{name}.timeout_seconds")
    max_output_tokens = optional_positive_int(raw_model, "max_output_tokens", 8192, f"llm.models.{name}.max_output_tokens")
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise config_invalid(f"环境变量 {api_key_env} 必须存在且非空。")
    return LlmModelConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
    )


def parse_optional_model_ref(
    raw_tasks: dict[str, Any],
    key: str,
    raw_models: dict[str, Any],
    display_name: str,
) -> str | None:
    value = raw_tasks.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise config_invalid(f"配置字段 {display_name} 必须是非空字符串。")
    value = value.strip()
    if value not in raw_models:
        raise config_invalid(f"{display_name} 引用的模型不存在。")
    return value


def parse_summary_config(raw_summary: Any) -> SummaryConfig:
    if raw_summary is None:
        raw_summary = {}
    if not isinstance(raw_summary, dict):
        raise config_invalid("配置字段 summary 必须是 TOML object。")
    max_input_chars = raw_summary.get("max_input_chars", 0)
    if isinstance(max_input_chars, bool) or not isinstance(max_input_chars, int) or max_input_chars < 0:
        raise config_invalid("配置字段 summary.max_input_chars 必须是非负整数。")
    evaluation = parse_summary_evaluation_config(raw_summary.get("evaluation", {}))
    return SummaryConfig(max_input_chars=max_input_chars, evaluation=evaluation)


def parse_summary_evaluation_config(raw_evaluation: Any) -> SummaryEvaluationConfig:
    if raw_evaluation is None:
        raw_evaluation = {}
    if not isinstance(raw_evaluation, dict):
        raise config_invalid("配置字段 summary.evaluation 必须是 TOML object。")
    enabled = raw_evaluation.get("enabled", False)
    if not isinstance(enabled, bool):
        raise config_invalid("配置字段 summary.evaluation.enabled 必须是布尔值。")
    if not enabled:
        return SummaryEvaluationConfig(enabled=False)

    raw_candidates = raw_evaluation.get("candidate_models")
    primary_model = raw_evaluation.get("primary_model")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise config_invalid("配置字段 summary.evaluation.candidate_models 必须是非空数组。")
    candidate_models: list[str] = []
    for candidate in raw_candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            raise config_invalid("summary.evaluation.candidate_models 中的模型引用必须是非空字符串。")
        candidate = candidate.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", candidate):
            raise config_invalid("summary.evaluation.candidate_models 中的模型引用必须是文件名安全字符串。")
        candidate_models.append(candidate)
    if not isinstance(primary_model, str) or not primary_model.strip():
        raise config_invalid("配置字段 summary.evaluation.primary_model 必须是非空字符串。")
    primary_model = primary_model.strip()
    if primary_model not in candidate_models:
        raise config_invalid("summary.evaluation.primary_model 必须包含在 candidate_models 中。")
    return SummaryEvaluationConfig(
        enabled=True,
        candidate_models=tuple(candidate_models),
        primary_model=primary_model,
    )


def required_string(config: dict[str, Any], field_name: str) -> str:
    value = config.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise config_invalid(f"配置字段 {field_name} 必须是非空字符串。")
    return value.strip()


def required_nested_string(config: dict[str, Any], key: str, display_name: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise config_invalid(f"配置字段 {display_name} 必须是非空字符串。")
    return value.strip()


def optional_string(config: dict[str, Any], field_name: str, default: str) -> str:
    value = config.get(field_name, default)
    if not isinstance(value, str) or not value.strip():
        raise config_invalid(f"配置字段 {field_name} 必须是非空字符串。")
    return value.strip()


def optional_positive_number(config: dict[str, Any], field_name: str, default: float, display_name: str) -> float:
    value = config.get(field_name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
        raise config_invalid(f"配置字段 {display_name} 必须是正数。")
    return float(value)


def optional_positive_int(config: dict[str, Any], field_name: str, default: int, display_name: str) -> int:
    value = config.get(field_name, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise config_invalid(f"配置字段 {display_name} 必须是正整数。")
    return value


def path_is_same_or_inside(path: Path, parent: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_parent = parent.resolve(strict=False)
    return resolved_path == resolved_parent or resolved_parent in resolved_path.parents
