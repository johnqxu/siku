## Why

当前 `km ingest` 已经具备从 URL 到 Obsidian `processed` 状态的确定性闭环，但还没有真正使用 Deep Agents 作为编排器。阶段九需要提供一个面向 Hermes 调用的 agent 入口，让 Hermes 只调用 `km agent-ingest`，由项目内 Deep Agents runtime 编排受控 Python tools 完成导入流程。

这个阶段要验证“skills + 受控 tools + 状态机 guard”的 agent 编排形态，同时保留现有 `km ingest` 作为确定性 CLI 基线。

## What Changes

- 新增 `km agent-ingest` 命令，stdin 复用现有 `{"url": "...", "mode": "ingest"}` 契约，stdout 仍输出单个 JSON object。
- 新增 Deep Agents 编排层：`km agent-ingest` 内部启动 Deep Agents runtime，Hermes 不直接编排项目内 tools。
- 新增同进程 Python agent tools：URL 路由、素材工作区准备、Bilibili 文本化、网页文本化、领域分类、中文总结、Obsidian 写入、SQLite processed 标记。
- 新增 Python 状态机 guard，强制 Deep Agents 只能按合法状态转换调用 tools。
- 新增 agent 运行状态与 trace：`<asset_dir>/agent/state.json` 和 `<asset_dir>/agent/trace.jsonl`。
- 新增 `AgentRuntime` 适配层与 `FakeAgentRuntime` 测试替身，默认测试不依赖真实 Deep Agents runtime 或远程 agent 模型。
- 新增 `agent` optional extra，依赖 PyPI `deepagents>=0.6.11,<0.7`，生产适配器通过 `from deepagents import create_deep_agent` 接入真实 runtime；缺少 Deep Agents runtime 时返回 `AGENT_RUNTIME_UNAVAILABLE`。
- 新增 `[llm.tasks] agent_orchestration = "<model_ref>"`，首版建议配置为 `deepseek_v4_flash`。
- `km agent-ingest` 成功/失败响应在现有 envelope 基础上增加 `orchestrator`、`trace_path` 和 `state_path`。
- 读取项目内 `skills/*.md` 作为 Deep Agents 编排指令资产，但所有副作用仍必须通过受控 Python tools。
- Deep Agents 只读取编排元数据、路径、状态和 tool 说明，不读取完整 transcript/content、HTML、prompt、模型输出、API key 或 cookie。
- 不自动 fallback 到 `km ingest`；agent 路径失败时明确返回 agent failure response。
- 新增 agent 编排相关错误码：`AGENT_RUNTIME_UNAVAILABLE`、`AGENT_SKILL_MISSING`、`AGENT_INVALID_TRANSITION`、`AGENT_ORCHESTRATION_FAILED`。

## Capabilities

### New Capabilities

- `deep-agents-ingest-orchestration`: 定义 `km agent-ingest`、Deep Agents 编排运行时、状态机 guard、agent tools、state/trace、重试、skills 读取和 agent 路径响应契约。

### Modified Capabilities

- `cli-contract-skeleton`: 增加 `km agent-ingest` 命令、agent 路径成功/失败响应字段、agent 错误码和退出码契约。
- `local-state-foundation`: 增加 `[llm.tasks] agent_orchestration` 配置校验、`agent` optional extra 运行时要求，以及素材仓库内 agent state/trace 文件约束。
- `url-routing-and-skill-skeleton`: 将项目内 `skills/*.md` 从未来指令资产推进为 Deep Agents runtime 读取的受控编排上下文，并明确 skill 不能授予副作用权限。

## Impact

- 影响 CLI 入口：新增 `km agent-ingest`，保留 `km ingest` 行为不变。
- 影响依赖管理：新增 `agent` optional dependency extra，默认 `uv sync` 不要求安装 Deep Agents runtime。
- 影响配置：新增 `llm.tasks.agent_orchestration` 模型引用校验。
- 影响素材仓库：每个 agent 运行来源新增 `agent/state.json` 和 `agent/trace.jsonl`。
- 影响错误模型：新增 4 个 `AGENT_*` 错误码，均为可恢复处理失败，退出码为 `2`。
- 影响测试：默认测试使用 `FakeAgentRuntime`；真实 Deep Agents 只作为手动或可选集成验证，不进入默认 `unittest discover`。
- 不改 SQLite schema，不改现有 `km ingest` 响应契约，不新增内容源，不改变 Bilibili、网页解析、中文总结或 Obsidian note 格式。
