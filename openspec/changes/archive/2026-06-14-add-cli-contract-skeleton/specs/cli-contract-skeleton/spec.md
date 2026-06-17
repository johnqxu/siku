## ADDED Requirements

### Requirement: CLI 命令入口
系统 SHALL 提供 `km ingest` 命令作为 Hermes 调用知识导入工具的第一阶段入口。

#### Scenario: 命令可被调用
- **WHEN** 用户或 Hermes 调用 `km ingest`
- **THEN** 系统执行 ingest 命令入口，而不是启动交互式对话

### Requirement: JSON stdin 输入
系统 SHALL 从 stdin 读取一个 JSON 对象作为请求输入。

#### Scenario: 有效输入被解析
- **WHEN** stdin 包含 `{"url":"https://example.com","mode":"ingest"}`
- **THEN** 系统解析出 `url` 和 `mode`

#### Scenario: mode 可以省略
- **WHEN** stdin 包含 `{"url":"https://example.com"}`
- **THEN** 系统将 `mode` 视为 `ingest`

#### Scenario: mode 只允许 ingest
- **WHEN** stdin 包含 `{"url":"https://example.com","mode":"dry_run"}`
- **THEN** 系统返回 `ok: false` 且 `error_code: "INPUT_INVALID"`

#### Scenario: 无效 JSON 被拒绝
- **WHEN** stdin 不是合法 JSON
- **THEN** 系统返回 `ok: false` 且 `error_code: "INPUT_INVALID"`

#### Scenario: 缺少 URL 被拒绝
- **WHEN** stdin JSON 不包含必填 `url`
- **THEN** 系统返回 `ok: false` 且 `error_code: "INPUT_INVALID"`

#### Scenario: 空白 URL 被拒绝
- **WHEN** stdin JSON 包含仅由空白字符组成的 `url`
- **THEN** 系统返回 `ok: false` 且 `error_code: "INPUT_INVALID"`

### Requirement: JSON stdout 输出
系统 SHALL 向 stdout 写入且只写入一个 JSON 对象。

#### Scenario: stdout 是单个 JSON 对象
- **WHEN** 命令完成一次请求处理
- **THEN** stdout 内容可以被解析为一个 JSON 对象

#### Scenario: 日志不写入 stdout
- **WHEN** 系统产生诊断日志或调试信息
- **THEN** 这些内容写入 stderr，且 stdout 不包含日志文本

### Requirement: 公开响应 envelope
系统 SHALL 使用稳定的公开响应 envelope 表达失败；成功和跳过响应在后续业务阶段定义。

#### Scenario: 失败响应包含必需字段
- **WHEN** 请求因输入或配置错误失败
- **THEN** stdout JSON 包含 `ok: false`、`error_code`、`message` 和 `recoverable`

#### Scenario: 合法请求返回未实现
- **WHEN** 请求通过输入校验和配置校验
- **THEN** stdout JSON 包含 `ok: false`、`error_code: "NOT_IMPLEMENTED"`、`message` 和 `recoverable: true`

### Requirement: 本地配置加载
系统 SHALL 从本地配置来源加载运行时配置，并在处理请求前完成基础校验。

#### Scenario: 配置存在且有效
- **WHEN** 本地配置文件存在且内容是合法 TOML object
- **THEN** 系统继续处理请求

#### Scenario: 配置缺失或无效
- **WHEN** 本地配置文件缺失、无法读取、不是合法 TOML，或 TOML 根节点不是 object
- **THEN** 系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

### Requirement: 退出码映射
系统 SHALL 根据处理结果返回稳定退出码。

#### Scenario: 输入错误返回退出码 1
- **WHEN** 输入 JSON 无效或缺少必填字段
- **THEN** 进程退出码为 `1`

#### Scenario: 配置错误返回退出码 1
- **WHEN** 配置加载或校验失败
- **THEN** 进程退出码为 `1`

#### Scenario: 可恢复处理失败返回退出码 2
- **WHEN** 合法请求到达本阶段未实现的业务边界
- **THEN** 进程退出码为 `2`

### Requirement: 协议测试基线
系统 SHALL 提供自动化测试覆盖 CLI 协议骨架。

#### Scenario: 测试覆盖输入和输出边界
- **WHEN** 测试套件运行
- **THEN** 它验证 stdin JSON 解析、stdout JSON 响应、stderr 日志分离和退出码

#### Scenario: 测试覆盖公开命令入口
- **WHEN** 测试套件运行
- **THEN** 它验证已安装的 `km ingest` console script 符合 stdout JSON 和退出码契约

#### Scenario: 测试覆盖配置错误
- **WHEN** 测试套件运行
- **THEN** 它验证缺失或无效配置会返回 `CONFIG_INVALID`

#### Scenario: 测试覆盖未实现边界
- **WHEN** 测试套件运行
- **THEN** 它验证合法请求返回 `NOT_IMPLEMENTED` 和退出码 `2`
