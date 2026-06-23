from __future__ import annotations

import json
import sys
from datetime import datetime

from .agent_runner import AgentIngestRunner
from .asset_store import AssetStore
from .bilibili import YtDlpBilibiliDownloader, collect_bilibili_transcript
from .config import load_config
from .domain import OpenAiCompatibleLlmClient, classify_domain
from .errors import KmError, index_write_failed, input_invalid, internal_error, unsupported_url
from .index import IngestIndex
from .models import (
    IngestRequest,
    failure_response,
    processed_ready_response,
    skipped_existing_response,
)
from .obsidian import ObsidianNoteContext, load_summary_payload, write_obsidian_note
from .routing import ContentType, route_url
from .summary import generate_summary
from .url_state import generate_source_id, normalize_url
from .web_article import HttpWebArticleFetcher, collect_web_article
from .whisper import OpenVinoWhisperTranscriber


def write_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def ensure_pipeline_llm_tasks_configured(config) -> None:
    from .errors import config_invalid

    if config.llm_tasks.domain_classification is None:
        raise config_invalid("缺少 llm.tasks.domain_classification 配置。")
    if config.llm_tasks.summary_generation is None:
        raise config_invalid("缺少 llm.tasks.summary_generation 配置。")


def summarize_collected_result(result, config):
    domain_model_ref = config.llm_tasks.domain_classification
    llm_model = config.llm_models[domain_model_ref]
    domain = classify_domain(
        canonical_text_path=result.canonical_text_path,
        asset_dir=result.asset_dir,
        llm_model=llm_model,
        model_ref=domain_model_ref,
        llm_client=OpenAiCompatibleLlmClient(),
    )

    summary_model_ref = config.llm_tasks.summary_generation
    summary = generate_summary(
        canonical_text_path=result.canonical_text_path,
        asset_dir=result.asset_dir,
        source_url=result.source_url,
        content_type=result.content_type,
        domain_path=domain.domain_path,
        llm_models=config.llm_models,
        summary_model_ref=summary_model_ref,
        llm_client=OpenAiCompatibleLlmClient(),
        max_input_chars=config.summary.max_input_chars,
        evaluation=config.summary.evaluation,
    )
    return summary


def process_obsidian_note(
    *,
    collected_result,
    summary_result,
    config,
    index: IngestIndex,
    source_id: str,
    normalized_url: str,
    original_url: str,
):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    context = ObsidianNoteContext(
        source_id=source_id,
        normalized_url=normalized_url,
        original_url=original_url,
        content_type=collected_result.content_type,
        asset_dir=collected_result.asset_dir,
        canonical_text_path=collected_result.canonical_text_path,
        domain_path=summary_result.domain_path,
        summary_path=summary_result.summary_path,
    )
    summary_payload = load_summary_payload(context=context)
    try:
        note = write_obsidian_note(
            context=context,
            summary_payload=summary_payload,
            vault_path=config.vault_path,
            inbox_dir=config.inbox_dir,
            now=now,
            date_prefix=now[:10],
        )
    except KmError as exc:
        if exc.error_code == "OBSIDIAN_WRITE_FAILED":
            mark_stage_eight_failed(
                index=index,
                source_id=source_id,
                normalized_url=normalized_url,
                original_url=original_url,
                content_type=collected_result.content_type,
                asset_dir=str(collected_result.asset_dir),
                error=exc,
                now=now,
                domain=summary_result.domain,
                title=summary_result.title,
            )
        raise
    try:
        index.mark_processed(
            source_id=source_id,
            normalized_url=normalized_url,
            original_url=original_url,
            content_type=collected_result.content_type,
            domain=summary_result.domain,
            title=summary_result.title,
            note_path=str(note.note_path),
            asset_dir=str(collected_result.asset_dir),
            now=now,
        )
    except KmError as exc:
        mark_stage_eight_failed(
            index=index,
            source_id=source_id,
            normalized_url=normalized_url,
            original_url=original_url,
            content_type=collected_result.content_type,
            asset_dir=str(collected_result.asset_dir),
            error=index_write_failed(str(note.note_path), exc.message),
            now=now,
            domain=summary_result.domain,
            title=summary_result.title,
            note_path=str(note.note_path),
        )
        raise index_write_failed(str(note.note_path)) from exc
    return processed_ready_response(
        content_type=collected_result.content_type,
        source_url=original_url,
        asset_dir=str(collected_result.asset_dir),
        canonical_text_path=str(collected_result.canonical_text_path),
        domain_path=str(summary_result.domain_path),
        summary_path=str(summary_result.summary_path),
        note_path=str(note.note_path),
        domain=summary_result.domain,
        title=summary_result.title,
    )


def mark_stage_eight_failed(
    *,
    index: IngestIndex,
    source_id: str,
    normalized_url: str,
    original_url: str,
    content_type: str,
    asset_dir: str,
    error: KmError,
    now: str,
    domain: str | None,
    title: str | None,
    note_path: str | None = None,
) -> None:
    try:
        index.mark_failed(
            source_id=source_id,
            normalized_url=normalized_url,
            original_url=original_url,
            content_type=content_type,
            asset_dir=asset_dir,
            error_code=error.error_code,
            error_message=error.message,
            now=now,
            domain=domain,
            title=title,
            note_path=note_path,
        )
    except KmError:
        pass


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in {"ingest", "agent-ingest"}:
        error = input_invalid("未知命令。")
        write_json(failure_response(error))
        return error.exit_code

    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        error = input_invalid("stdin 必须是合法 JSON。")
        write_json(failure_response(error))
        return error.exit_code

    if sys.argv[1] == "agent-ingest":
        try:
            config = load_config()
            runner = AgentIngestRunner(config=config)
            response = runner.run(payload)
            write_json(response)
            if response.get("ok") is True:
                return 0
            recoverable = response.get("recoverable")
            return 2 if recoverable is True else 1
        except KmError as exc:
            write_json(failure_response(exc))
            return exc.exit_code
        except Exception as exc:
            print(f"internal error: {exc}", file=sys.stderr)
            error = internal_error()
            write_json(failure_response(error))
            return error.exit_code

    try:
        request = IngestRequest.from_payload(payload)
        config = load_config()
        normalized = normalize_url(request.url)
        source_id = generate_source_id(normalized.normalized_url)

        asset_store = AssetStore(config.asset_store_path)
        source_paths = asset_store.initialize_source(source_id)
        index = IngestIndex(asset_store.index_path)
        index.initialize()
        duplicate = index.find_processed_source(normalized.normalized_url)
        if duplicate is not None:
            write_json(
                skipped_existing_response(
                    note_path=duplicate.note_path,
                    asset_dir=duplicate.asset_dir,
                    source_url=duplicate.original_url,
                )
            )
            return 0

        route = route_url(normalized.normalized_url)
        if route.content_type == ContentType.UNSUPPORTED:
            error = unsupported_url()
        elif route.content_type == ContentType.BILIBILI_VIDEO:
            ensure_pipeline_llm_tasks_configured(config)
            result = collect_bilibili_transcript(
                source_url=normalized.normalized_url,
                asset_dir=source_paths.asset_dir,
                downloader=YtDlpBilibiliDownloader(),
                transcriber=OpenVinoWhisperTranscriber(
                    model_dir=config.whisper_model_dir,
                    model_size=config.whisper_model_size,
                    device=config.whisper_device,
                ),
            )
            summary = summarize_collected_result(result, config)
            response = process_obsidian_note(
                collected_result=result,
                summary_result=summary,
                config=config,
                index=index,
                source_id=source_id,
                normalized_url=normalized.normalized_url,
                original_url=request.url,
            )
            write_json(response)
            return 0
        else:
            ensure_pipeline_llm_tasks_configured(config)
            result = collect_web_article(
                source_url=normalized.normalized_url,
                asset_dir=source_paths.asset_dir,
                fetcher=HttpWebArticleFetcher(),
            )
            summary = summarize_collected_result(result, config)
            response = process_obsidian_note(
                collected_result=result,
                summary_result=summary,
                config=config,
                index=index,
                source_id=source_id,
                normalized_url=normalized.normalized_url,
                original_url=request.url,
            )
            write_json(response)
            return 0
    except KmError as exc:
        error = exc
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        error = internal_error()

    write_json(failure_response(error))
    return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
