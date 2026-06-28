from __future__ import annotations

import json
import sys

from .agent_runner import AgentIngestRunner
from .config import load_config
from .errors import KmError, input_invalid, internal_error
from .models import failure_response


def write_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] != "agent-ingest":
        error = input_invalid("未知命令。")
        write_json(failure_response(error))
        return error.exit_code

    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        error = input_invalid("stdin 必须是合法 JSON。")
        write_json(failure_response(error))
        return error.exit_code

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


if __name__ == "__main__":
    raise SystemExit(main())
