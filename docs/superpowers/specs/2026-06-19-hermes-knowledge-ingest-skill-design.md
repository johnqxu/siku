# Hermes Knowledge Ingest Skill Design

## Goal

Add one high-level project skill for Hermes to manage the complete knowledge ingest workflow: receive a URL, call the current stable CLI, and interpret the structured result without exposing internal pipeline tools.

This skill is a Hermes-facing entry point. It is not an internal Deep Agents sub-skill and does not grant Hermes permission to call project Python tools directly.

## Skill Location

Create the skill at:

```text
skills/hermes-knowledge-ingest/SKILL.md
```

The name is intentionally explicit. Existing skills such as `bilibili-ingest`, `summary-generation`, and `obsidian-write` describe internal pipeline capabilities. `hermes-knowledge-ingest` describes the single complete workflow Hermes should call.

## Current Invocation Contract

Until `km agent-ingest` is implemented, the skill uses the current stable deterministic CLI:

```bash
cd /home/xu/workspace/siku
uv run --env-file .env km ingest
```

Hermes passes exactly one JSON object on stdin:

```json
{"url":"https://example.com/article","mode":"ingest"}
```

`url` is required. `mode` should be `ingest`. The skill should not introduce batch mode, dry run, force, rerun, or interactive confirmation.

## Lightweight Preflight

Before invoking the CLI, the skill should instruct Hermes to confirm the local execution context is ready:

- Current working directory is `/home/xu/workspace/siku`.
- `.env` is available in that directory.
- `.env` provides `KM_CONFIG`.
- `DEEPSEEK_API_KEY` is configured through `.env` or the inherited environment.

The skill should not duplicate full CLI validation. Obsidian paths, asset store paths, model references, URL validity, downloader behavior, Whisper runtime, and SQLite errors remain the CLI's responsibility and must be returned through the CLI's structured JSON envelope.

## Retry Policy

The skill must not add its own retry loop.

The CLI is the only layer that may perform limited retries for recoverable internal operations. If the CLI returns a failure JSON, the skill should pass that result back to Hermes and explain the decision rule:

- `recoverable: true`: Hermes may schedule a later retry at the workflow level.
- `recoverable: false`: Hermes should stop and report the failure.

This avoids double retries between Hermes and the CLI runner.

## Output Handling

The CLI stdout JSON is the source of truth. The skill should not rewrite factual fields or hide paths.

For successful responses:

- `status: "processed_ready"` means the knowledge item has been downloaded or parsed, summarized, written to Obsidian, and marked processed.
- `status: "skipped_existing"` means SQLite already has a processed record for the normalized URL and Hermes should not repeat the import.

For failures:

- Preserve `ok`, `error_code`, `message`, and `recoverable`.
- Do not convert business errors into conversational summaries only.
- Do not parse stderr as the authoritative result.

Hermes may use returned paths such as `note_path`, `asset_dir`, `canonical_text_path`, `domain_path`, and `summary_path` for tracking. By default, Hermes should not read note, summary, transcript, HTML, audio, or other generated files after success. If a later workflow needs file content, that should be a separate explicit capability.

## Boundary Rules

Hermes must not call internal pipeline tools directly:

- `route_url`
- `prepare_source_workspace`
- `collect_bilibili_text`
- `collect_web_article_text`
- `classify_domain`
- `generate_summary`
- `write_obsidian_note`
- `mark_source_processed`

Hermes should treat `km ingest` as the stable public boundary for the current phase. It should not write to the asset store, SQLite, Obsidian vault, or project skill files itself.

The skill should also remind Hermes that stdout must contain exactly one JSON object and that logs or diagnostics belong to stderr.

## Migration Path

When the Stage 9 Deep Agents entry point is implemented, update this skill to call:

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

That future change should be explicit. The skill should not automatically fallback from `km agent-ingest` to `km ingest`, because fallback would hide Deep Agents orchestration failures.

The Hermes-facing input and output decision rules should stay the same across the migration.

## Tests And Review

Implementation should add or update tests that verify:

- `skills/hermes-knowledge-ingest/SKILL.md` exists.
- The skill names `uv run --env-file .env km ingest` as the current command.
- The skill documents the lightweight preflight requirements.
- The skill forbids Hermes from calling internal tools directly.
- The skill states that it does not perform extra retries.
- The skill documents the later switch to `km agent-ingest` without automatic fallback.

Manual review should confirm the skill does not imply Hermes can read full source content, write project state, or bypass the CLI JSON contract.
