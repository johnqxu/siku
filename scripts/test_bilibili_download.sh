#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  scripts/test_bilibili_download.sh --help
  COOKIE='SESSDATA=...' scripts/test_bilibili_download.sh <bilibili-url> <output-dir>

用途:
  手动诊断 Bilibili 元数据、字幕和音频下载能力。该脚本不会写入 SQLite 或 Obsidian。

环境变量:
  COOKIE  可选。需要登录态时传入 Bilibili cookie。
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

url="$1"
output_dir="$2"
mkdir -p "$output_dir"

common_args=(
  --user-agent "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
  --add-header "Referer: https://www.bilibili.com"
  --add-header "Origin: https://www.bilibili.com"
)

if [[ -n "${COOKIE:-}" ]]; then
  common_args+=(--add-header "Cookie: ${COOKIE}")
fi

yt-dlp "${common_args[@]}" --dump-single-json "$url" > "$output_dir/metadata.json"
yt-dlp "${common_args[@]}" --skip-download --write-subs --write-auto-subs --sub-langs "zh-CN,zh-Hans,zh" -o "$output_dir/subtitle.%(ext)s" "$url"
yt-dlp "${common_args[@]}" --extract-audio --audio-format m4a -o "$output_dir/audio.%(ext)s" "$url"
