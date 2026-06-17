#!/usr/bin/env bash
set -u

URL="${1:-https://www.bilibili.com/video/BV13rLx6NEbA/?spm_id_from=333.1007.tianma.1-1-1.click&vd_source=9010daf41b729b78d3785ff7bd92abb2}"

echo "== 基础环境 =="
pwd
date
echo "KM_CONFIG=${KM_CONFIG:-未设置}"
echo "DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:+已设置}"

echo
echo "== uv =="
command -v uv || true
uv --version || true

echo
echo "== 项目依赖 =="
UV_CACHE_DIR=.uv-cache uv sync || true

echo
echo "== yt-dlp 可用性 =="
command -v yt-dlp || true
yt-dlp --version || true

echo
echo "== uv run yt-dlp 可用性 =="
UV_CACHE_DIR=.uv-cache uv run yt-dlp --version || true

echo
echo "== 配置文件 =="
if [ -n "${KM_CONFIG:-}" ]; then
  ls -l "$KM_CONFIG" || true
  sed -n '1,220p' "$KM_CONFIG" || true
else
  echo "KM_CONFIG 未设置"
fi

echo
echo "== 直接测试 yt-dlp 元数据 =="
echo "URL=$URL"
UV_CACHE_DIR=.uv-cache uv run yt-dlp \
  --dump-single-json \
  --skip-download \
  --no-warnings \
  "$URL" \
  > /tmp/km-bilibili-metadata.stdout \
  2> /tmp/km-bilibili-metadata.stderr

STATUS=$?
echo "exit_code=$STATUS"

echo
echo "== yt-dlp stderr =="
cat /tmp/km-bilibili-metadata.stderr || true

echo
echo "== yt-dlp stdout 前 2000 字符 =="
head -c 2000 /tmp/km-bilibili-metadata.stdout || true
echo

echo
echo "== 如果 stdout 是 JSON，检查关键字段 =="
python - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/km-bilibili-metadata.stdout")
text = path.read_text(encoding="utf-8", errors="replace").strip()
if not text:
    print("stdout 为空")
    raise SystemExit(0)

try:
    data = json.loads(text)
except Exception as exc:
    print(f"stdout 不是合法 JSON: {exc}")
    raise SystemExit(0)

for key in ["id", "title", "uploader", "webpage_url", "duration"]:
    print(f"{key}: {data.get(key)!r}")

print("subtitles keys:", list((data.get("subtitles") or {}).keys()))
print("automatic_captions keys:", list((data.get("automatic_captions") or {}).keys())[:20])
PY

echo
echo "== km ingest 再跑一次 =="
UV_CACHE_DIR=.uv-cache uv run km ingest <<JSON
{"url":"$URL","mode":"ingest"}
JSON
