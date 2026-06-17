## ADDED Requirements

### Requirement: 领域分类 pipeline 入口
系统 SHALL 为已生成规范文本的新来源执行领域分类 pipeline。

#### Scenario: Bilibili transcript 后进入领域分类
- **WHEN** `km ingest` 请求路由为 `bilibili_video`，且 Bilibili transcript pipeline 成功生成 `canonical/transcript.md`
- **THEN** 系统继续执行领域分类 pipeline，而不是停在 `transcript_ready`

#### Scenario: 网页 content 后进入领域分类
- **WHEN** `km ingest` 请求路由为 `web_article`，且网页文章 content pipeline 成功生成 `canonical/content.md`
- **THEN** 系统继续执行领域分类 pipeline，而不是停在 `content_ready`

#### Scenario: pipeline 不执行后续知识处理
- **WHEN** 领域分类 pipeline 产出 `summary/domain.json`
- **THEN** 系统 MUST NOT 执行中文总结、Obsidian 写入、SQLite `processed` 记录写入或 Deep Agents 端到端编排

### Requirement: 固定领域表
系统 SHALL 使用版本化固定领域表执行单一主领域分类。

#### Scenario: 固定领域表版本为 1
- **WHEN** 领域分类 pipeline 执行
- **THEN** 分类结果使用 `taxonomy_version: 1`

#### Scenario: 只允许一个主领域
- **WHEN** 模型输出分类结果
- **THEN** 系统只接受一个 `domain` 字段，不接受辅助领域或自由标签

#### Scenario: 主领域必须来自固定表
- **WHEN** 系统校验分类结果
- **THEN** `domain` MUST 是 `AI`、`编程`、`产品`、`商业`、`学习`、`心理学`、`投资`、`写作`、`生活`、`菜谱`、`其他` 之一

#### Scenario: 低置信度归入其他
- **WHEN** 内容跨领域、证据不足或模型无法明确判断主领域
- **THEN** 分类结果 SHALL 使用 `domain: "其他"`，并在 `reason` 中说明原因

### Requirement: LLM 模型定义与任务引用
系统 SHALL 支持集中式 LLM 模型定义，并由领域分类任务引用具体模型。

#### Scenario: 模型定义包含必需字段
- **WHEN** 配置声明 `[llm.models.<ref>]`
- **THEN** 每个被领域分类任务引用的模型定义 MUST 包含非空字符串 `provider`、`base_url`、`model` 和 `api_key_env`

#### Scenario: 领域分类引用模型定义
- **WHEN** 配置声明 `[llm.tasks] domain_classification = "<ref>"`
- **THEN** 系统使用 `llm.models.<ref>` 中的模型定义执行领域分类

#### Scenario: 引用不存在返回配置错误
- **WHEN** `llm.tasks.domain_classification` 引用的模型不存在
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: API key 环境变量缺失返回配置错误
- **WHEN** 被引用模型的 `api_key_env` 对应环境变量不存在或为空
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 首版只支持 OpenAI-compatible provider
- **WHEN** 被引用模型的 `provider` 不是 `openai_compatible`
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

### Requirement: 受控 LLM 分类调用
系统 SHALL 通过受控 Python tool 调用远程 LLM 执行领域分类。

#### Scenario: 使用规范文本作为分类输入
- **WHEN** 领域分类 pipeline 执行
- **THEN** 系统读取 `canonical_text_path` 指向的规范文本作为分类输入

#### Scenario: 超长规范文本被截断
- **WHEN** 规范文本长度超过阶段六分类输入上限
- **THEN** 系统只将前 12000 个字符放入分类 prompt，并在 prompt 中说明规范文本已截断

#### Scenario: 分类提示词要求中文说明
- **WHEN** 系统请求 LLM 执行领域分类
- **THEN** prompt SHALL 要求 `reason` 使用中文，并要求输出符合领域分类 JSON schema

#### Scenario: LLM 请求失败返回结构化错误
- **WHEN** 远程模型请求发生网络错误、超时、鉴权失败、服务端错误或非成功 HTTP 状态
- **THEN** 系统返回 `ok: false` 且 `error_code: "LLM_REQUEST_FAILED"`

#### Scenario: 不接入 Deep Agents 运行时
- **WHEN** 领域分类 pipeline 执行
- **THEN** 系统 MUST NOT 创建 LangChain Deep Agent 或让 agent 编排分类步骤

### Requirement: 分类 schema 校验
系统 SHALL 校验 LLM 返回的领域分类结果。

#### Scenario: 合法分类结果被接受
- **WHEN** LLM 返回包含 `domain`、`confidence` 和 `reason` 的合法 JSON，且 `domain` 属于固定领域表
- **THEN** 系统接受该分类结果并补充 `taxonomy_version`、`model_ref` 和 `model`

#### Scenario: 非 JSON 响应返回 schema 错误
- **WHEN** LLM 返回内容不是合法 JSON
- **THEN** 系统返回 `ok: false` 且 `error_code: "LLM_SCHEMA_INVALID"`

#### Scenario: 缺少字段返回 schema 错误
- **WHEN** LLM 返回 JSON 缺少 `domain`、`confidence` 或 `reason`
- **THEN** 系统返回 `ok: false` 且 `error_code: "LLM_SCHEMA_INVALID"`

#### Scenario: 非法领域返回 schema 错误
- **WHEN** LLM 返回的 `domain` 不属于固定领域表
- **THEN** 系统返回 `ok: false` 且 `error_code: "LLM_SCHEMA_INVALID"`

#### Scenario: 置信度非法返回 schema 错误
- **WHEN** LLM 返回的 `confidence` 不是数字、不能解析为数字或不是有限数字
- **THEN** 系统返回 `ok: false` 且 `error_code: "LLM_SCHEMA_INVALID"`

### Requirement: 领域分类产物
系统 SHALL 将分类结果写入素材仓库 summary 目录。

#### Scenario: domain.json 被写入
- **WHEN** 领域分类成功
- **THEN** 系统将分类结果写入 `<asset_store_path>/<source_id>/summary/domain.json`

#### Scenario: domain.json 包含追溯字段
- **WHEN** `summary/domain.json` 被写入
- **THEN** JSON 包含 `taxonomy_version`、`domain`、`confidence`、`reason`、`model_ref` 和 `model`

#### Scenario: 不生成 domain.md
- **WHEN** 领域分类成功
- **THEN** 系统 MUST NOT 生成 `summary/domain.md`

### Requirement: domain_ready 响应
系统 SHALL 在领域分类成功后返回阶段性成功响应 `domain_ready`。

#### Scenario: domain_ready 成功响应
- **WHEN** 领域分类 pipeline 成功写入 `summary/domain.json`
- **THEN** stdout JSON 包含 `ok: true`、`status: "domain_ready"`、`content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`domain_path`、`domain`、`taxonomy_version` 和 `model_ref`

#### Scenario: domain_ready 不表示完整知识笔记完成
- **WHEN** 系统返回 `domain_ready`
- **THEN** 该响应只表示领域分类完成，不表示中文总结、Obsidian 笔记或 SQLite `processed` 记录已经完成

### Requirement: domain classification skill 资产
系统 SHALL 维护项目内领域分类 skill 文件，供未来 Hermes/Deep Agents 编排复用。

#### Scenario: domain-classification skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/domain-classification/SKILL.md` 存在，并说明固定领域表、单一主领域、低置信度归入 `其他` 和受控 tool 使用约束

#### Scenario: skill 不直接执行副作用
- **WHEN** 阅读 `skills/domain-classification/SKILL.md`
- **THEN** skill 文件 MUST 指示 agent 使用受控 Python tools，而不是自行调用 LLM、写入素材仓库、修改 SQLite 或写 Obsidian

### Requirement: 测试替身
系统 SHALL 使用测试替身验证领域分类 pipeline，不依赖真实 LLM 网络调用。

#### Scenario: 单元测试使用 fake LLM client
- **WHEN** 单元测试运行
- **THEN** 领域分类请求使用 fake LLM client 或 fixture 响应，而不是访问真实远程模型

#### Scenario: 单元测试覆盖成功路径
- **WHEN** 单元测试运行
- **THEN** 它验证 Bilibili 和网页文本化成功后继续返回 `domain_ready`，并写入 `summary/domain.json`

#### Scenario: 单元测试覆盖失败路径
- **WHEN** 单元测试运行
- **THEN** 它验证 LLM 请求失败返回 `LLM_REQUEST_FAILED`，schema 校验失败返回 `LLM_SCHEMA_INVALID`
