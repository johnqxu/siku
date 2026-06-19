## Why

当前项目已有完整 `km ingest` 知识导入闭环，但 Hermes 还缺少一个面向完整流程的高层 skill 入口。现有项目内 skills 多数描述内部流水线能力，不适合让 Hermes 直接编排下载、解析、总结和写入步骤。

本变更新增一个 Hermes-facing skill，让 Hermes 只调用稳定 CLI 边界并解释结构化结果，同时继续禁止 Hermes 直接调用内部 Python tools 或写项目状态。

## What Changes

- 新增 `skills/hermes-knowledge-ingest/SKILL.md`，作为 Hermes 托管完整知识导入流程的单一高层入口。
- skill 当前阶段固定指导 Hermes 在 `/home/xu/workspace/siku` 运行 `uv run --env-file .env km ingest`，并通过 stdin 传入单个 `{"url":"...","mode":"ingest"}` JSON object。
- skill 记录轻量预检查：当前目录、`.env`、`KM_CONFIG`、`DEEPSEEK_API_KEY`。
- skill 明确不执行额外重试，失败时保留 CLI stdout JSON 的 `ok`、`error_code`、`message` 和 `recoverable` 字段，并由 Hermes 根据 `recoverable` 做 workflow 层决策。
- skill 明确 `processed_ready`、`skipped_existing` 的 Hermes 决策含义。
- skill 禁止 Hermes 直接调用 `route_url`、`collect_bilibili_text`、`generate_summary`、`write_obsidian_note` 等内部流水线 tools。
- skill 记录阶段九实现后显式切换到 `uv run --extra agent --env-file .env km agent-ingest`，且不允许自动 fallback 到 `km ingest`。
- 更新项目 skill 测试，覆盖新增 Hermes 高层 skill 的存在性、命令、预检查、边界、重试和迁移说明。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `url-routing-and-skill-skeleton`: 扩展项目内 skills 骨架，新增 Hermes 完整知识导入高层 skill 及其边界要求。

## Impact

- 影响文件：新增 `skills/hermes-knowledge-ingest/SKILL.md`。
- 影响测试：扩展 `tests/test_project_skills.py` 或等价项目 skill 测试。
- 不改变 `km ingest` CLI 契约、stdout JSON 字段、退出码、配置 schema、SQLite schema、素材仓库格式或 Obsidian note 格式。
- 不新增依赖。
