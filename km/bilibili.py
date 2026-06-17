from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Protocol

from .errors import (
    bilibili_metadata_failed,
    bilibili_transcript_failed,
    KmError,
)
from .whisper import TranscriptionResult


BILIBILI_YTDLP_HEADERS = [
    "--add-header",
    "Referer: https://www.bilibili.com",
    "--add-header",
    "Origin: https://www.bilibili.com",
    "--user-agent",
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
]


class BilibiliPipelineError(Exception):
    pass


@dataclass(frozen=True)
class BilibiliMetadata:
    title: str
    uploader: str
    source_url: str
    canonical_url: str | None = None
    raw_info: dict[str, object] | None = None


@dataclass(frozen=True)
class BilibiliSubtitle:
    filename: str
    text: str


@dataclass(frozen=True)
class LocalAudio:
    path: Path


@dataclass(frozen=True)
class BilibiliTranscriptResult:
    status: str
    content_type: str
    source_url: str
    asset_dir: Path
    canonical_text_path: Path
    asset_manifest: dict[str, str]


class BilibiliDownloader(Protocol):
    def fetch_metadata(self, source_url: str) -> BilibiliMetadata:
        ...

    def fetch_subtitle(self, metadata: BilibiliMetadata) -> BilibiliSubtitle | None:
        ...

    def download_audio(self, metadata: BilibiliMetadata, raw_dir: Path) -> LocalAudio:
        ...


class WhisperTranscriber(Protocol):
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        ...


class YtDlpBilibiliDownloader:
    def __init__(self, runner=subprocess.run) -> None:
        self._runner = runner

    def fetch_metadata(self, source_url: str) -> BilibiliMetadata:
        command = [
            "yt-dlp",
            "--dump-single-json",
            "--skip-download",
            "--no-warnings",
            *BILIBILI_YTDLP_HEADERS,
            source_url,
        ]
        completed = self._run(command)
        try:
            info = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise BilibiliPipelineError("yt-dlp 元数据输出不是合法 JSON。") from exc
        if not isinstance(info, dict):
            raise BilibiliPipelineError("yt-dlp 元数据输出必须是 JSON object。")
        title = _string_from_info(info, "title", "未命名 Bilibili 视频")
        uploader = _string_from_info(info, "uploader", "")
        canonical_url = _optional_string_from_info(info, "webpage_url")
        return BilibiliMetadata(
            title=title,
            uploader=uploader,
            source_url=source_url,
            canonical_url=canonical_url,
            raw_info=info,
        )

    def fetch_subtitle(self, metadata: BilibiliMetadata) -> BilibiliSubtitle | None:
        info = metadata.raw_info or {}
        subtitles = info.get("subtitles")
        automatic = info.get("automatic_captions")
        for language, entries in _subtitle_groups(subtitles, automatic):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                data = entry.get("data")
                if isinstance(data, str) and data.strip():
                    ext = _string_from_info(entry, "ext", "srt")
                    return BilibiliSubtitle(filename=f"subtitle.{language}.{ext}", text=data)
        return None

    def download_audio(self, metadata: BilibiliMetadata, raw_dir: Path) -> LocalAudio:
        output_template = str(raw_dir / "audio.%(ext)s")
        command = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format",
            "wav",
            "--print",
            "after_move:filepath",
            "-o",
            output_template,
            *BILIBILI_YTDLP_HEADERS,
            metadata.source_url,
        ]
        completed = self._run(command)
        path_text = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
        if not path_text:
            raise BilibiliPipelineError("yt-dlp 未返回音频文件路径。")
        return LocalAudio(path=Path(path_text))

    def _run(self, command: list[str]):
        try:
            return self._runner(command, text=True, capture_output=True, check=True)
        except FileNotFoundError as exc:
            raise BilibiliPipelineError("缺少 yt-dlp。") from exc
        except subprocess.CalledProcessError as exc:
            raise BilibiliPipelineError("yt-dlp 执行失败。") from exc


def collect_bilibili_transcript(
    *,
    source_url: str,
    asset_dir: Path,
    downloader: BilibiliDownloader,
    transcriber: WhisperTranscriber,
) -> BilibiliTranscriptResult:
    raw_dir = asset_dir / "raw"
    canonical_dir = asset_dir / "canonical"
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir.mkdir(parents=True, exist_ok=True)

    try:
        metadata = downloader.fetch_metadata(source_url)
    except Exception as exc:
        raise bilibili_metadata_failed("Bilibili 元数据采集失败。") from exc

    metadata_path = raw_dir / "metadata.json"
    _write_metadata(metadata_path, metadata)
    manifest = {"metadata": str(metadata_path)}

    try:
        subtitle = downloader.fetch_subtitle(metadata)
    except Exception as exc:
        raise bilibili_transcript_failed("Bilibili 字幕采集失败。") from exc

    if subtitle is not None and subtitle.text.strip():
        subtitle_path = raw_dir / _safe_filename(subtitle.filename, "subtitle.srt")
        subtitle_path.write_text(subtitle.text, encoding="utf-8")
        manifest["subtitle"] = str(subtitle_path)
        transcript_text = _subtitle_to_text(subtitle.text)
    else:
        try:
            audio = downloader.download_audio(metadata, raw_dir)
        except Exception as exc:
            raise bilibili_transcript_failed("Bilibili 音频下载失败。") from exc
        manifest["audio"] = str(audio.path)
        try:
            transcript = transcriber.transcribe(audio.path)
        except KmError:
            raise
        except Exception as exc:
            raise bilibili_transcript_failed("Whisper 转写失败。") from exc
        transcript_text = transcript.text

    transcript_path = canonical_dir / "transcript.md"
    transcript_path.write_text(_to_markdown_transcript(transcript_text), encoding="utf-8")
    manifest["canonical_text"] = str(transcript_path)
    return BilibiliTranscriptResult(
        status="transcript_ready",
        content_type="bilibili_video",
        source_url=source_url,
        asset_dir=asset_dir,
        canonical_text_path=transcript_path,
        asset_manifest=manifest,
    )


def _write_metadata(path: Path, metadata: BilibiliMetadata) -> None:
    payload = {
        "title": metadata.title,
        "uploader": metadata.uploader,
        "source_url": metadata.source_url,
        "canonical_url": metadata.canonical_url,
        "raw_info": metadata.raw_info,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_filename(filename: str, fallback: str) -> str:
    candidate = Path(filename).name
    return candidate or fallback


def _subtitle_to_text(subtitle: str) -> str:
    lines: list[str] = []
    for line in subtitle.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        if "-->" in stripped:
            continue
        lines.append(re.sub(r"<[^>]+>", "", stripped))
    return "\n".join(lines)


def _to_markdown_transcript(text: str) -> str:
    stripped = text.strip()
    return f"# 转写文本\n\n{stripped}\n"


def _string_from_info(info: dict[str, object], key: str, default: str) -> str:
    value = info.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _optional_string_from_info(info: dict[str, object], key: str) -> str | None:
    value = info.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _subtitle_groups(*groups: object):
    for group in groups:
        if not isinstance(group, dict):
            continue
        for language, entries in group.items():
            if isinstance(language, str) and isinstance(entries, list):
                yield language, entries
