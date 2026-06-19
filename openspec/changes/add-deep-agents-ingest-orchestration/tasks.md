## 1. TDD 测试基线

- [ ] 1.1 新增 `agent_orchestration` 配置测试，覆盖缺失任务引用、引用不存在模型、引用模型字段非法和不影响 `domain_classification` / `summary_generation`。
- [ ] 1.2 新增 `AgentRuntime` 适配层测试，覆盖 `FakeAgentRuntime` 默认测试路径、`DeepAgentsRuntime` 使用 `from deepagents import create_deep_agent` 的导入边界，以及真实 runtime 缺失返回 `AGENT_RUNTIME_UNAVAILABLE`。
- [ ] 1.3 新增 agent 状态机测试，覆盖完整合法路径、`routed -> prepare_source_workspace -> processed_ready` 重复来源跳过路径、错误 stage 调用 tool 返回 `AGENT_INVALID_TRANSITION`、非法调用不执行副作用且不重试。
- [ ] 1.4 新增 `ToolResult` 测试，覆盖成功、失败、复用跳过、错误字段和最终 stdout 不由 tool 直接构造。
- [ ] 1.5 新增 `agent/state.json` 测试，覆盖字段完整性、成功推进清空错误、失败保留最近错误和重复运行覆盖最新快照。
- [ ] 1.6 新增 `agent/trace.jsonl` 测试，覆盖 append-only、`run_id`、`run_started`、tool attempt、`run_finished`、`run_failed` 和每行合法 JSON object。
- [ ] 1.7 新增 trace 隐私测试，确认 trace 不包含完整 transcript、完整正文、完整 HTML、完整 prompt、完整模型输出、API key、cookie 或环境变量值。
- [ ] 1.8 新增 agent tools 测试，使用 stub 依赖覆盖 `route_url`、`prepare_source_workspace`、Bilibili 文本化、网页文本化、分类、总结、Obsidian 写入和 processed 标记。
- [ ] 1.9 新增产物复用测试，覆盖已有规范文本、`domain.json`、`summary.json` 合法时对应 tool 返回 `skipped: true`。
- [ ] 1.10 新增重复来源测试，覆盖 SQLite `status = "processed"` 命中时返回 `skipped_existing`、state stage 为 `processed_ready`、ToolResult/trace 包含 `skip_reason: "processed_existing"`、不执行后续副作用 tools。
- [ ] 1.11 新增有限重试测试，覆盖网络/API/下载错误最多重试一次，`BILIBILI_TRANSCRIPT_FAILED` 仅在 ToolResult 标记 `retryable: true` 时重试，schema、配置、Whisper、写入和非法转换错误不重试。
- [ ] 1.12 新增 `km agent-ingest` CLI 契约测试，覆盖 stdin JSON、`mode` 可选、额外字段忽略、stdout 单 JSON object、成功和失败响应 agent 字段。
- [ ] 1.13 新增 skill loader 测试，覆盖必需 `skills/*.md` 被读取、缺失或空文件返回 `AGENT_SKILL_MISSING`、skill 上下文不附带完整来源内容。
- [ ] 1.14 更新项目内 skill 文档测试，确认 URL、Bilibili、网页、Whisper、领域分类、总结和 Obsidian skills 都说明使用受控 Python tools。

## 2. 配置、错误与运行时适配

- [ ] 2.1 在 `pyproject.toml` 增加 `agent` optional extra，放入 PyPI `deepagents>=0.6.11,<0.7` runtime 依赖，并保持默认安装不要求该 extra。
- [ ] 2.2 扩展配置加载逻辑，支持并校验 `[llm.tasks] agent_orchestration` 对 `[llm.models.<ref>]` 的引用。
- [ ] 2.3 增加公开错误码 `AGENT_RUNTIME_UNAVAILABLE`、`AGENT_SKILL_MISSING`、`AGENT_INVALID_TRANSITION` 和 `AGENT_ORCHESTRATION_FAILED`。
- [ ] 2.4 新增 `AgentRuntime` 接口、`DeepAgentsRuntime` 生产适配器和 `FakeAgentRuntime` 测试替身，runner 只能依赖项目内 `AgentRuntime.run(context, tools) -> AgentRunResult` 契约。
- [ ] 2.5 实现 runtime factory，集中处理真实 Deep Agents import 或初始化失败，并映射为 `AGENT_RUNTIME_UNAVAILABLE`。
- [ ] 2.6 实现 agent skill loader，读取阶段九必需 `SKILL.md`，校验存在、可读、非空，并返回最小化指令上下文。

## 3. Agent 状态、Trace 与 Guard

- [ ] 3.1 新增 agent 状态模型，表示 `initialized`、`routed`、`workspace_ready`、`text_ready`、`domain_ready`、`summary_ready`、`note_ready` 和 `processed_ready`。
- [ ] 3.2 实现 Python 状态机 guard，按 tool 和当前 stage 校验合法转换，包含重复来源 `routed -> prepare_source_workspace -> processed_ready` 跳过转换，非法转换不执行副作用。
- [ ] 3.3 实现 `<asset_dir>/agent/state.json` 写入器，支持初始化、阶段推进、路径字段更新、错误字段更新和最新快照覆盖。
- [ ] 3.4 实现 `<asset_dir>/agent/trace.jsonl` append-only 写入器，支持 run 事件、tool attempt 事件、跳过原因和失败事件。
- [ ] 3.5 实现 trace sanitization，禁止写入完整内容、完整 prompt、完整模型输出、API key、cookie 和环境变量值。
- [ ] 3.6 实现 `max_tool_steps = 12` 限制，超限写入 `run_failed` 并返回 `AGENT_ORCHESTRATION_FAILED`。
- [ ] 3.7 实现重试策略组件，网络/API/下载类错误每个 tool 最多重试一次；`BILIBILI_TRANSCRIPT_FAILED` 只在 ToolResult `retryable: true` 时重试，且不新增 `BILIBILI_SUBTITLE_FAILED` 或 `BILIBILI_AUDIO_DOWNLOAD_FAILED` 公开错误码。

## 4. 受控 Python Tools

- [ ] 4.1 实现 `route_url` tool，复用既有 URL 规范化和内容类型识别逻辑，只输出 `normalized_url` 和 `content_type`，不创建或返回 `source_id`，不访问 SQLite 或素材目录。
- [ ] 4.2 实现 `prepare_source_workspace` tool，基于 `normalized_url` 生成或查找 `source_id`，初始化素材目录、SQLite 边界、agent 目录、state/trace，并处理 processed 重复来源跳过。
- [ ] 4.3 实现 `collect_bilibili_text` tool，复用既有 Bilibili 元数据、字幕、音频下载、Whisper 转写和规范文本写入能力。
- [ ] 4.4 实现 `collect_web_article_text` tool，复用既有微信公众号 parser、`trafilatura` fallback、规范文本写入和网页错误映射。
- [ ] 4.5 实现 `classify_domain` tool，复用既有固定领域表、领域分类模型引用和 `summary/domain.json` schema 校验。
- [ ] 4.6 实现 `generate_summary` tool，复用既有中文总结、双模型评测输出配置和 `summary/summary.json` schema 校验。
- [ ] 4.7 实现 `write_obsidian_note` tool，复用既有 Obsidian note 渲染、路径选择、幂等覆盖和写入错误映射。
- [ ] 4.8 实现 `mark_source_processed` tool，复用既有 SQLite processed 写入逻辑，并更新最终 state。
- [ ] 4.9 为每个 tool 增加产物合法性检查，已有合法产物时返回 `skipped: true` 并避免重复副作用。

## 5. Agent Runner 与 CLI 集成

- [ ] 5.1 新增 agent runner，负责构造最小上下文、注册 tools、启动 runtime、执行状态推进和收敛最终结果。
- [ ] 5.2 让 runner 根据最终 state 构造 stdout envelope，成功响应包含 `orchestrator`、`trace_path` 和 `state_path`。
- [ ] 5.3 让 runner 在拥有 asset context 的失败响应中包含 `orchestrator`、`trace_path` 和 `state_path`，早期失败允许省略路径。
- [ ] 5.4 新增 `km agent-ingest` CLI 命令，复用现有 stdin JSON 解析、错误 envelope 和退出码约定。
- [ ] 5.5 保持 `km ingest` 确定性路径不变，确认 agent 路径失败时不自动 fallback 到 `km ingest`。
- [ ] 5.6 确认 stdout 只输出一个 JSON object，Deep Agents 日志、下载器日志和诊断信息不得写入 stdout。
- [ ] 5.7 增加可选手动验证命令或脚本，用于安装 `agent` extra 后运行真实 Deep Agents 编排，但不纳入默认单元测试。

## 6. 文档与 Skills

- [ ] 6.1 更新 `skills/url-routing/SKILL.md`，说明 `km ingest` 与 `km agent-ingest` 共享 URL 分类规则但使用不同编排路径。
- [ ] 6.2 更新 `skills/bilibili-ingest/SKILL.md`，说明 agent 只调用 `collect_bilibili_text`，Bilibili 内部步骤由受控 Python tool 完成。
- [ ] 6.3 更新 `skills/web-article-ingest/SKILL.md`，说明 agent 只调用 `collect_web_article_text`，网页 fetch、解析和规范文本写入由受控 Python tool 完成。
- [ ] 6.4 更新 `skills/whisper-transcription/SKILL.md`，说明 Whisper 由 Bilibili 受控 tool 内部触发，不作为 Hermes 直接调用能力。
- [ ] 6.5 更新 `skills/domain-classification/SKILL.md` 和 `skills/summary-generation/SKILL.md`，说明 agent 通过受控 tools 触发业务 LLM，不直接调用模型生成业务内容。
- [ ] 6.6 更新 `skills/obsidian-write/SKILL.md`，说明 agent 不得直接写 Obsidian、SQLite 或素材仓库，只能调用受控写入 tools。
- [ ] 6.7 更新 README，记录 `km agent-ingest` 用法、`agent` extra、`agent_orchestration` 配置、响应字段、state/trace 路径、错误码和 Hermes 边界。
- [ ] 6.8 更新 Superpowers 设计文档，补充阶段九 Deep Agents 编排、状态机 guard、产物复用和 Hermes 调用边界。

## 7. 验证

- [ ] 7.1 运行 `UV_CACHE_DIR=.uv-cache uv --no-config run python -m unittest discover -s tests -v`。
- [ ] 7.2 运行 `openspec validate add-deep-agents-ingest-orchestration`。
- [ ] 7.3 运行 `openspec validate --all`。
- [ ] 7.4 手动验证 `uv run --extra agent --env-file .env km agent-ingest` 在测试 URL 上返回 `processed_ready` 或 `skipped_existing`，并产生 `state.json` 与 `trace.jsonl`。
