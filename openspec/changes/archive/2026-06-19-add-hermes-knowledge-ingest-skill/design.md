## Context

当前项目已有完整 `km ingest` 确定性闭环，可以从单个 URL 完成下载或解析、领域分类、中文总结、Obsidian 写入和 SQLite `processed` 标记。项目内也已有多个 `skills/*.md`，但这些 skills 主要面向内部 Deep Agents 或受控 tools 的流水线能力，例如 URL 路由、Bilibili 导入、网页文章导入、中文总结和 Obsidian 写入。

Hermes 需要的是更高层的入口：给一个 URL，调用项目稳定边界，拿到结构化结果并决定是否完成、跳过或稍后重试。Hermes 不应理解或编排内部 Python tools，也不应直接写素材仓库、SQLite 或 Obsidian。

阶段九 `km agent-ingest` 仍是独立提案，尚未实施。因此本变更以当前稳定可用的 `km ingest` 为执行入口，同时在 skill 中记录未来显式切换到 `km agent-ingest` 的迁移规则。

## Goals / Non-Goals

**Goals:**

- 新增 `skills/hermes-knowledge-ingest/SKILL.md`，作为 Hermes 调用完整知识导入流程的单一高层 skill。
- 明确当前执行命令为 `cd /home/xu/workspace/siku` 后运行 `uv run --env-file .env km ingest`。
- 明确 stdin JSON、轻量预检查、stdout JSON 解释规则和失败决策规则。
- 禁止 Hermes 直接调用内部流水线 tools。
- 禁止 skill 自己做额外重试，避免和 CLI 内部重试叠加。
- 记录未来切换到 `km agent-ingest` 时必须显式修改 skill，且不自动 fallback。
- 增加测试覆盖，确保 skill 文档不会把 Hermes 边界放宽。

**Non-Goals:**

- 不实现 `km agent-ingest`。
- 不改变 `km ingest` 的 stdin/stdout 契约、退出码或错误码。
- 不新增 batch、dry run、force、rerun 或交互确认。
- 不让 Hermes 读取完整 note、summary、transcript、HTML、audio 或其他生成文件内容。
- 不让 Hermes 调用 `route_url`、`collect_bilibili_text`、`generate_summary` 等内部 tools。
- 不新增依赖，不修改 SQLite schema，不改变素材仓库或 Obsidian note 格式。

## Decisions

### 1. 新增独立 Hermes 高层 skill

新增文件：

```text
skills/hermes-knowledge-ingest/SKILL.md
```

选择带 `hermes-` 前缀，是为了和现有内部流水线 skills 区分。`bilibili-ingest`、`summary-generation`、`obsidian-write` 等描述“某个内部阶段怎么做”；`hermes-knowledge-ingest` 描述“Hermes 应该如何调用完整能力”。

替代方案是把 Hermes 入口说明塞进现有 `url-routing` 或 README，但这会混淆 skill 的消费对象。Hermes 需要一个清晰入口，不需要阅读所有内部 skill。

### 2. 当前阶段调用 `km ingest`

skill 当前命令固定为：

```bash
cd /home/xu/workspace/siku
uv run --env-file .env km ingest
```

这是因为 `km ingest` 已经实现并可验证完整闭环，而 `km agent-ingest` 仍在阶段九提案中。选择当前稳定入口可以让 Hermes 立刻托管完整流程。

替代方案是直接写未来的 `km agent-ingest`，但那会让 skill 在实现前不可用。另一个替代方案是同时描述两个入口，但容易诱导自动 fallback，掩盖 agent 编排失败。

### 3. 只做轻量预检查

skill 只要求 Hermes 确认：

- 当前工作目录是 `/home/xu/workspace/siku`。
- `.env` 可用。
- `.env` 提供 `KM_CONFIG`。
- `DEEPSEEK_API_KEY` 已配置。

完整配置校验、URL 校验、素材仓库、Obsidian、SQLite、Whisper 和下载器错误仍由 CLI 返回结构化 JSON。这样避免把 CLI 的校验逻辑复制到 skill 文档中。

### 4. stdout JSON 是事实来源

skill 不重写 CLI stdout JSON。Hermes 根据 JSON 字段决策：

- `status: "processed_ready"` 表示完整导入完成。
- `status: "skipped_existing"` 表示已处理，无需重复导入。
- `recoverable: true` 表示 Hermes 可在工作流层稍后重试。
- `recoverable: false` 表示 Hermes 应停止并报告用户。

stderr 只用于日志和诊断，不是权威结果。

### 5. skill 不额外重试

CLI 是唯一可执行内部有限重试的层。Hermes skill 不应对同一调用自行 retry，否则会导致双重重试、重复下载或更难解释的失败 trace。

Hermes 可以在工作流层基于 `recoverable: true` 安排稍后重试，但这不是 skill 内部循环。

### 6. 未来 `km agent-ingest` 迁移必须显式完成

阶段九实现后，skill 可以改为：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

该迁移必须作为显式变更完成，不允许从 `km agent-ingest` 自动 fallback 到 `km ingest`。自动 fallback 会把 Deep Agents 编排错误伪装成确定性路径成功，降低可观测性。

## Risks / Trade-offs

- [Risk] 当前 skill 调用 `km ingest`，和未来 Deep Agents 终局入口不同。  
  Mitigation: 在 skill 中明确这是当前阶段入口，并记录未来显式迁移命令。

- [Risk] Hermes 可能误以为可以读取返回路径里的完整文件内容。  
  Mitigation: skill 明确默认只使用 stdout JSON 和路径字段做跟踪，不主动读取生成文件内容。

- [Risk] skill 文档过多复制 CLI 契约，未来 CLI 契约变化时需要同步。  
  Mitigation: skill 只解释最小稳定字段和决策规则，不复制完整 README 或全部错误码。

- [Risk] 双重重试导致重复副作用。  
  Mitigation: skill 明确不增加自己的重试循环，只允许 Hermes 在 workflow 层基于 `recoverable` 稍后重试。

## Migration Plan

1. 新增 `skills/hermes-knowledge-ingest/SKILL.md`。
2. 更新项目 skill 测试，覆盖新增 skill 的命令、预检查、输出解释、重试边界、内部工具禁用和未来迁移说明。
3. 运行默认单元测试中与 project skills 相关的测试。

回滚策略：删除新增 skill 文件并移除对应测试即可，不影响 `km ingest`、素材仓库、SQLite 或 Obsidian 数据。

## Open Questions

无。当前设计已确认：Hermes 只需要一个高层 skill；skill 当前调用 `km ingest`；不额外重试；输出采用 CLI JSON 透传加决策说明；默认不读取生成文件内容。
