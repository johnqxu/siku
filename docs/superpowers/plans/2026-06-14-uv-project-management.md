# uv 项目管理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工程的 Python 项目管理、依赖锁定、命令运行和本地虚拟环境约定统一到 `uv`。

**Architecture:** 保留现有 PEP 621 `pyproject.toml` 作为项目元数据入口，使用 `uv_build` 构建后端保留 `km` console script，由 `uv` 生成并维护 `uv.lock`。本地环境使用 `uv sync` 自动创建和同步 `.venv/`，所有开发命令通过 `uv run` 执行。

**Tech Stack:** Python 3.11、uv、uv_build、unittest。

---

### Task 1: 固定 uv 项目约定

**Files:**
- Create: `.python-version`
- Modify: `.gitignore`
- Modify: `pyproject.toml`
- Generate: `uv.lock`

- [x] **Step 1: 固定本地开发 Python 版本**

Create `.python-version`:

```text
3.11
```

- [x] **Step 2: 忽略本地 uv 生成物**

Modify `.gitignore`:

```gitignore
.venv/
.uv-cache/
```

- [x] **Step 3: 配置 uv 构建后端**

Modify `pyproject.toml` to use the uv build backend while preserving the existing top-level `km/` package:

```toml
[build-system]
requires = ["uv_build>=0.11.19,<0.12.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "km"
module-root = ""
```

- [x] **Step 4: 生成锁文件**

Run:

```bash
UV_CACHE_DIR=/home/xu/workspace/siku/.uv-cache uv lock
```

Expected: creates or updates `uv.lock` without changing application code.

### Task 2: 更新中文文档

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-06-13-knowledge-ingest-cli-design.md`
- Modify: `openspec/changes/add-cli-contract-skeleton/design.md`
- Modify: `openspec/config.yaml`

- [x] **Step 1: README 使用 uv 命令**

Document:

```bash
uv sync
uv run python -m unittest discover -s tests -v
KM_CONFIG=/path/to/config.toml uv run km ingest
```

- [x] **Step 2: 设计文档记录 uv 决策**

Document that `uv` manages dependencies, `uv.lock`, command execution, and `.venv/`; `.venv/` is local-only and not committed.

### Task 3: 验证 uv 管理方式

**Files:**
- Read: `uv.lock`
- Read: `.venv/`

- [x] **Step 1: 同步环境**

Run:

```bash
UV_CACHE_DIR=/home/xu/workspace/siku/.uv-cache uv sync
```

Expected: `uv` creates or updates `.venv/` and installs the project.

- [x] **Step 2: 通过 uv 运行测试**

Run:

```bash
UV_CACHE_DIR=/home/xu/workspace/siku/.uv-cache uv run python -m unittest discover -s tests -v
```

Expected: all CLI contract tests pass.

- [x] **Step 3: 通过 uv 运行 CLI**

Run:

```bash
printf '' > /tmp/km-empty-config.toml
printf '{"url":"https://example.com"}' | UV_CACHE_DIR=/home/xu/workspace/siku/.uv-cache KM_CONFIG=/tmp/km-empty-config.toml uv run km ingest
```

Expected: stdout is a single JSON object with `error_code` equal to `NOT_IMPLEMENTED`.
