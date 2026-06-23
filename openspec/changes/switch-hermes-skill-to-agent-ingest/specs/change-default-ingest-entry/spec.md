## ADDED Requirements

### Requirement: Hermes skill 默认使用 agent ingest 入口
系统 SHALL 让 `skills/hermes-knowledge-ingest/SKILL.md` 把 `km agent-ingest` 列为默认推荐入口，而不是 `km ingest`。

#### Scenario: skill 默认命令是 km agent-ingest
- **WHEN** Hermes 读取 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 首先列出 `km agent-ingest` 作为默认推荐命令，包含 `--extra agent`、`--env-file .env` 和 `km agent-ingest`

#### Scenario: km ingest 仍是可用的调试备用入口
- **WHEN** Hermes 读取 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 仍包含 `km ingest` 的调用示例，但标记为可选备用/确定性调试入口

#### Scenario: 预检查包含 agent extra 和 agent_orchestration
- **WHEN** Hermes 读取 `skills/hermes-knowledge-ingest/SKILL.md` 的预检查部分
- **THEN** 文档 MUST 声明需要 `agent` extra（`uv sync --extra agent`）和 `[llm.tasks] agent_orchestration` 配置引用

#### Scenario: 移除未来迁移表述
- **WHEN** Hermes 读取 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST NOT 将 `km agent-ingest` 描述为"未来"或"阶段九"迁移目标，而应描述为"当前默认入口"

### Requirement: 项目文档反映默认入口变更
系统 SHALL 更新 README.md 和 docs/project-overview.md，使 `km agent-ingest` 放在示例的默认位置。

#### Scenario: README 默认示例使用 km agent-ingest
- **WHEN** 用户阅读 README.md
- **THEN** "快速开始"和"Deep Agents 编排入口"等章节 MUST 将 `km agent-ingest` 放在更前位置，`km ingest` 作为可选替代

#### Scenario: project-overview 更新入口描述
- **WHEN** 用户阅读 `docs/project-overview.md`
- **THEN** 文档 MUST 将 `km agent-ingest` 标注为当前 Hermes 推荐入口

### Requirement: 测试验证 skill 默认入口
系统 SHALL 更新 `tests/test_project_skills.py`，确认 skill 文档默认命令为 `km agent-ingest`。

#### Scenario: 默认命令测试包含 km agent-ingest
- **WHEN** 测试套件运行 `test_project_skills` 中 Hermes skill 默认命令测试
- **THEN** 断言 MUST 检查 skill 文档包含 `uv run --extra agent --env-file .env km agent-ingest`

#### Scenario: skill 仍包含 km ingest 作为备用
- **WHEN** 测试套件运行 `test_project_skills` 中 Hermes skill 备用命令测试
- **THEN** 断言 MUST 确认 skill 文档仍包含 `km ingest`，但不再作为默认推荐
