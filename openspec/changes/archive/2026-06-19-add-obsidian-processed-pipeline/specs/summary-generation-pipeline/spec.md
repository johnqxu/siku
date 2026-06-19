## MODIFIED Requirements

### Requirement: 中文总结 pipeline 入口
系统 SHALL 为已完成领域分类的新来源执行中文总结 pipeline，并在中文总结成功后继续执行 Obsidian processed pipeline。

#### Scenario: Bilibili domain 后进入总结
- **WHEN** `km ingest` 请求路由为 `bilibili_video`，Bilibili transcript pipeline 成功生成 `canonical/transcript.md`，且领域分类 pipeline 成功生成 `summary/domain.json`
- **THEN** 系统继续执行中文总结 pipeline，而不是停在 `domain_ready`

#### Scenario: 网页 domain 后进入总结
- **WHEN** `km ingest` 请求路由为 `web_article`，网页文章 content pipeline 成功生成 `canonical/content.md`，且领域分类 pipeline 成功生成 `summary/domain.json`
- **THEN** 系统继续执行中文总结 pipeline，而不是停在 `domain_ready`

#### Scenario: 总结成功后进入 Obsidian processed pipeline
- **WHEN** 中文总结 pipeline 产出 `summary/summary.json`
- **THEN** 系统继续执行 Obsidian note pipeline，并在成功时返回 `processed_ready`

#### Scenario: pipeline 不执行 Deep Agents 编排
- **WHEN** 中文总结 pipeline 和 Obsidian note pipeline 均成功
- **THEN** 系统 MUST NOT 启用 Deep Agents 端到端编排

### Requirement: summary_ready 响应
系统 SHALL 保留中文总结成功响应 builder 作为内部阶段结果，但 `km ingest` 端到端成功路径 SHALL 在 Obsidian processed pipeline 成功后返回 `processed_ready`。

#### Scenario: summary_ready 成功响应 builder
- **WHEN** 中文总结 pipeline 成功写入 `summary/summary.json`
- **THEN** 内部响应 builder 可生成包含 `ok: true`、`status: "summary_ready"`、`content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path`、`domain`、`title`、`summary_model_ref` 和 `evaluation_enabled` 的阶段性响应

#### Scenario: 评测响应 builder 包含 evaluation_dir
- **WHEN** 评测模式启用且中文总结成功
- **THEN** 内部 `summary_ready` 响应 builder 可包含 `evaluation_dir`

#### Scenario: km ingest 不停在 summary_ready
- **WHEN** `km ingest` 文本化、领域分类、中文总结和 Obsidian note pipeline 均成功
- **THEN** stdout JSON 返回 `processed_ready`，而不是 `summary_ready`

#### Scenario: summary_ready 不输出总结正文
- **WHEN** 内部系统生成 `summary_ready`
- **THEN** 该响应 MUST NOT 嵌入 `summary/summary.json` 的正文内容

#### Scenario: summary_ready 不表示完整知识笔记完成
- **WHEN** 内部系统生成 `summary_ready`
- **THEN** 该响应只表示中文总结完成，不表示 Obsidian 笔记或 SQLite `processed` 记录已经完成

### Requirement: summary generation skill 资产
系统 SHALL 维护项目内中文总结 skill 文件，供未来 Hermes/Deep Agents 编排复用。

#### Scenario: summary-generation skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/summary-generation/SKILL.md` 存在，并说明中文总结必须通过受控 Python 总结工具执行

#### Scenario: skill 不直接执行副作用
- **WHEN** 阅读 `skills/summary-generation/SKILL.md`
- **THEN** skill 文件 MUST 指示 agent 不直接调用 LLM、不直接写 Obsidian、不写 SQLite `processed` 记录、不做评测评分或排序、不启用 Deep Agents 运行时编排；Obsidian 写入必须交给 `obsidian-write` skill 对应的受控 tools

### Requirement: summary 测试替身
系统 SHALL 使用测试替身验证中文总结 pipeline，不依赖真实 LLM 网络调用。

#### Scenario: 单元测试使用 fake LLM client
- **WHEN** 单元测试运行
- **THEN** 中文总结请求使用 fake LLM client 或 fixture 响应，而不是访问真实远程模型

#### Scenario: 单元测试覆盖成功路径
- **WHEN** 单元测试运行
- **THEN** 它验证 Bilibili 和网页文本化加领域分类成功后继续写入 `summary/summary.json`，并由端到端 CLI 继续返回 `processed_ready`

#### Scenario: 单元测试覆盖失败路径
- **WHEN** 单元测试运行
- **THEN** 它验证 `SUMMARY_INPUT_INVALID`、`SUMMARY_INPUT_TOO_LARGE`、`SUMMARY_SCHEMA_INVALID` 和 `LLM_REQUEST_FAILED`
