## Why

当前 `skills/hermes-knowledge-ingest/SKILL.md` 将确定性 `km ingest` 列为默认稳定入口，`km agent-ingest` 列为可选的未来入口。阶段九 `km agent-ingest` 已经实现并可用，Hermes 应当默认使用 Deep Agents 编排路径而不是确定性路径，以获得 agent 编排的可观测性（state/trace）、产物复用自动跳过、和有限自动重试能力。

本变更将 Hermes 整理知识库的 skill 默认入口从 `km ingest` 切换到 `km agent-ingest`，使 Hermes 之后调用知识导入时默认通过 Deep Agents 编排受控 Python tools。

## What Changes

- **`skills/hermes-knowledge-ingest/SKILL.md`**：将默认调用命令从 `km ingest` 切换为 `km agent-ingest`，`km ingest` 降级为可选的备用/调试入口。更新预检查要求（增加 `agent` extra 检查），更新 agent 入口边界的表述（不再称未来，而是当前默认）。
- **`README.md`**：反映 Hermes skill 的默认入口变更，将 `km agent-ingest` 放在示例更前面。
- **`docs/project-overview.md`**：更新 Hermes 调用截面图和默认入口描述。
- **`tests/test_project_skills.py`**：更新 Hermes skill 测试，默认命令改为 `km agent-ingest`。
- 不影响 `km ingest` 和 `km agent-ingest` 的 CLI 行为、stdout 契约、退出码、配置 schema、SQLite schema、素材仓库格式或 Obsidian note 格式。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `url-routing-and-skill-skeleton`：更新 `skills/hermes-knowledge-ingest/SKILL.md` 使其默认使用 agent 编排入口。

## Impact

- 影响文件：`skills/hermes-knowledge-ingest/SKILL.md`（内容重写）、`README.md`（默认示例调整）、`docs/project-overview.md`（入口描述更新）、`tests/test_project_skills.py`（测试断言更新）。
- 不改变 `km ingest` CLI 行为、`km agent-ingest` CLI 行为、stdin/stdout 契约、退出码、配置 schema、SQLite schema、素材仓库格式或 Obsidian note 格式。
- Hermes 用户如尚未安装 `agent` extra，需要在切换后执行 `uv sync --extra agent`。
- `km ingest` 保留为确定性调试入口，不删除。
