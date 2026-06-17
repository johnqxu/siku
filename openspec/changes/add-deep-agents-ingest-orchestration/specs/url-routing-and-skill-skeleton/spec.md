## ADDED Requirements

### Requirement: Agent runtime skill loader
系统 SHALL 在 `km agent-ingest` 启动 Deep Agents runtime 前读取项目内必需 skill 文档，并把这些文档作为 agent 编排指令资产。

#### Scenario: 读取阶段九必需 skills
- **WHEN** `km agent-ingest` 初始化 Deep Agents runtime
- **THEN** 系统 MUST 读取 `skills/url-routing/SKILL.md`、`skills/bilibili-ingest/SKILL.md`、`skills/web-article-ingest/SKILL.md`、`skills/whisper-transcription/SKILL.md`、`skills/domain-classification/SKILL.md`、`skills/summary-generation/SKILL.md` 和 `skills/obsidian-write/SKILL.md`

#### Scenario: 缺失 skill 阻止 agent 启动
- **WHEN** 任一阶段九必需 `SKILL.md` 缺失、不可读或内容为空
- **THEN** `km agent-ingest` MUST 返回 `AGENT_SKILL_MISSING`，且 MUST NOT 启动 Deep Agents runtime

#### Scenario: skill 内容进入最小上下文
- **WHEN** 系统构造 Deep Agents 任务上下文
- **THEN** 上下文 MAY 包含必需 skill 文档的指令文本、tool schema、状态机规则和错误处理规则

#### Scenario: skill 上下文不包含完整来源内容
- **WHEN** 系统把 skill 指令资产提供给 Deep Agents
- **THEN** 上下文 MUST NOT 附带完整 transcript、完整网页正文、完整 HTML、完整 prompt、完整模型输出、API key、cookie 或环境变量值

### Requirement: Agent 编排语义更新
系统 SHALL 更新项目内 skill 文档，使其明确阶段九由 Deep Agents 编排受控 Python tools，同时保留现有确定性 `km ingest` 语义。

#### Scenario: url-routing skill 区分两条入口
- **WHEN** 开发者阅读 `skills/url-routing/SKILL.md`
- **THEN** 文档 MUST 说明 `km ingest` 使用确定性编排，`km agent-ingest` 使用 Deep Agents 编排，二者共享 URL 分类规则

#### Scenario: Bilibili skill 说明中等粒度 tool
- **WHEN** 开发者阅读 `skills/bilibili-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 agent 只调用 `collect_bilibili_text`，下载元数据、字幕、音频和 Whisper 转写由该受控 Python tool 内部完成

#### Scenario: Web article skill 说明中等粒度 tool
- **WHEN** 开发者阅读 `skills/web-article-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 agent 只调用 `collect_web_article_text`，HTTP fetch、解析器选择、fallback 解析和规范文本写入由该受控 Python tool 内部完成

#### Scenario: Obsidian skill 禁止 agent 直接写入
- **WHEN** 开发者阅读 `skills/obsidian-write/SKILL.md`
- **THEN** 文档 MUST 明确 Deep Agents 不得直接写 Obsidian、SQLite 或素材仓库，只能调用 `write_obsidian_note` 和 `mark_source_processed`

### Requirement: Hermes 调用边界文档
系统 SHALL 在项目文档中明确 Hermes 的职责边界，避免把 Hermes 设计为 tool 编排者。

#### Scenario: Hermes 只调用 CLI
- **WHEN** 开发者阅读阶段九文档或 README
- **THEN** 文档 MUST 说明 Hermes 只调用 `km agent-ingest` 并传入 JSON stdin

#### Scenario: Deep Agents 执行编排
- **WHEN** `km agent-ingest` 收到 Hermes 请求
- **THEN** 工具选择、状态推进、重试和 trace 写入 MUST 由 `km agent-ingest` 内部 Deep Agents 编排路径负责

#### Scenario: 不暴露内部 tools 给 Hermes
- **WHEN** 文档描述 Hermes 集成方式
- **THEN** 文档 MUST NOT 要求 Hermes 直接调用 `route_url`、`collect_bilibili_text`、`generate_summary` 或其他项目内 agent tools
