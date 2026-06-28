# Remove Km Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the public deterministic `km ingest` entrypoint while preserving the underlying collector, summary, index, and Obsidian modules used by `km agent-ingest`.

**Architecture:** `km.__main__.main()` will expose only `agent-ingest`. Unknown commands, including `ingest`, return the existing `INPUT_INVALID` JSON error. Existing domain, summary, web article, Bilibili, Whisper, index, and Obsidian modules remain importable for agent controlled tools.

**Tech Stack:** Python 3.11, `unittest`, project `km` console script, Deep Agents optional extra.

## Global Constraints

- Do not delete bottom-layer pipeline modules used by `AgentToolbox`.
- Do not change the JSON stdin payload contract used by `km agent-ingest`.
- Keep stdout as a single JSON object for CLI errors.
- Update runtime skill docs so Hermes only sees `km agent-ingest`.

---

### Task 1: Replace Public CLI Tests For Removed Command

**Files:**
- Modify: `tests/test_cli_contract.py`

**Interfaces:**
- Consumes: `km.__main__.main()`
- Produces: regression coverage that `km ingest` is no longer supported and returns `INPUT_INVALID`.

- [ ] **Step 1: Write failing tests**

Replace legacy deterministic `km ingest` contract tests with focused tests:

```python
def test_ingest_command_is_removed(self):
    result = self.run_cli("ingest", '{"url":"https://example.com"}')
    self.assertEqual(result.returncode, 1)
    response = self.parse_stdout_json(result)
    self.assertFalse(response["ok"])
    self.assertEqual(response["error_code"], "INPUT_INVALID")

def test_main_rejects_ingest_without_loading_config_or_runner(self):
    with (...):
        exit_code = main()
    self.assertEqual(exit_code, 1)
    load_config.assert_not_called()
    runner.assert_not_called()
```

- [ ] **Step 2: Run red verification**

Run: `uv run python -m unittest tests.test_cli_contract -v`
Expected: the new removed-command assertions fail while old `km ingest` code is still present.

- [ ] **Step 3: Remove deterministic CLI branch**

Modify `km/__main__.py` so only `agent-ingest` is accepted. Delete deterministic pipeline helper functions and unused imports from this module only.

- [ ] **Step 4: Run green verification**

Run: `uv run python -m unittest tests.test_cli_contract tests.test_agent_runner_cli -v`
Expected: all selected tests pass.

### Task 2: Remove Runtime Documentation References

**Files:**
- Modify: `skills/hermes-knowledge-ingest/SKILL.md`
- Modify: `skills/url-routing/SKILL.md`
- Modify: `tests/test_project_skills.py`
- Modify: `README.md`
- Modify: `docs/project-overview.md`

**Interfaces:**
- Consumes: the project skill text tests.
- Produces: docs and skills that no longer present `km ingest` as a supported path.

- [ ] **Step 1: Write failing documentation assertions**

Update `tests/test_project_skills.py` to assert `uv run --env-file .env km ingest` is absent from Hermes skill text and that `km agent-ingest` remains documented.

- [ ] **Step 2: Run red verification**

Run: `uv run python -m unittest tests.test_project_skills -v`
Expected: assertions fail until docs are updated.

- [ ] **Step 3: Update docs and skill text**

Remove `km ingest` examples and fallback/debug language from current runtime docs and skills. Preserve archived OpenSpec history.

- [ ] **Step 4: Run green verification**

Run: `uv run python -m unittest tests.test_project_skills -v`
Expected: tests pass.

### Task 3: Final Verification

**Files:**
- No new production files.

**Interfaces:**
- Consumes: all changed tests and CLI code.
- Produces: verified removal of public `km ingest` entrypoint.

- [ ] **Step 1: Search active runtime references**

Run: `rg -n "uv run --env-file \\.env km ingest|km ingest|\\[\\\"km\\\", \"ingest\"\\]" README.md docs/project-overview.md skills tests km -S`
Expected: no active runtime/test references to supported `km ingest`; archived OpenSpec history may still mention it.

- [ ] **Step 2: Run targeted tests**

Run: `uv run python -m unittest tests.test_cli_contract tests.test_agent_runner_cli tests.test_project_skills -v`
Expected: all selected tests pass.

- [ ] **Step 3: Check diff hygiene**

Run: `git diff --check`
Expected: no whitespace errors.
