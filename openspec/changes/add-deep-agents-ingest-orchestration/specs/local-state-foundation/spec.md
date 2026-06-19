## ADDED Requirements

### Requirement: Agent orchestration 配置
系统 SHALL 在 `km agent-ingest` 启动 Deep Agents 编排时校验 `[llm.tasks] agent_orchestration`，并复用 `[llm.models.<ref>]` 的模型定义。

#### Scenario: agent_orchestration 必须存在
- **WHEN** `km agent-ingest` 需要启动 Deep Agents runtime
- **THEN** 配置 MUST 包含 `[llm.tasks] agent_orchestration = "<ref>"`，否则系统返回 `CONFIG_INVALID`

#### Scenario: agent_orchestration 必须引用有效模型
- **WHEN** `[llm.tasks] agent_orchestration` 指向 `<ref>`
- **THEN** `<ref>` MUST 存在于 `[llm.models]`，否则系统返回 `CONFIG_INVALID`

#### Scenario: agent_orchestration 引用模型必须可加载
- **WHEN** `[llm.tasks] agent_orchestration` 引用 `[llm.models.<ref>]`
- **THEN** 该模型 MUST 满足既有 OpenAI-compatible 模型字段、provider、timeout、max output tokens 和 API key 环境变量校验

#### Scenario: agent_orchestration 不影响业务任务
- **WHEN** 配置同时包含 `agent_orchestration`、`domain_classification` 和 `summary_generation`
- **THEN** `agent_orchestration` MUST 只用于 Deep Agents 编排模型，不改变领域分类或中文总结模型引用

### Requirement: Agent 素材状态目录
系统 SHALL 在每个 agent ingest 来源素材目录内维护 `agent/` 运行状态目录。

#### Scenario: agent 目录被创建
- **WHEN** `km agent-ingest` 初始化 `<asset_store_path>/<source_id>`
- **THEN** 系统 MUST 确保 `<asset_store_path>/<source_id>/agent` 存在

#### Scenario: agent state 位于素材目录
- **WHEN** `km agent-ingest` 写入 agent 状态快照
- **THEN** 状态文件 MUST 位于 `<asset_store_path>/<source_id>/agent/state.json`

#### Scenario: agent trace 位于素材目录
- **WHEN** `km agent-ingest` 写入 agent trace
- **THEN** trace 文件 MUST 位于 `<asset_store_path>/<source_id>/agent/trace.jsonl`

#### Scenario: agent 目录失败返回配置错误
- **WHEN** `agent/` 目录无法创建或不可写
- **THEN** 系统 MUST 返回公开失败 envelope，且错误码 MUST 与素材仓库不可用保持一致为 `CONFIG_INVALID`

### Requirement: Agent state schema
系统 SHALL 将 agent 最新状态快照写入 JSON object，供重试、调试和响应生成使用。

#### Scenario: state schema version
- **WHEN** 系统写入 `agent/state.json`
- **THEN** JSON MUST 包含 `schema_version: 1`

#### Scenario: state 包含来源字段
- **WHEN** 系统写入 `agent/state.json`
- **THEN** JSON MUST 包含 `source_id`、`original_url`、`normalized_url`、`content_type` 和 `asset_dir`

#### Scenario: state 包含阶段字段
- **WHEN** 系统写入 `agent/state.json`
- **THEN** JSON MUST 包含 `stage`，其值 MUST 是 agent 状态机定义的 stage 或失败时保留的最近 stage

#### Scenario: state 包含产物路径
- **WHEN** 系统写入 `agent/state.json`
- **THEN** JSON MUST 包含 `canonical_text_path`、`domain_path`、`summary_path` 和 `note_path`，未生成的路径使用 `null`

#### Scenario: state 包含最近错误
- **WHEN** agent 运行失败
- **THEN** `state.json` MUST 包含最近 `error_code` 和 `error_message`

### Requirement: Agent trace append-only
系统 SHALL 以 JSON Lines 形式追加 agent 运行事件，而不是覆盖历史 trace。

#### Scenario: 新运行追加 trace
- **WHEN** 同一来源再次执行 `km agent-ingest`
- **THEN** 系统 MUST 向同一个 `agent/trace.jsonl` 追加新的 `run_id` 事件，而不是覆盖旧事件

#### Scenario: trace 每行是 JSON object
- **WHEN** 系统写入 `agent/trace.jsonl`
- **THEN** 每一行 MUST 是一个合法 JSON object

#### Scenario: trace 不写入完整内容
- **WHEN** 系统写入 `agent/trace.jsonl`
- **THEN** trace MUST NOT 包含完整 transcript、完整正文、完整 HTML、完整 prompt、完整模型输出、API key、cookie 或环境变量值

### Requirement: Agent 重复来源状态
系统 SHALL 在 agent 路径命中 SQLite processed 重复来源时仍写入或追加 agent state/trace。

#### Scenario: 重复来源 state
- **WHEN** `km agent-ingest` 命中 SQLite `status = 'processed'` 的重复来源
- **THEN** 系统 MUST 写入 `state.json`，且 `stage` MUST 为 `processed_ready`

#### Scenario: 重复来源 trace
- **WHEN** `km agent-ingest` 命中 SQLite `status = 'processed'` 的重复来源
- **THEN** 系统 MUST 追加 trace 事件记录 `skip_reason: "processed_existing"`，且 MUST NOT 执行后续有副作用 tools
