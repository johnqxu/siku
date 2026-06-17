# local-state-foundation Specification

## Purpose
定义知识导入工具的本地状态基础，包括阶段二配置 schema、URL 规范化、`source_id` 生成、素材仓库目录结构、SQLite 索引初始化和重复来源查询。
## Requirements
### Requirement: 阶段二配置 schema
系统 SHALL 要求本地配置包含阶段二本地状态所需字段：`vault_path`、`inbox_dir` 和 `asset_store_path`，并在启用阶段六领域分类和阶段七中文总结时包含有效的 LLM 模型定义、任务引用与总结配置。

#### Scenario: 有效阶段二配置被接受
- **WHEN** 本地配置文件包含非空字符串 `vault_path`、`inbox_dir` 和 `asset_store_path`
- **THEN** 系统将配置视为阶段二有效配置

#### Scenario: 缺少必填配置字段被拒绝
- **WHEN** 本地配置文件缺少 `vault_path`、`inbox_dir` 或 `asset_store_path`
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 空白配置字段被拒绝
- **WHEN** `vault_path`、`inbox_dir` 或 `asset_store_path` 是空字符串或仅包含空白字符
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 非字符串配置字段被拒绝
- **WHEN** `vault_path`、`inbox_dir` 或 `asset_store_path` 不是字符串
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: inbox_dir 必须是 vault 内相对路径
- **WHEN** `inbox_dir` 是绝对路径或包含 `..` 路径片段
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 素材仓库不能位于 vault 内
- **WHEN** `asset_store_path` 等于 `vault_path` 或位于 `vault_path` 内部
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 领域分类任务必须引用有效 LLM 模型
- **WHEN** `km ingest` 需要执行阶段六领域分类
- **THEN** 配置 MUST 包含 `[llm.tasks] domain_classification = "<ref>"`，且 `<ref>` 指向存在的 `[llm.models.<ref>]`

#### Scenario: 中文总结任务必须引用有效 LLM 模型
- **WHEN** `km ingest` 需要执行阶段七中文总结
- **THEN** 配置 MUST 包含 `[llm.tasks] summary_generation = "<ref>"`，且 `<ref>` 指向存在的 `[llm.models.<ref>]`

#### Scenario: 被引用 LLM 模型必须包含必需字段
- **WHEN** 领域分类任务、中文总结任务或评测候选引用 `[llm.models.<ref>]`
- **THEN** 该模型定义 MUST 包含非空字符串 `provider`、`base_url`、`model` 和 `api_key_env`

#### Scenario: 被引用 LLM 模型的 API key 环境变量必须存在
- **WHEN** 领域分类任务、中文总结任务或评测候选引用的模型定义包含 `api_key_env`
- **THEN** 对应环境变量 MUST 存在且非空，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 不支持的 LLM provider 被拒绝
- **WHEN** 领域分类任务、中文总结任务或评测候选引用的模型定义中 `provider` 不是 `openai_compatible`
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 模型级超时可选
- **WHEN** `[llm.models.<ref>]` 包含 `timeout_seconds`
- **THEN** `timeout_seconds` MUST 是正数，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 模型级输出 token 上限可选
- **WHEN** `[llm.models.<ref>]` 包含 `max_output_tokens`
- **THEN** `max_output_tokens` MUST 是正整数，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: summary 输入长度保护可选
- **WHEN** 配置包含 `[summary] max_input_chars`
- **THEN** `max_input_chars` MUST 是非负整数，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 评测模式配置必须完整
- **WHEN** 配置包含 `[summary.evaluation] enabled = true`
- **THEN** 配置 MUST 包含非空 `candidate_models` 和 `primary_model`，且 `primary_model` MUST 在 `candidate_models` 中

#### Scenario: 评测候选必须引用有效模型
- **WHEN** `[summary.evaluation] candidate_models` 包含模型引用
- **THEN** 每个引用 MUST 指向存在的 `[llm.models.<ref>]`

#### Scenario: 评测模型引用必须文件名安全
- **WHEN** `[summary.evaluation] candidate_models` 包含模型引用
- **THEN** 每个引用只能包含 `a-z`、`A-Z`、`0-9`、`_` 和 `-`，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

### Requirement: URL 规范化
系统 SHALL 在本地状态操作前将输入 URL 规范化为稳定的 `normalized_url`。

#### Scenario: URL 基础规范化
- **WHEN** 输入 URL 包含首尾空白、大小写混合的 scheme 或 host，以及 fragment
- **THEN** 系统去除首尾空白、小写化 scheme 和 host、删除 fragment，并保留 path 与 query

#### Scenario: query 被保留
- **WHEN** 输入 URL 包含 query 参数
- **THEN** `normalized_url` 保留 query 参数

#### Scenario: 非 http 或 https URL 被拒绝
- **WHEN** 输入 URL 的 scheme 不是 `http` 或 `https`
- **THEN** 系统返回 `ok: false` 且 `error_code: "INPUT_INVALID"`

#### Scenario: 缺少 host 的 URL 被拒绝
- **WHEN** 输入 URL 不包含 host
- **THEN** 系统返回 `ok: false` 且 `error_code: "INPUT_INVALID"`

### Requirement: source_id 生成
系统 SHALL 基于 `normalized_url` 生成稳定 `source_id`。

#### Scenario: source_id 来自 normalized_url 哈希
- **WHEN** 系统获得 `normalized_url`
- **THEN** 系统使用 `sha256(normalized_url).hexdigest()` 作为 `source_id`

#### Scenario: 相同 normalized_url 生成相同 source_id
- **WHEN** 两次请求得到相同 `normalized_url`
- **THEN** 两次请求生成相同 `source_id`

#### Scenario: source_id 使用完整 SHA-256 hex
- **WHEN** 系统生成 `source_id`
- **THEN** `source_id` 是 64 字符十六进制字符串

### Requirement: 素材仓库初始化
系统 SHALL 在配置的 `asset_store_path` 下初始化阶段二本地素材仓库结构。

#### Scenario: 素材仓库根目录被创建
- **WHEN** `asset_store_path` 不存在且父目录可写
- **THEN** 系统创建 `asset_store_path` 目录

#### Scenario: 来源素材目录被创建
- **WHEN** 请求通过配置校验和 URL 规范化
- **THEN** 系统创建 `<asset_store_path>/<source_id>/raw`、`<asset_store_path>/<source_id>/canonical` 和 `<asset_store_path>/<source_id>/summary`

#### Scenario: 不可用素材仓库路径被拒绝
- **WHEN** `asset_store_path` 无法创建、不是目录或不可写
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

### Requirement: SQLite 索引初始化
系统 SHALL 使用 `<asset_store_path>/index.sqlite` 作为本地状态权威索引。

#### Scenario: index.sqlite 被初始化
- **WHEN** 请求通过配置校验
- **THEN** 系统在 `asset_store_path` 下创建或打开 `index.sqlite`

#### Scenario: sources 表被创建
- **WHEN** 系统初始化 SQLite 索引
- **THEN** SQLite 数据库包含 `sources` 表，且表字段包括 `id`、`normalized_url`、`original_url`、`content_type`、`domain`、`title`、`note_path`、`asset_dir`、`created_at`、`updated_at`、`status`、`error_code` 和 `error_message`

#### Scenario: 基础索引被创建
- **WHEN** 系统初始化 SQLite 索引
- **THEN** SQLite 数据库包含面向 `domain`、`created_at` 和 `status` 的查询索引

#### Scenario: schema 版本被记录
- **WHEN** 系统初始化 SQLite 索引
- **THEN** SQLite 数据库的 `PRAGMA user_version` 为 `1`

#### Scenario: 未来 schema 版本被拒绝
- **WHEN** 系统打开 `PRAGMA user_version` 高于当前支持版本的 SQLite 数据库
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 初始化可重复执行
- **WHEN** 系统多次初始化同一个 `index.sqlite`
- **THEN** 初始化操作不破坏已有 `sources` 数据

### Requirement: 重复来源查询
系统 SHALL 在进入后续采集阶段前查询 SQLite 索引中的已处理来源。

#### Scenario: 已处理来源被识别为重复
- **WHEN** `sources` 表存在 `normalized_url` 匹配且 `status = 'processed'` 的记录
- **THEN** 系统将该来源识别为重复来源，并返回记录中的 `note_path`、`asset_dir` 和 `original_url`

#### Scenario: 未处理来源不视为重复
- **WHEN** `sources` 表存在 `normalized_url` 匹配但 `status` 不是 `processed` 的记录
- **THEN** 系统不将该来源识别为重复来源

#### Scenario: 未命中重复来源不写入来源记录
- **WHEN** 请求未命中 `status = 'processed'` 的重复来源
- **THEN** 阶段二系统不向 `sources` 表插入新的来源记录

