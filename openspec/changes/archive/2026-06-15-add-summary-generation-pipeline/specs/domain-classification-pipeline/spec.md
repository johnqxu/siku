## MODIFIED Requirements

### Requirement: 领域分类 pipeline 入口
系统 SHALL 为已生成规范文本的新来源执行领域分类 pipeline，并在领域分类成功后继续执行中文总结 pipeline。

#### Scenario: Bilibili transcript 后进入领域分类
- **WHEN** `km ingest` 请求路由为 `bilibili_video`，且 Bilibili transcript pipeline 成功生成 `canonical/transcript.md`
- **THEN** 系统继续执行领域分类 pipeline，而不是停在 `transcript_ready`

#### Scenario: 网页 content 后进入领域分类
- **WHEN** `km ingest` 请求路由为 `web_article`，且网页文章 content pipeline 成功生成 `canonical/content.md`
- **THEN** 系统继续执行领域分类 pipeline，而不是停在 `content_ready`

#### Scenario: 领域分类成功后进入中文总结
- **WHEN** 领域分类 pipeline 产出 `summary/domain.json`
- **THEN** 系统继续执行中文总结 pipeline，并在成功时返回 `summary_ready`

#### Scenario: pipeline 不执行更后续知识处理
- **WHEN** 领域分类 pipeline 和中文总结 pipeline 均成功
- **THEN** 系统 MUST NOT 执行 Obsidian 写入、SQLite `processed` 记录写入或 Deep Agents 端到端编排

### Requirement: domain_ready 响应
系统 SHALL 保留领域分类成功响应 builder 作为内部阶段结果，但 `km ingest` 端到端成功路径 SHALL 在中文总结成功后返回 `summary_ready`。

#### Scenario: domain_ready 成功响应 builder
- **WHEN** 领域分类 pipeline 成功写入 `summary/domain.json`
- **THEN** 内部响应 builder 可生成包含 `ok: true`、`status: "domain_ready"`、`content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`domain_path`、`domain`、`taxonomy_version` 和 `model_ref` 的阶段性响应

#### Scenario: km ingest 不停在 domain_ready
- **WHEN** `km ingest` 文本化和领域分类均成功，且中文总结 pipeline 成功
- **THEN** stdout JSON 返回 `summary_ready`，而不是 `domain_ready`

#### Scenario: domain_ready 不表示完整知识笔记完成
- **WHEN** 内部系统生成 `domain_ready`
- **THEN** 该响应只表示领域分类完成，不表示中文总结、Obsidian 笔记或 SQLite `processed` 记录已经完成
