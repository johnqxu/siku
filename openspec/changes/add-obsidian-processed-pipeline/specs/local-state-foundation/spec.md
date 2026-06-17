## MODIFIED Requirements

### Requirement: 阶段二配置 schema
系统 SHALL 要求本地配置包含阶段二本地状态所需字段：`vault_path`、`inbox_dir` 和 `asset_store_path`，并在启用阶段六领域分类、阶段七中文总结和阶段八 Obsidian processed 写入时包含有效的 LLM 模型定义、任务引用、总结配置与 Obsidian 路径。

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

#### Scenario: vault_path 必须是已存在目录
- **WHEN** `km ingest` 需要执行阶段八 Obsidian processed 写入
- **THEN** `vault_path` MUST 已存在、是目录且可写，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

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

### Requirement: 重复来源查询
系统 SHALL 在进入后续采集阶段前查询 SQLite 索引中的已处理来源。

#### Scenario: 已处理来源被识别为重复
- **WHEN** `sources` 表存在 `normalized_url` 匹配且 `status = 'processed'` 的记录
- **THEN** 系统将该来源识别为重复来源，并返回记录中的 `note_path`、`asset_dir` 和 `original_url`

#### Scenario: 未处理来源不视为重复
- **WHEN** `sources` 表存在 `normalized_url` 匹配但 `status` 不是 `processed`
- **THEN** 系统不将该来源识别为重复来源

#### Scenario: failed 来源不阻止重试
- **WHEN** `sources` 表存在 `normalized_url` 匹配且 `status = 'failed'` 的记录
- **THEN** 系统不将该来源识别为重复来源，后续 pipeline 可重新执行

#### Scenario: 未命中重复来源不预写来源记录
- **WHEN** 请求未命中 `status = 'processed'` 的重复来源
- **THEN** 阶段二系统不向 `sources` 表预写新的来源记录；来源记录由阶段八 Obsidian processed pipeline 在成功或阶段八失败时写入

## ADDED Requirements

### Requirement: SQLite processed 与 failed 写入
系统 SHALL 复用现有 `sources` 表记录阶段八的最终 processed 状态和阶段八自身 failed 状态。

#### Scenario: processed 写入复用现有 schema
- **WHEN** Obsidian note pipeline 成功写入 note
- **THEN** 系统使用现有 `sources` 表写入或更新 `status = 'processed'`，MUST NOT 升级 `PRAGMA user_version`

#### Scenario: failed 只记录阶段八失败
- **WHEN** Obsidian note pipeline 发生 `OBSIDIAN_WRITE_FAILED` 或 `INDEX_WRITE_FAILED`
- **THEN** 系统在 SQLite 可写时记录 `status = 'failed'`、`error_code`、`error_message`、`asset_dir` 和已知字段

#### Scenario: 前置 pipeline 失败不补写 failed
- **WHEN** 文本化、领域分类或中文总结阶段失败
- **THEN** 阶段八 MUST NOT 为这些失败补写 SQLite `failed` 记录
