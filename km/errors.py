from __future__ import annotations

from dataclasses import dataclass


EXIT_PROTOCOL_ERROR = 1
EXIT_RECOVERABLE_FAILURE = 2


@dataclass(frozen=True)
class KmError(Exception):
    error_code: str
    message: str
    recoverable: bool
    exit_code: int


def input_invalid(message: str) -> KmError:
    return KmError("INPUT_INVALID", message, False, EXIT_PROTOCOL_ERROR)


def config_invalid(message: str) -> KmError:
    return KmError("CONFIG_INVALID", message, False, EXIT_PROTOCOL_ERROR)


def not_implemented() -> KmError:
    return KmError("NOT_IMPLEMENTED", "导入能力尚未实现。", True, EXIT_RECOVERABLE_FAILURE)


def unsupported_url() -> KmError:
    return KmError("UNSUPPORTED_URL", "当前版本不支持处理该 URL。", False, EXIT_PROTOCOL_ERROR)


def bilibili_metadata_failed(message: str = "Bilibili 元数据采集失败。") -> KmError:
    return KmError("BILIBILI_METADATA_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


def bilibili_transcript_failed(message: str = "Bilibili 文本生成失败。") -> KmError:
    return KmError("BILIBILI_TRANSCRIPT_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


def whisper_unavailable(message: str = "本地 Whisper 不可用。") -> KmError:
    return KmError("WHISPER_UNAVAILABLE", message, True, EXIT_RECOVERABLE_FAILURE)


def web_fetch_failed(message: str = "网页抓取失败。") -> KmError:
    return KmError("WEB_FETCH_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


def web_parse_failed(message: str = "网页正文解析失败。") -> KmError:
    return KmError("WEB_PARSE_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


def llm_request_failed(message: str = "LLM 请求失败。") -> KmError:
    return KmError("LLM_REQUEST_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


def llm_schema_invalid(message: str = "LLM 返回内容不符合 schema。") -> KmError:
    return KmError("LLM_SCHEMA_INVALID", message, True, EXIT_RECOVERABLE_FAILURE)


def summary_input_invalid(message: str = "中文总结输入无效。") -> KmError:
    return KmError("SUMMARY_INPUT_INVALID", message, True, EXIT_RECOVERABLE_FAILURE)


def summary_input_too_large(message: str = "中文总结输入超过模型上下文限制。") -> KmError:
    return KmError("SUMMARY_INPUT_TOO_LARGE", message, True, EXIT_RECOVERABLE_FAILURE)


def summary_schema_invalid(message: str = "中文总结返回内容不符合 schema。") -> KmError:
    return KmError("SUMMARY_SCHEMA_INVALID", message, True, EXIT_RECOVERABLE_FAILURE)


def obsidian_write_failed(message: str = "Obsidian 写入失败。") -> KmError:
    return KmError("OBSIDIAN_WRITE_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


def agent_runtime_unavailable(message: str = "Deep Agents runtime 不可用。") -> KmError:
    return KmError("AGENT_RUNTIME_UNAVAILABLE", message, True, EXIT_RECOVERABLE_FAILURE)


def agent_skill_missing(message: str = "Agent 必需 skill 缺失或为空。") -> KmError:
    return KmError("AGENT_SKILL_MISSING", message, True, EXIT_RECOVERABLE_FAILURE)


def agent_invalid_transition(message: str = "Agent tool 状态转换非法。") -> KmError:
    return KmError("AGENT_INVALID_TRANSITION", message, True, EXIT_RECOVERABLE_FAILURE)


def agent_orchestration_failed(message: str = "Agent 编排失败。") -> KmError:
    return KmError("AGENT_ORCHESTRATION_FAILED", message, True, EXIT_RECOVERABLE_FAILURE)


@dataclass(frozen=True)
class IndexWriteFailed(KmError):
    note_path: str


def index_write_failed(note_path: str, message: str = "SQLite processed 状态写入失败。") -> IndexWriteFailed:
    return IndexWriteFailed("INDEX_WRITE_FAILED", message, True, EXIT_RECOVERABLE_FAILURE, note_path)


def internal_error() -> KmError:
    return KmError("INTERNAL_ERROR", "内部错误。", False, EXIT_PROTOCOL_ERROR)
