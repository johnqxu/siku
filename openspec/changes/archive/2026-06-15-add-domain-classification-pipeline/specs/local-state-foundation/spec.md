## MODIFIED Requirements

### Requirement: 阶段二配置 schema
系统 SHALL 要求本地配置包含阶段二本地状态所需字段：`vault_path`、`inbox_dir` 和 `asset_store_path`，并在启用阶段六领域分类时包含有效的 LLM 模型定义与任务引用。

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

#### Scenario: 被引用 LLM 模型必须包含必需字段
- **WHEN** 领域分类任务引用 `[llm.models.<ref>]`
- **THEN** 该模型定义 MUST 包含非空字符串 `provider`、`base_url`、`model` 和 `api_key_env`

#### Scenario: 被引用 LLM 模型的 API key 环境变量必须存在
- **WHEN** 领域分类任务引用的模型定义包含 `api_key_env`
- **THEN** 对应环境变量 MUST 存在且非空，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: 不支持的 LLM provider 被拒绝
- **WHEN** 领域分类任务引用的模型定义中 `provider` 不是 `openai_compatible`
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`
