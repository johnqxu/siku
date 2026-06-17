## ADDED Requirements

### Requirement: Agent ingest 命令入口
系统 SHALL 提供 `km agent-ingest` 命令作为 Hermes 调用 Deep Agents 编排导入流程的入口，并保持 `km ingest` 现有行为不变。

#### Scenario: agent ingest 命令可被调用
- **WHEN** 用户或 Hermes 调用 `km agent-ingest`
- **THEN** 系统执行 agent ingest 命令入口，而不是启动交互式对话

#### Scenario: agent ingest 复用 stdin 契约
- **WHEN** stdin 包含 `{"url":"https://example.com","mode":"ingest"}`
- **THEN** `km agent-ingest` MUST 按现有 ingest 请求格式解析 `url` 和 `mode`

#### Scenario: agent ingest 忽略额外字段
- **WHEN** stdin 包含合法 `url` 和 `mode`，并包含 `force`、`rerun_from` 或其他额外字段
- **THEN** `km agent-ingest` MUST 忽略额外字段，且 MUST NOT 因这些字段改变首版默认复用策略

#### Scenario: agent ingest 不改变 km ingest
- **WHEN** 用户或 Hermes 调用 `km ingest`
- **THEN** 系统 MUST 继续执行确定性 ingest 流程，而不是 Deep Agents 编排流程

### Requirement: Agent ingest stdout 响应
系统 SHALL 让 `km agent-ingest` stdout 只输出一个 JSON object，并在现有响应 envelope 基础上增加 agent 可观察字段。

#### Scenario: agent processed_ready 响应
- **WHEN** `km agent-ingest` 完成新来源导入并标记 processed
- **THEN** stdout JSON MUST 包含 `ok: true`、`status: "processed_ready"`、现有 processed 成功字段，以及 `orchestrator: "deep_agents"`、`trace_path` 和 `state_path`

#### Scenario: agent skipped_existing 响应
- **WHEN** `km agent-ingest` 命中 SQLite `status = 'processed'` 的重复来源
- **THEN** stdout JSON MUST 包含 `ok: true`、`status: "skipped_existing"`、`note_path`、`asset_dir`、`source_url`、`orchestrator: "deep_agents"`、`trace_path` 和 `state_path`

#### Scenario: agent 失败响应
- **WHEN** `km agent-ingest` 在拥有 agent state 路径后失败
- **THEN** stdout JSON MUST 包含 `ok: false`、`error_code`、`message`、`recoverable`、`orchestrator: "deep_agents"`、`trace_path` 和 `state_path`

#### Scenario: agent 早期失败响应
- **WHEN** `km agent-ingest` 在输入解析、配置加载或素材目录初始化前失败
- **THEN** stdout JSON MUST 包含公开失败 envelope，且 MAY 省略 `trace_path` 和 `state_path`

#### Scenario: agent 日志不写入 stdout
- **WHEN** Deep Agents runtime、Python tools 或 trace recorder 产生诊断日志
- **THEN** 日志 MUST NOT 写入 stdout

### Requirement: Agent ingest 错误码和退出码
系统 SHALL 为 `km agent-ingest` 提供 agent 编排相关公开错误码，并保持退出码映射稳定。

#### Scenario: agent runtime 缺失
- **WHEN** 用户调用 `km agent-ingest` 但缺少 Deep Agents runtime
- **THEN** stdout JSON MUST 包含 `error_code: "AGENT_RUNTIME_UNAVAILABLE"`、`recoverable: true`，且进程退出码为 `2`

#### Scenario: agent skill 缺失
- **WHEN** `km agent-ingest` 必需的项目内 `SKILL.md` 缺失、不可读或为空
- **THEN** stdout JSON MUST 包含 `error_code: "AGENT_SKILL_MISSING"`、`recoverable: true`，且进程退出码为 `2`

#### Scenario: agent 非法状态转换
- **WHEN** Deep Agents 尝试调用当前 stage 不允许的 tool
- **THEN** stdout JSON MUST 包含 `error_code: "AGENT_INVALID_TRANSITION"`、`recoverable: true`，且进程退出码为 `2`

#### Scenario: agent 编排兜底失败
- **WHEN** Deep Agents runtime 发生无法映射到业务错误码的编排失败、超过最大 tool 步数或返回无法解释的结果
- **THEN** stdout JSON MUST 包含 `error_code: "AGENT_ORCHESTRATION_FAILED"`、`recoverable: true`，且进程退出码为 `2`

#### Scenario: agent 业务错误码透出
- **WHEN** `km agent-ingest` 调用的受控 Python tool 返回既有业务错误码
- **THEN** stdout JSON MUST 保留该业务错误码，且按既有退出码规则返回

### Requirement: Agent ingest 协议测试基线
系统 SHALL 提供自动化测试覆盖 `km agent-ingest` 的 stdin/stdout、退出码、agent 字段、错误码和 FakeAgentRuntime 路径。

#### Scenario: 测试覆盖 agent 命令入口
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `km agent-ingest` console script 符合 stdout JSON 和退出码契约

#### Scenario: 测试覆盖 agent 成功响应
- **WHEN** 测试套件使用 `FakeAgentRuntime` 验证成功路径
- **THEN** 它 MUST 验证 stdout 返回 `processed_ready`、退出码 `0`，并包含 `orchestrator`、`trace_path` 和 `state_path`

#### Scenario: 测试覆盖 agent 重复来源响应
- **WHEN** 测试套件使用 SQLite processed 记录验证重复来源
- **THEN** 它 MUST 验证 stdout 返回 `skipped_existing`、退出码 `0`，并包含 agent 可观察字段

#### Scenario: 测试覆盖 agent 错误
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `AGENT_RUNTIME_UNAVAILABLE`、`AGENT_SKILL_MISSING`、`AGENT_INVALID_TRANSITION` 和 `AGENT_ORCHESTRATION_FAILED` 的公开响应和退出码
