## ADDED Requirements

### Requirement: Hermes 完整知识导入 skill
系统 SHALL 在项目内 skills 目录维护 `hermes-knowledge-ingest` 高层 skill，作为 Hermes 调用完整知识导入流程的入口。

#### Scenario: Hermes 高层 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/hermes-knowledge-ingest/SKILL.md` MUST 存在，并说明该 skill 面向 Hermes 调用完整知识导入流程

#### Scenario: Hermes skill 使用当前稳定 CLI
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 指示 Hermes 在 `/home/xu/workspace/siku` 下运行 `uv run --env-file .env km ingest`

#### Scenario: Hermes skill 定义 stdin 请求
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 指示 Hermes 通过 stdin 传入单个 JSON object，包含 `url` 和 `mode: "ingest"`

#### Scenario: Hermes skill 轻量预检查
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 要求 Hermes 在调用前确认当前目录、`.env`、`KM_CONFIG` 和 `DEEPSEEK_API_KEY`

#### Scenario: Hermes skill 不重复完整校验
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 Obsidian 路径、素材仓库路径、URL 合法性、Whisper 运行时、下载器和 SQLite 错误由 CLI 负责返回结构化 JSON

#### Scenario: Hermes skill 解释成功状态
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 `processed_ready` 表示完整导入完成，`skipped_existing` 表示已处理且不应重复导入

#### Scenario: Hermes skill 保留失败 envelope
- **WHEN** `km ingest` 返回失败 JSON
- **THEN** skill 文档 MUST 指示 Hermes 保留 `ok`、`error_code`、`message` 和 `recoverable`，并 MUST NOT 将业务错误只转换成对话式摘要

#### Scenario: Hermes skill 不额外重试
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 声明 skill 不增加自己的重试循环，并说明 `recoverable: true` 只允许 Hermes 在 workflow 层稍后重试

#### Scenario: Hermes skill 禁止内部工具调用
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 禁止 Hermes 直接调用 `route_url`、`collect_bilibili_text`、`collect_web_article_text`、`classify_domain`、`generate_summary`、`write_obsidian_note` 或 `mark_source_processed`

#### Scenario: Hermes skill 不读取生成内容
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 Hermes 默认只使用 stdout JSON 和路径字段做任务跟踪，不主动读取 note、summary、transcript、HTML、audio 或其他生成文件内容

#### Scenario: Hermes skill 记录 agent 入口迁移
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 记录阶段九实现后可显式切换到 `uv run --extra agent --env-file .env km agent-ingest`，且 MUST 禁止从 `km agent-ingest` 自动 fallback 到 `km ingest`

### Requirement: Hermes skill 测试覆盖
系统 SHALL 通过自动化测试覆盖 `hermes-knowledge-ingest` skill 的存在性和关键边界。

#### Scenario: 测试覆盖 Hermes skill 文件
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `skills/hermes-knowledge-ingest/SKILL.md` 存在

#### Scenario: 测试覆盖 Hermes skill 命令
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `hermes-knowledge-ingest` skill 记录当前命令 `uv run --env-file .env km ingest`

#### Scenario: 测试覆盖 Hermes skill 边界
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `hermes-knowledge-ingest` skill 说明轻量预检查、不额外重试、禁止内部工具调用、默认不读取生成内容，以及未来切换 `km agent-ingest` 不自动 fallback
