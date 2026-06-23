## Context

`km agent-ingest` 自阶段九实施后已经稳定可用。Hermes 知识导入 skill 当前仍把 `km ingest` 列为默认入口，仅在"agent 入口边界"一节记录未来可以显式使用 `km agent-ingest`。

实际的 Deep Agents 编排路径具备多项优势：自动产物复用跳过降低重复下载和 LLM 成本、state/trace 提供运行可观测性、状态机 guard 防止 agent 误操作、有限自动重试减少瞬时网络失败。Hermes 应该默认走 agent 路径，只在需要确定性调试或验证基线时才使用 `km ingest`。

## Goals / Non-Goals

**Goals:**

- 将 `skills/hermes-knowledge-ingest/SKILL.md` 的默认入口从 `km ingest` 改为 `km agent-ingest`。
- 更新预检查要求，增加 `agent` extra 的检查声明。
- 将 `km ingest` 降级为可选的备用/调试入口，保留在 skill 文档中但不作为推荐路径。
- 更新 README 和 project-overview 的默认示例顺序。
- 更新项目 skill 测试，确认 skill 文档默认命令为 `km agent-ingest`。

**Non-Goals:**

- 不改变 `km ingest` CLI 行为或 stdin/stdout 契约。
- 不改变 `km agent-ingest` CLI 行为或 stdin/stdout 契约。
- 不删除、不弃用 `km ingest` 代码路径。
- 不修改 SQLite schema、素材仓库格式、Obsidian note 格式、配置 schema、错误码或退出码。
- 不改变其他项目内 skill（`bilibili-ingest`、`web-article-ingest`、`domain-classification` 等）。
- 不改变 `km agent-ingest` 的自动回退规则（仍不允许从 agent 路径 fallback 到 `km ingest`）。

## Decisions

### 1. 修改 skill 默认命令，保留 `km ingest` 作为调试备用

新 skill 结构：

```markdown
## 当前默认调用命令

推荐入口是 `km agent-ingest`，由项目内 Deep Agents 编排受控 Python tools：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

需要确定性直接编排（调试、验证确定性基线）时，使用 `km ingest`：

```bash
cd /home/xu/workspace/siku
uv run --env-file .env km ingest
```
```

选择保留 `km ingest` 引用而不是完全删除的原因是：`km ingest` 是确定性基线，在调试 agent 路径失败原因、验证 regressions 时仍有价值。但 skill 默认路径必须是 `km agent-ingest`，因为 Hermes 每次调用知识导入都应该享受 agent 编排带来的可观测性和正确性保障。

### 2. 更新预检查要求

新 skill 的预检查增加 `agent` extra 检查点：

- 当前工作目录是 `/home/xu/workspace/siku`。
- 该目录下存在可用的 `.env`。
- `.env` 提供 `KM_CONFIG`。
- `DEEPSEEK_API_KEY` 已通过 `.env` 或继承环境配置。
- 配置包含 `[llm.tasks] agent_orchestration` 引用（`km agent-ingest` 必需）。
- 如需调用 `km agent-ingest`，确认已安装 `agent` extra（`uv sync --extra agent`）。

### 3. 更新 README 和 project-overview 的示例顺序

README 的"快速开始"和"深入"部分将 `km agent-ingest` 放在首位置，`km ingest` 作为可选替代。project-overview 更新调用截面图和默认入口描述，标注 `km agent-ingest` 为当前 Hermes 推荐入口。

### 4. Hermes skill 的"agent 入口边界"中的迁移说明不再适用

原有"阶段九实现后，也可以显式选择 Deep Agents 编排入口"等未来迁移说明已过时。新 skill 直接以 `km agent-ingest` 为默认，不再使用"未来"、"阶段九"等表述。

### 5. 不影响 CLI 代码

本变更只影响 skill 文档、项目文档和测试断言。`km/__main__.py`、`km/agent_runner.py`、`km/agent_runtime.py` 和所有其他 Python 模块均无需修改。

## Risks / Trade-offs

- [Risk] Hermes 用户可能尚未安装 `agent` extra，默认命令会返回 `AGENT_RUNTIME_UNAVAILABLE`。  
  Mitigation: skill 预检查中明确声明需要 `uv sync --extra agent`；如果 Hermes 确实遇到该错误，可根据 `recoverable: true` 安装 extra 后重试。

- [Risk] `km agent-ingest` 需要配置 `agent_orchestration` 模型引用，`km ingest` 不需要。  
  Mitigation: skill 预检查包含 `agent_orchestration` 配置校验的声明。

- [Risk] `km agent-ingest` Hermes 可见的响应契约比 `km ingest` 多 `orchestrator`、`trace_path` 和 `state_path` 字段。  
  Mitigation: 已在原 skill 的输出处理章节记录了这些字段。Hermes 按原字段解析业务结果，agent 字段仅用于任务跟踪和调试，不解释为业务字段。

## Migration Plan

1. 创建本 OpenSpec 提案。
2. 重写 `skills/hermes-knowledge-ingest/SKILL.md`，默认命令切换为 `km agent-ingest`，`km ingest` 降级为调试备用。
3. 更新 `README.md`，`km agent-ingest` 放在示例更前面。
4. 更新 `docs/project-overview.md`，更新默认入口描述。
5. 更新 `tests/test_project_skills.py`，默认命令断言改为 `km agent-ingest`。
6. 运行 `openspec validate switch-hermes-skill-to-agent-ingest --strict`。
7. 运行 `uv run python -m unittest tests.test_project_skills -v`。
8. 提交并推送变更。

回滚策略：回滚 skill 文档、README、project-overview 和测试声明，使默认入口恢复为 `km ingest`。不影响 CLI 代码、SQLite 或素材仓库。

## Open Questions

无。
