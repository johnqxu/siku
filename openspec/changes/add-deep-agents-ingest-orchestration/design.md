## Context

当前项目已有 `km ingest` 的确定性端到端路径：URL 输入、配置校验、URL 规范化、重复来源查询、Bilibili 或网页文本化、领域分类、中文总结、Obsidian note 写入和 SQLite `processed` 标记。这个路径由 Python 代码直接编排，适合作为稳定回归基线，但还没有真正使用 Deep Agents 作为运行时编排器。

阶段九要新增 `km agent-ingest`：Hermes 只调用这个命令，命令内部启动 Deep Agents runtime，由 Deep Agents 在受控状态机内编排项目内 Python tools。Deep Agents 负责“下一步调用哪个 tool”，但不直接访问文件系统、SQLite、Obsidian、下载器、Whisper 或 LLM；所有副作用都由受控 Python tools 执行。

相关约束：

- 文档和用户可见内容使用中文；命令、JSON 字段、错误码、路径和代码标识保持原文。
- `km ingest` 保留为确定性 CLI 基线，不被阶段九替换。
- `km agent-ingest` 不自动 fallback 到 `km ingest`。
- Deep Agents 只看编排元数据和 tool 描述，不读取完整 transcript/content、HTML、prompt、模型输出、API key 或 cookie。
- 不修改 SQLite schema，不新增内容源，不改变 Bilibili、网页、总结或 Obsidian note 格式。

## Goals / Non-Goals

**Goals:**

- 新增 `km agent-ingest` 命令，作为 Hermes 调用 Deep Agents 编排路径的入口。
- 使用 Deep Agents runtime 编排中等粒度 Python tools，完成 URL 到 `processed_ready` 的闭环。
- 使用 Python 状态机 guard 强制合法 tool 转移，避免仅依赖 prompt 约束。
- 为每个来源写入 `<asset_dir>/agent/state.json` 和 `<asset_dir>/agent/trace.jsonl`，提供可观察自动模式。
- 支持默认复用已有成功产物，降低下载、Whisper 和 LLM 成本。
- 支持网络/API/下载类错误每个 tool 最多自动重试 1 次。
- 新增 `AgentRuntime` 适配层和 `FakeAgentRuntime`，让默认测试不依赖真实 Deep Agents runtime。
- 新增 `agent` optional extra 和 `llm.tasks.agent_orchestration` 配置引用。
- 更新项目内 `skills/*.md`，让它们成为 Deep Agents runtime 读取的指令资产。

**Non-Goals:**

- 不让 Hermes 直接编排项目内 tools。
- 不替换或删除 `km ingest`。
- 不自动 fallback 到 `km ingest`。
- 不支持交互确认模式。
- 不支持 `force`、`rerun_from`、`dry_run` 或批处理。
- 不让 Deep Agents 直接读完整正文、写素材仓库、写 SQLite 或写 Obsidian。
- 不拆分 Bilibili 内部元数据、字幕、音频和 Whisper 为 agent 可见 tools。
- 不新增 SQLite 表或字段。
- 不把真实 Deep Agents 集成测试放入默认 `unittest discover`。

## Decisions

### 1. 新增 `km agent-ingest`，保留 `km ingest`

阶段九新增独立命令：

```bash
uv run --extra agent --env-file .env km agent-ingest <<'JSON'
{"url":"https://example.com","mode":"ingest"}
JSON
```

无字幕 Bilibili 场景需要同时启用 GPU extra：

```bash
uv run --extra agent --extra gpu --env-file .env km agent-ingest <<'JSON'
{"url":"https://www.bilibili.com/video/BV...","mode":"ingest"}
JSON
```

选择独立命令而不是 `km ingest --orchestrator deep_agents` 的原因是：现有 `km ingest` 契约保持稳定，Hermes 可以明确选择 agent 路径，测试和失败边界也更清楚。`km agent-ingest` 不自动 fallback 到 `km ingest`，否则会掩盖 Deep Agents 编排问题。

### 2. Deep Agents 只在项目内部编排，Hermes 不直接编排 tools

调用链为：

```text
Hermes
  -> km agent-ingest
    -> Deep Agents runtime
      -> AgentRuntime adapter
        -> Python 状态机 guard
          -> 受控 Python tools
```

Hermes 只负责传入 URL 并读取 stdout JSON。项目内 tools、状态机、skills 和 trace 都是 `km agent-ingest` 的内部实现细节。

### 3. 使用同进程中等粒度 Python tools

Deep Agents 可见 tools 为：

```text
route_url
prepare_source_workspace
collect_bilibili_text
collect_web_article_text
classify_domain
generate_summary
write_obsidian_note
mark_source_processed
```

`collect_bilibili_text` 内部仍封装元数据、字幕、音频下载和 Whisper 转写；`collect_web_article_text` 内部仍封装 HTTP fetch、微信公众号 parser 和 `trafilatura` fallback。这个粒度与既有研发阶段一致，既让 Deep Agents 参与编排，又避免把 Bilibili 内部复杂度暴露给 agent。

### 4. 使用 Python 状态机 guard 作为安全边界

Deep Agents 可以选择下一步，但每次 tool 调用前必须经过 Python guard。合法状态转换为：

```text
initialized -> route_url -> routed
routed -> prepare_source_workspace -> workspace_ready
workspace_ready -> collect_bilibili_text|collect_web_article_text -> text_ready
text_ready -> classify_domain -> domain_ready
domain_ready -> generate_summary -> summary_ready
summary_ready -> write_obsidian_note -> note_ready
note_ready -> mark_source_processed -> processed_ready
```

如果 agent 在错误 stage 调用 tool，guard 返回 `AGENT_INVALID_TRANSITION`，不执行副作用，不自动重试，并记录 trace。prompt 不是安全边界，状态机才是。

### 5. `prepare_source_workspace` 单独作为 tool

`prepare_source_workspace` 负责初始化本次 agent 运行的基础上下文，包括生成 `source_id`、初始化素材目录和 SQLite、检查 `processed` 重复来源、创建 `agent/` 目录、初始化 state/trace。

如果 SQLite 命中同一 `normalized_url` 且 `status = 'processed'`，该 tool 直接推进到 `processed_ready` 并由 runner 返回 `skipped_existing`。这种情况下仍创建或追加 agent trace/state，但不执行后续采集、分类、总结或写入 tools。

### 6. state 快照和 trace 事件放在素材仓库

每个来源新增：

```text
<asset_dir>/agent/state.json
<asset_dir>/agent/trace.jsonl
```

`state.json` 只保存最新快照，包括 `schema_version`、`orchestrator`、`source_id`、`original_url`、`normalized_url`、`content_type`、`stage`、各产物路径、最近错误和 `updated_at`。

`trace.jsonl` 追加写入历史事件。每次 `km agent-ingest` 创建新的 `run_id`，写入 `run_started`、tool attempt、`run_finished` 或 `run_failed`。trace 不记录完整正文、完整 prompt、完整模型输出、API key 或 cookie。

选择素材仓库 JSON 而不是 SQLite 的原因是：agent 编排状态属于运行过程细节，和 source 素材强绑定；SQLite 继续只表示最终业务状态，不升级 schema。

### 7. 默认复用已有成功产物，暂不支持 force

每个 tool 执行前先校验自己的目标产物：

- 规范文本存在且合法，则文本化 tool 可返回 `text_ready` 且 `skipped = true`。
- `summary/domain.json` 存在且合法，则分类 tool 可返回 `domain_ready` 且 `skipped = true`。
- `summary/summary.json` 存在且合法，则总结 tool 可返回 `summary_ready` 且 `skipped = true`。
- 同 `source_id` 的 Obsidian note 可按现有幂等规则复用或覆盖。
- SQLite 已 `processed` 则直接返回 `skipped_existing`。

首版不支持 `force` 或 `rerun_from`，避免引入下游产物失效和级联重跑规则。未来可以单独设计重跑能力。

### 8. 有限自动重试

网络/API/下载类错误每个 tool 最多自动重试 1 次，包括：

```text
WEB_FETCH_FAILED
BILIBILI_METADATA_FAILED
BILIBILI_SUBTITLE_FAILED
BILIBILI_AUDIO_DOWNLOAD_FAILED
LLM_REQUEST_FAILED
```

输入、配置、schema、本地 runtime、Whisper、Obsidian 和 SQLite 写入错误不自动重试。`LLM_SCHEMA_INVALID` 和 `SUMMARY_SCHEMA_INVALID` 首版也不重试，避免让 agent 做 JSON 修复或重问策略。

### 9. 使用 `AgentRuntime` 适配层

`km agent-ingest` 依赖项目内 `AgentRuntime` 接口，而不是直接在业务入口到处 import Deep Agents 框架 API。生产实现为 `DeepAgentsRuntime`，测试实现为 `FakeAgentRuntime`。

这样可以：

- 集中处理缺少 `agent` extra 的 `AGENT_RUNTIME_UNAVAILABLE`。
- 隔离 Deep Agents API 变化。
- 让默认单元测试不依赖真实 agent runtime、网络或 agent 模型。

### 10. Deep Agents 使用独立模型引用

配置新增：

```toml
[llm.tasks]
agent_orchestration = "deepseek_v4_flash"
```

模型仍在 `[llm.models.<ref>]` 统一定义。该模型只用于 agent 编排决策，不用于领域分类或中文总结。阶段九推荐使用 `deepseek_v4_flash`，因为状态机已经限制编排空间，内容质量仍由总结模型负责。

### 11. Deep Agents 读取项目内 skills 作为指令资产

`km agent-ingest` 启动时读取项目内 `skills/*.md`，作为 system prompt 或 tool context 的组成部分。必需 skill 缺失、不可读或为空时返回 `AGENT_SKILL_MISSING`。

读取 skill 不授予 agent 副作用权限。真实能力仍由 tool schema、Python tool 和状态机 guard 决定。阶段九需要更新旧 skill 中“当前阶段不接入 Deep Agents”的表述。

### 12. stdout 响应复用现有 envelope 并增加 agent 字段

成功响应复用现有字段，并新增：

```json
{
  "orchestrator": "deep_agents",
  "trace_path": ".../agent/trace.jsonl",
  "state_path": ".../agent/state.json"
}
```

失败响应保持 `ok`、`error_code`、`message`、`recoverable`，在 asset context 可用时同样增加 `orchestrator`、`trace_path` 和 `state_path`。stdout 只输出一个 JSON object；日志和诊断不得写入 stdout。

### 13. 固定 `max_tool_steps = 12`

正常路径约 7 个 tool 步骤。考虑 1 次自动重试和少量 agent 误判，首版固定 `max_tool_steps = 12`。超限返回 `AGENT_ORCHESTRATION_FAILED`，写入 `run_failed` trace，不做配置化。

### 14. ToolResult 统一结构

所有 agent tools 返回统一结构，包含 `ok`、`tool`、`status`、`stage_before`、`stage_after`、`skipped`、`skip_reason`、路径字段、`domain`、`title` 或错误字段。ToolResult 不直接构造最终 stdout；最终响应由 runner 根据最终 state 和 tool result 构造。

## Risks / Trade-offs

- [Risk] Deep Agents 框架 API 不稳定。  
  Mitigation: 使用 `AgentRuntime` 适配层隔离真实 runtime，默认测试使用 `FakeAgentRuntime`。

- [Risk] agent 尝试跳过步骤或调用错误 tool。  
  Mitigation: Python 状态机 guard 强制合法转移，非法调用返回 `AGENT_INVALID_TRANSITION`。

- [Risk] trace 文件长期追加会变大。  
  Mitigation: 单个来源运行次数通常有限，首版接受 append-only；未来如需要可设计 trace rotation。

- [Risk] 读取 skills 增加 prompt token 消耗。  
  Mitigation: 只读取编排相关 skill，不读取完整正文；后续可压缩 skill 内容。

- [Risk] `km agent-ingest` 比 `km ingest` 多一层 agent 运行失败模式。  
  Mitigation: 保留 `km ingest` 独立入口；agent 路径不自动 fallback，失败原因通过 `AGENT_*` 错误码和 trace 暴露。

- [Risk] 默认复用已有产物可能复用外部篡改文件。  
  Mitigation: 每个 tool 在复用前必须做 schema 和上下文校验，不合法则重新执行或返回相应输入/schema 错误。

## Migration Plan

1. 新增 agent 配置、错误码、响应字段和 `agent` optional extra。
2. 新增 state/trace recorder、状态机 guard 和 ToolResult 数据结构。
3. 新增中等粒度 agent tool wrappers，复用现有 pipeline 模块。
4. 新增 `AgentRuntime`、`DeepAgentsRuntime` 和 `FakeAgentRuntime`。
5. 新增 `km agent-ingest` CLI 入口。
6. 更新项目内 skills、README 和 OpenSpec specs。
7. 使用默认单元测试验证 fake runtime 和协议边界。
8. 提供真实 Deep Agents 手动验证命令，但不纳入默认测试。

回滚策略：如 agent 路径不可用，可停止使用 `km agent-ingest`，继续使用现有 `km ingest`。本阶段不修改 SQLite schema，也不改变现有素材产物格式，因此回滚不会破坏已有导入数据。

## Open Questions

无。当前阶段已经确认不做 force/rerun、交互模式、批处理、自动 fallback、SQLite schema migration、完整正文注入 agent context 或默认真实 Deep Agents 测试。
