#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/test_agent_ingest.sh <url>" >&2
  exit 64
fi

cd "$(dirname "$0")/.."

uv run --extra agent --env-file .env km agent-ingest <<JSON
{"url":"$1","mode":"ingest"}
JSON
