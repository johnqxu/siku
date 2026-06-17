## MODIFIED Requirements

### Requirement: 公开响应 envelope
系统 SHALL 使用稳定的公开响应 envelope 表达失败，并在阶段二支持重复来源跳过成功响应。

#### Scenario: 失败响应包含必需字段
- **WHEN** 请求因输入或配置错误失败
- **THEN** stdout JSON 包含 `ok: false`、`error_code`、`message` 和 `recoverable`

#### Scenario: 合法请求未命中重复来源返回未实现
- **WHEN** 请求通过输入校验、阶段二配置校验、URL 规范化和重复查询，且未命中已处理来源
- **THEN** stdout JSON 包含 `ok: false`、`error_code: "NOT_IMPLEMENTED"`、`message` 和 `recoverable: true`

#### Scenario: 重复来源返回跳过成功响应
- **WHEN** 请求通过输入校验、阶段二配置校验和 URL 规范化，且 SQLite 索引命中 `status = 'processed'` 的重复来源
- **THEN** stdout JSON 包含 `ok: true`、`status: "skipped_existing"`、`note_path`、`asset_dir` 和 `source_url`，其中 `source_url` 来自已处理记录的 `original_url`

### Requirement: 本地配置加载
系统 SHALL 从本地配置来源加载运行时配置，并在处理请求前完成阶段二配置 schema 校验。

#### Scenario: 配置存在且有效
- **WHEN** 本地配置文件存在、内容是合法 TOML object，且包含非空字符串 `vault_path`、`inbox_dir` 和 `asset_store_path`
- **THEN** 系统继续处理请求

#### Scenario: 配置缺失或无效
- **WHEN** 本地配置文件缺失、无法读取、不是合法 TOML、TOML 根节点不是 object，或缺少阶段二必填配置字段
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

### Requirement: 退出码映射
系统 SHALL 根据处理结果返回稳定退出码。

#### Scenario: 输入错误返回退出码 1
- **WHEN** 输入 JSON 无效、缺少必填字段，或 URL 无法规范化为有效的 `http` 或 `https` URL
- **THEN** 进程退出码为 `1`

#### Scenario: 配置错误返回退出码 1
- **WHEN** 配置加载、阶段二配置 schema 校验、素材仓库初始化、SQLite 初始化或 SQLite schema 版本校验失败
- **THEN** 进程退出码为 `1`

#### Scenario: 可恢复处理失败返回退出码 2
- **WHEN** 合法请求通过本地状态层且未命中重复来源，并到达本阶段未实现的业务边界
- **THEN** 进程退出码为 `2`

#### Scenario: 重复来源跳过返回退出码 0
- **WHEN** 合法请求命中 `status = 'processed'` 的重复来源并返回 `skipped_existing`
- **THEN** 进程退出码为 `0`

### Requirement: 协议测试基线
系统 SHALL 提供自动化测试覆盖 CLI 协议骨架和阶段二本地状态入口。

#### Scenario: 测试覆盖输入和输出边界
- **WHEN** 测试套件运行
- **THEN** 它验证 stdin JSON 解析、stdout JSON 响应、stderr 日志分离和退出码

#### Scenario: 测试覆盖公开命令入口
- **WHEN** 测试套件运行
- **THEN** 它验证已安装的 `km ingest` console script 符合 stdout JSON 和退出码契约

#### Scenario: 测试覆盖配置错误
- **WHEN** 测试套件运行
- **THEN** 它验证缺失、无效或不满足阶段二 schema 的配置会返回 `CONFIG_INVALID`

#### Scenario: 测试覆盖未实现边界
- **WHEN** 测试套件运行
- **THEN** 它验证合法请求未命中重复来源时返回 `NOT_IMPLEMENTED` 和退出码 `2`

#### Scenario: 测试覆盖重复来源跳过
- **WHEN** 测试套件运行
- **THEN** 它验证合法请求命中 `status = 'processed'` 的重复来源时返回 `skipped_existing` 和退出码 `0`
