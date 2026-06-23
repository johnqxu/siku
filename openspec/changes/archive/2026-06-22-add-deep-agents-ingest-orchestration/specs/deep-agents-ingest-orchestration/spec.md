## ADDED Requirements

### Requirement: Deep Agents 编排入口
系统 SHALL 提供 `km agent-ingest` 作为 Hermes 调用 Deep Agents 编排路径的 CLI 入口，并由该命令内部启动 Deep Agents runtime 编排受控 Python tools。

#### Scenario: Hermes 调用 agent ingest 命令
- **WHEN** Hermes 调用 `km agent-ingest` 并通过 stdin 传入合法 ingest JSON
- **THEN** 系统 MUST 启动 agent ingest 路径，而不是启动交互式对话

#### Scenario: Hermes 不直接编排 tools
- **WHEN** `km agent-ingest` 处理请求
- **THEN** Hermes MUST NOT 直接调用项目内 agent tools，tool 编排 MUST 发生在 `km agent-ingest` 内部

#### Scenario: 不替换确定性 ingest
- **WHEN** 用户或 Hermes 调用 `km ingest`
- **THEN** 系统 MUST 保持现有确定性 ingest 路径，不切换到 Deep Agents 编排路径

#### Scenario: agent 路径不自动 fallback
- **WHEN** `km agent-ingest` 内部 Deep Agents 编排失败
- **THEN** 系统 MUST 返回 agent 路径失败响应，且 MUST NOT 自动调用 `km ingest`

### Requirement: Agent optional runtime
系统 SHALL 将 Deep Agents 运行时依赖放入 `agent` optional extra，并在缺少运行时时返回公开错误。

#### Scenario: agent extra 可安装
- **WHEN** 用户执行 `uv sync --extra agent`
- **THEN** 项目环境 MUST 包含 `km agent-ingest` 所需的 PyPI `deepagents>=0.6.11,<0.7` runtime 依赖

#### Scenario: 缺少 runtime 返回错误
- **WHEN** 用户调用 `km agent-ingest` 但 Deep Agents runtime 不可导入
- **THEN** stdout JSON MUST 包含 `ok: false`、`error_code: "AGENT_RUNTIME_UNAVAILABLE"`、`recoverable: true`

#### Scenario: GPU 场景需要组合 extra
- **WHEN** `km agent-ingest` 处理无字幕 Bilibili 视频并需要 Whisper GPU 转写
- **THEN** 用户 MUST 同时启用 `agent` 和 `gpu` extra，否则对应运行时缺失错误按公开错误 envelope 返回

### Requirement: Agent orchestration 模型引用
系统 SHALL 使用 `[llm.tasks] agent_orchestration` 指定 Deep Agents 编排模型引用，并从 `[llm.models.<ref>]` 加载模型定义。

#### Scenario: agent_orchestration 引用有效模型
- **WHEN** `km agent-ingest` 需要启动 Deep Agents runtime
- **THEN** 配置 MUST 包含 `[llm.tasks] agent_orchestration = "<ref>"`，且 `<ref>` MUST 指向存在的 `[llm.models.<ref>]`

#### Scenario: 编排模型与业务模型分离
- **WHEN** 系统加载 `agent_orchestration`、`domain_classification` 和 `summary_generation`
- **THEN** 三个任务 MAY 引用不同模型，且变更 `agent_orchestration` MUST NOT 改变领域分类或中文总结使用的模型引用

#### Scenario: 缺少 agent_orchestration 被拒绝
- **WHEN** `km agent-ingest` 启动时配置缺少 `[llm.tasks] agent_orchestration`
- **THEN** 系统 MUST 返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

### Requirement: AgentRuntime 适配层
系统 SHALL 通过项目内 `AgentRuntime` 适配层调用真实 Deep Agents runtime，并提供 `FakeAgentRuntime` 作为默认测试替身。

#### Scenario: runner 不直接依赖框架 API
- **WHEN** `km agent-ingest` runner 启动编排
- **THEN** runner MUST 通过 `AgentRuntime` 接口运行 agent，而不是在业务入口直接绑定 Deep Agents 框架 API

#### Scenario: DeepAgentsRuntime 使用固定导入路径
- **WHEN** `DeepAgentsRuntime` 初始化真实 Deep Agents runtime
- **THEN** 生产适配器 MUST 使用 `from deepagents import create_deep_agent` 作为唯一框架导入边界，并把框架对象转换为项目内 `AgentRuntime` 结果类型

#### Scenario: 真实 runtime 缺失集中处理
- **WHEN** `DeepAgentsRuntime` 无法导入或初始化真实 Deep Agents runtime
- **THEN** 系统 MUST 返回 `AGENT_RUNTIME_UNAVAILABLE`

#### Scenario: 默认测试使用 FakeAgentRuntime
- **WHEN** 默认单元测试验证 agent ingest 编排
- **THEN** 测试 MUST 使用 `FakeAgentRuntime` 或等价测试替身，不依赖真实 Deep Agents runtime、远程模型或网络

### Requirement: 中等粒度 agent tools
系统 SHALL 向 Deep Agents 注册中等粒度同进程 Python tools，并通过这些 tools 执行所有副作用。

#### Scenario: 注册受控 tools
- **WHEN** `km agent-ingest` 初始化 Deep Agents runtime
- **THEN** 系统 MUST 注册 `route_url`、`prepare_source_workspace`、`collect_bilibili_text`、`collect_web_article_text`、`classify_domain`、`generate_summary`、`write_obsidian_note` 和 `mark_source_processed`

#### Scenario: route_url 不拥有 source_id
- **WHEN** Deep Agents 调用 `route_url`
- **THEN** 该 tool MUST 只返回 URL 规范化和内容类型识别结果，包括 `normalized_url` 和 `content_type`，且 MUST NOT 创建或返回 `source_id`、初始化素材目录或访问 SQLite

#### Scenario: prepare_source_workspace 拥有 source_id
- **WHEN** Deep Agents 调用 `prepare_source_workspace`
- **THEN** 该 tool MUST 基于 `normalized_url` 生成或查找 `source_id`，初始化素材目录、SQLite 边界、agent state/trace，并处理 processed 重复来源跳过

#### Scenario: Bilibili 内部流程不拆给 agent
- **WHEN** Deep Agents 调用 `collect_bilibili_text`
- **THEN** 元数据、字幕、音频下载和 Whisper 转写 MUST 由该受控 Python tool 内部处理，而不是暴露为多个 agent 可见 tools

#### Scenario: 网页内部流程不拆给 agent
- **WHEN** Deep Agents 调用 `collect_web_article_text`
- **THEN** HTTP fetch、专用 parser 选择、fallback parser 和规范正文写入 MUST 由该受控 Python tool 内部处理

#### Scenario: agent 不直接执行副作用
- **WHEN** Deep Agents 需要下载、解析、转写、调用业务 LLM、写文件、写 Obsidian 或写 SQLite
- **THEN** Deep Agents MUST 通过受控 Python tool 完成，MUST NOT 自行调用 shell、文件系统、SQLite、Obsidian 或外部 API

### Requirement: Python 状态机 guard
系统 SHALL 使用 Python 状态机 guard 强制 Deep Agents 只能按合法状态转换调用 tools。

#### Scenario: 合法状态转换
- **WHEN** 当前 stage 为 `text_ready` 且 Deep Agents 调用 `classify_domain`
- **THEN** guard MUST 允许调用，并在成功后将 stage 推进到 `domain_ready`

#### Scenario: 非法状态转换被拒绝
- **WHEN** 当前 stage 为 `text_ready` 且 Deep Agents 调用 `write_obsidian_note`
- **THEN** guard MUST 拒绝调用，返回 `AGENT_INVALID_TRANSITION`，且 MUST NOT 执行 Obsidian 写入副作用

#### Scenario: 非法转移不重试
- **WHEN** tool 调用被 guard 拒绝为 `AGENT_INVALID_TRANSITION`
- **THEN** 系统 MUST NOT 自动重试该错误，并 MUST 记录失败 trace

#### Scenario: 状态机路径完整
- **WHEN** `km agent-ingest` 从新来源开始执行
- **THEN** 合法完成路径 MUST 按 `initialized`、`routed`、`workspace_ready`、`text_ready`、`domain_ready`、`summary_ready`、`note_ready`、`processed_ready` 推进

#### Scenario: 重复来源合法跳过转换
- **WHEN** 当前 stage 为 `routed` 且 `prepare_source_workspace` 命中 SQLite `status = 'processed'` 的重复来源
- **THEN** guard MUST 允许该 tool 将 stage 直接推进到 `processed_ready`，且 ToolResult MUST 包含 `status: "skipped_existing"`、`skipped: true` 和 `skip_reason: "processed_existing"`

### Requirement: Agent state 快照
系统 SHALL 在素材仓库来源目录下维护 `agent/state.json` 作为 agent 运行最新状态快照。

#### Scenario: state 文件位置
- **WHEN** `prepare_source_workspace` 初始化来源素材目录
- **THEN** 系统 MUST 创建或更新 `<asset_dir>/agent/state.json`

#### Scenario: state 字段
- **WHEN** 系统写入 `agent/state.json`
- **THEN** 文件 MUST 包含 `schema_version`、`orchestrator`、`source_id`、`original_url`、`normalized_url`、`content_type`、`stage`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path`、`note_path`、`error_code`、`error_message` 和 `updated_at`

#### Scenario: state 只保存最新快照
- **WHEN** 同一来源多次执行 `km agent-ingest`
- **THEN** `state.json` MUST 表示最新状态快照，而不是保存所有历史运行事件

#### Scenario: 成功推进清空错误字段
- **WHEN** tool 成功推进 stage
- **THEN** `state.json` 中最近错误字段 MUST 被清空或置为 `null`

### Requirement: Agent trace 事件
系统 SHALL 在素材仓库来源目录下维护 append-only `agent/trace.jsonl`，记录 agent 编排历史事件。

#### Scenario: trace 文件位置
- **WHEN** `km agent-ingest` 处理来源并拥有 `asset_dir`
- **THEN** 系统 MUST 追加写入 `<asset_dir>/agent/trace.jsonl`

#### Scenario: 每次运行有 run_id
- **WHEN** `km agent-ingest` 开始一次运行
- **THEN** 系统 MUST 创建新的 `run_id` 并写入 `run_started` trace 事件

#### Scenario: tool attempt 被记录
- **WHEN** agent tool 被调用或被状态机 guard 拒绝
- **THEN** trace 事件 MUST 记录 `timestamp`、`run_id`、`step`、`tool`、`attempt`、`stage_before`、`stage_after`、`status`、`skipped`、`error_code` 和 `message`

#### Scenario: 成功运行完成
- **WHEN** agent 路径成功返回 `processed_ready` 或 `skipped_existing`
- **THEN** trace MUST 追加 `run_finished` 事件

#### Scenario: 失败运行完成
- **WHEN** agent 路径返回失败响应
- **THEN** trace MUST 追加 `run_failed` 事件

#### Scenario: trace 不记录完整内容
- **WHEN** 系统写入 trace 事件
- **THEN** trace MUST NOT 包含完整 transcript、完整正文、完整 HTML、完整 prompt、完整模型输出、API key、cookie 或环境变量值

### Requirement: 产物复用策略
系统 SHALL 在 agent tool 执行前校验已有产物，并在产物合法时复用而不是重复执行副作用。

#### Scenario: 复用规范文本
- **WHEN** `collect_bilibili_text` 或 `collect_web_article_text` 的目标规范文本已存在且通过合法性校验
- **THEN** tool MUST 返回 `text_ready`，并在 ToolResult 和 trace 中标记 `skipped: true`

#### Scenario: 复用领域分类结果
- **WHEN** `summary/domain.json` 已存在且通过 schema 与上下文校验
- **THEN** `classify_domain` MUST 返回 `domain_ready`，并标记 `skipped: true`

#### Scenario: 复用中文总结结果
- **WHEN** `summary/summary.json` 已存在且通过 schema 与上下文校验
- **THEN** `generate_summary` MUST 返回 `summary_ready`，并标记 `skipped: true`

#### Scenario: 不支持 force
- **WHEN** stdin JSON 包含 `force`、`rerun_from` 或类似额外字段
- **THEN** 首版 `km agent-ingest` MUST 忽略这些额外字段，不改变默认复用策略

### Requirement: 重复来源跳过
系统 SHALL 在 agent 路径下复用 SQLite `processed` 重复来源查询，并返回 `skipped_existing`。

#### Scenario: processed 命中直接跳过
- **WHEN** SQLite `sources` 表存在同一 `normalized_url` 且 `status = 'processed'` 的记录
- **THEN** `km agent-ingest` MUST 返回 `ok: true`、`status: "skipped_existing"`，并包含 `note_path`、`asset_dir`、`source_url`、`orchestrator`、`trace_path` 和 `state_path`，且 state stage MUST 为 `processed_ready`

#### Scenario: 跳过仍记录 trace
- **WHEN** agent 路径命中重复来源并跳过
- **THEN** 系统 MUST 写入或追加 agent state/trace，trace 中 MUST 记录 `skip_reason: "processed_existing"`，并 MUST NOT 执行后续文本化、分类、总结、Obsidian 写入或 processed 标记 tools

#### Scenario: 文件系统缺失不主动修复
- **WHEN** SQLite `processed` 命中但记录中的文件路径已被用户删除
- **THEN** 首版系统 MUST 仍按 SQLite 记录返回 `skipped_existing`，不主动重建素材或笔记

### Requirement: 有限自动重试
系统 SHALL 只对网络、API 和下载类可恢复错误执行有限自动重试。

#### Scenario: LLM 请求失败重试一次
- **WHEN** agent tool 返回 `LLM_REQUEST_FAILED`
- **THEN** 系统 MAY 自动重试同一 tool 一次，且 trace MUST 记录 `attempt` 递增

#### Scenario: 下载类失败重试一次
- **WHEN** agent tool 返回 `WEB_FETCH_FAILED`、`BILIBILI_METADATA_FAILED`，或返回 `BILIBILI_TRANSCRIPT_FAILED` 且 ToolResult 标记 `retryable: true`
- **THEN** 系统 MAY 自动重试同一 tool 一次

#### Scenario: Bilibili transcript 非瞬时失败不重试
- **WHEN** agent tool 返回 `BILIBILI_TRANSCRIPT_FAILED` 且 ToolResult 未标记 `retryable: true`
- **THEN** 系统 MUST NOT 自动重试该错误，且 MUST 保留公开错误码 `BILIBILI_TRANSCRIPT_FAILED`

#### Scenario: schema 错误不重试
- **WHEN** agent tool 返回 `LLM_SCHEMA_INVALID`、`SUMMARY_SCHEMA_INVALID` 或 `SUMMARY_INPUT_INVALID`
- **THEN** 系统 MUST NOT 自动重试该错误

#### Scenario: 写入错误不重试
- **WHEN** agent tool 返回 `OBSIDIAN_WRITE_FAILED` 或 `INDEX_WRITE_FAILED`
- **THEN** 系统 MUST NOT 自动重试该错误

#### Scenario: Whisper runtime 错误不重试
- **WHEN** agent tool 返回 `WHISPER_UNAVAILABLE`
- **THEN** 系统 MUST NOT 自动重试该错误

### Requirement: ToolResult 统一结构
系统 SHALL 使用统一 ToolResult 结构表达每个 agent tool 的执行结果。

#### Scenario: 成功 ToolResult 字段
- **WHEN** agent tool 成功完成或成功复用产物
- **THEN** ToolResult MUST 包含 `ok: true`、`tool`、`status`、`stage_before`、`stage_after`、`skipped`，并按阶段包含相关路径、`content_type`、`source_url`、`domain` 或 `title`

#### Scenario: 失败 ToolResult 字段
- **WHEN** agent tool 失败
- **THEN** ToolResult MUST 包含 `ok: false`、`tool`、`status: "failed"`、`stage_before`、`stage_after`、`error_code`、`message` 和 `recoverable`，并 MAY 包含 `retryable` 和 `retry_reason`

#### Scenario: ToolResult 不构造最终 stdout
- **WHEN** tool 返回 ToolResult
- **THEN** 最终 stdout JSON MUST 由 agent runner 根据最终 state 和结果构造，而不是由单个 tool 直接输出

### Requirement: Agent context 最小化
系统 SHALL 只向 Deep Agents 提供编排所需元数据和指令，不提供完整来源内容。

#### Scenario: agent 可见编排元数据
- **WHEN** Deep Agents runtime 接收任务上下文
- **THEN** 上下文 MAY 包含用户 URL、`normalized_url`、当前 state 摘要、`content_type`、产物路径、tool 描述、tool schema、项目内 skills、状态机规则和错误处理规则；`source_id` 只有在 `prepare_source_workspace` 成功生成或查到后才可出现在上下文中

#### Scenario: agent 不可见完整来源内容
- **WHEN** Deep Agents runtime 接收任务上下文
- **THEN** 上下文 MUST NOT 包含完整 transcript、完整正文、完整 HTML、完整字幕、完整 summary prompt、完整 LLM 输出、API key、cookie 或环境变量值

### Requirement: 项目内 skills 作为 agent 指令资产
系统 SHALL 在 `km agent-ingest` 启动时读取项目内必需 `skills/*.md`，作为 Deep Agents 编排上下文的一部分。

#### Scenario: 必需 skills 被读取
- **WHEN** `km agent-ingest` 初始化 agent runtime
- **THEN** 系统 MUST 读取 URL 路由、Bilibili 导入、网页文章导入、Whisper 转写、领域分类、中文总结和 Obsidian 写入相关 `SKILL.md`

#### Scenario: 缺失 skill 返回错误
- **WHEN** 必需 `SKILL.md` 缺失、不可读或内容为空
- **THEN** 系统 MUST 返回 `AGENT_SKILL_MISSING`

#### Scenario: skill 不授予副作用权限
- **WHEN** Deep Agents 读取项目内 skill 指令资产
- **THEN** skill 内容 MUST NOT 允许 agent 绕过受控 Python tools 直接写入素材仓库、SQLite 或 Obsidian

### Requirement: Agent stdout 响应
系统 SHALL 在 `km agent-ingest` stdout 响应中复用现有公开 envelope，并增加 agent 可观察字段。

#### Scenario: processed_ready 响应包含 agent 字段
- **WHEN** `km agent-ingest` 成功处理新来源并完成 processed 标记
- **THEN** stdout JSON MUST 包含现有 `processed_ready` 字段，并额外包含 `orchestrator: "deep_agents"`、`trace_path` 和 `state_path`

#### Scenario: skipped_existing 响应包含 agent 字段
- **WHEN** `km agent-ingest` 命中重复来源并返回 `skipped_existing`
- **THEN** stdout JSON MUST 包含 `orchestrator: "deep_agents"`、`trace_path` 和 `state_path`

#### Scenario: 失败响应包含 agent 字段
- **WHEN** `km agent-ingest` 在拥有 agent state 路径后失败
- **THEN** stdout JSON MUST 包含 `ok: false`、`error_code`、`message`、`recoverable`、`orchestrator: "deep_agents"`、`trace_path` 和 `state_path`

#### Scenario: 早期失败可省略 state 路径
- **WHEN** `km agent-ingest` 在配置加载、输入解析或素材目录初始化前失败
- **THEN** stdout JSON MAY 省略 `trace_path` 和 `state_path`

### Requirement: Agent 错误码
系统 SHALL 为 agent 编排层提供公开 `AGENT_*` 错误码，并保持业务 tool 错误码原样透出。

#### Scenario: runtime 缺失错误
- **WHEN** Deep Agents runtime 缺失
- **THEN** 系统 MUST 返回 `AGENT_RUNTIME_UNAVAILABLE`

#### Scenario: skill 缺失错误
- **WHEN** 必需 skill 指令资产缺失
- **THEN** 系统 MUST 返回 `AGENT_SKILL_MISSING`

#### Scenario: 非法状态转换错误
- **WHEN** Deep Agents 尝试非法 tool 转换
- **THEN** 系统 MUST 返回 `AGENT_INVALID_TRANSITION`

#### Scenario: 编排兜底错误
- **WHEN** Deep Agents runtime 返回无法解释的结果、超过最大 tool 步数、未调用任何合法 tool 或发生无标准 `KmError` 的异常
- **THEN** 系统 MUST 返回 `AGENT_ORCHESTRATION_FAILED`

#### Scenario: 业务错误码不被包裹
- **WHEN** 受控 Python tool 返回 `WEB_FETCH_FAILED`、`LLM_REQUEST_FAILED`、`OBSIDIAN_WRITE_FAILED` 或其他既有业务错误
- **THEN** `km agent-ingest` MUST 在 stdout failure envelope 中保留该业务错误码，而不是改写为 `AGENT_ORCHESTRATION_FAILED`

### Requirement: Agent tool step 上限
系统 SHALL 限制单次 agent 运行的 tool 调用步数，防止无限循环。

#### Scenario: 正常路径未超限
- **WHEN** agent 按正常路径调用 7 个左右 tools 完成导入
- **THEN** 系统 MUST 允许运行完成

#### Scenario: 超过最大步数失败
- **WHEN** 单次 `km agent-ingest` 运行超过 `max_tool_steps = 12`
- **THEN** 系统 MUST 停止编排、写入 `run_failed` trace，并返回 `AGENT_ORCHESTRATION_FAILED`

#### Scenario: 非法调用计入步数
- **WHEN** Deep Agents 调用被 guard 拒绝的非法 tool
- **THEN** 该调用 MUST 计入 `max_tool_steps`

### Requirement: Agent 默认测试策略
系统 SHALL 通过默认自动化测试覆盖 agent 编排边界，且默认测试不依赖真实 Deep Agents runtime。

#### Scenario: 默认测试不需要 agent extra
- **WHEN** 开发者运行 `uv run python -m unittest discover -s tests -v`
- **THEN** agent ingest 相关默认测试 MUST 使用 fake runtime 或 stub，不要求安装 `agent` extra

#### Scenario: 测试覆盖状态机
- **WHEN** agent ingest 测试运行
- **THEN** 测试 MUST 覆盖合法状态转换、非法状态转换和 `AGENT_INVALID_TRANSITION`

#### Scenario: 测试覆盖 state 和 trace
- **WHEN** agent ingest 测试运行
- **THEN** 测试 MUST 验证 `state.json` 写入、`trace.jsonl` 追加、`run_id`、`run_started`、tool event 和 `run_finished` 或 `run_failed`

#### Scenario: 测试覆盖响应字段
- **WHEN** agent ingest 测试运行
- **THEN** 测试 MUST 验证成功和失败响应包含 `orchestrator`、`trace_path` 和 `state_path`

#### Scenario: 真实 Deep Agents 仅手动验证
- **WHEN** 项目提供真实 Deep Agents 验证命令或脚本
- **THEN** 该验证 MUST 作为手动或可选集成验证，不纳入默认单元测试入口
