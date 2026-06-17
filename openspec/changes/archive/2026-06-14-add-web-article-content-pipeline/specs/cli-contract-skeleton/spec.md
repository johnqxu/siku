## MODIFIED Requirements

### Requirement: 公开响应 envelope
系统 SHALL 使用稳定的公开响应 envelope 表达失败，并支持重复来源跳过成功响应、Bilibili transcript 阶段性成功响应和网页文章 content 阶段性成功响应。

#### Scenario: 失败响应包含必需字段
- **WHEN** 请求因输入、配置、不支持的 URL、Bilibili 采集、Whisper 转写、网页抓取或网页解析失败
- **THEN** stdout JSON 包含 `ok: false`、`error_code`、`message` 和 `recoverable`

#### Scenario: 不支持 URL 返回公开错误码
- **WHEN** 请求通过输入校验、阶段二配置校验、URL 规范化和重复查询，但 URL 路由结果为 `unsupported`
- **THEN** stdout JSON 包含 `ok: false`、`error_code: "UNSUPPORTED_URL"`、`message` 和 `recoverable: false`

#### Scenario: Bilibili transcript 成功返回阶段性响应
- **WHEN** 请求通过输入校验、阶段二配置校验、URL 规范化和重复查询，URL 路由结果为 `bilibili_video`，且 Bilibili transcript pipeline 成功
- **THEN** stdout JSON 包含 `ok: true`、`status: "transcript_ready"`、`content_type: "bilibili_video"`、`source_url`、`asset_dir`、`canonical_text_path` 和 `asset_manifest`

#### Scenario: 网页文章 content 成功返回阶段性响应
- **WHEN** 请求通过输入校验、阶段二配置校验、URL 规范化和重复查询，URL 路由结果为 `web_article`，且网页文章 content pipeline 成功
- **THEN** stdout JSON 包含 `ok: true`、`status: "content_ready"`、`content_type: "web_article"`、`source_url`、`asset_dir`、`canonical_text_path`、`asset_manifest`、`parser_id` 和 `fetch_method`

#### Scenario: 重复来源返回跳过成功响应
- **WHEN** 请求通过输入校验、阶段二配置校验和 URL 规范化，且 SQLite 索引命中 `status = 'processed'` 的重复来源
- **THEN** stdout JSON 包含 `ok: true`、`status: "skipped_existing"`、`note_path`、`asset_dir` 和 `source_url`，其中 `source_url` 来自已处理记录的 `original_url`

### Requirement: 退出码映射
系统 SHALL 根据处理结果返回稳定退出码。

#### Scenario: 输入错误返回退出码 1
- **WHEN** 输入 JSON 无效、缺少必填字段，或 URL 无法规范化为有效的 `http` 或 `https` URL
- **THEN** 进程退出码为 `1`

#### Scenario: 配置错误返回退出码 1
- **WHEN** 配置加载、阶段二配置 schema 校验、素材仓库初始化、SQLite 初始化或 SQLite schema 版本校验失败
- **THEN** 进程退出码为 `1`

#### Scenario: 不支持 URL 返回退出码 1
- **WHEN** 合法请求通过本地状态层但 URL 路由结果为 `unsupported`
- **THEN** 进程退出码为 `1`

#### Scenario: Bilibili transcript 成功返回退出码 0
- **WHEN** Bilibili transcript pipeline 成功生成规范文本并返回 `transcript_ready`
- **THEN** 进程退出码为 `0`

#### Scenario: 网页文章 content 成功返回退出码 0
- **WHEN** 网页文章 content pipeline 成功生成规范正文并返回 `content_ready`
- **THEN** 进程退出码为 `0`

#### Scenario: 可恢复处理失败返回退出码 2
- **WHEN** 合法请求通过本地状态层和 URL 路由，且 Bilibili transcript pipeline、Whisper 转写、网页文章 content pipeline 或其他受支持业务边界发生可恢复失败
- **THEN** 进程退出码为 `2`

#### Scenario: 重复来源跳过返回退出码 0
- **WHEN** 合法请求命中 `status = 'processed'` 的重复来源并返回 `skipped_existing`
- **THEN** 进程退出码为 `0`

### Requirement: 协议测试基线
系统 SHALL 提供自动化测试覆盖 CLI 协议骨架、阶段二本地状态入口、阶段三 URL 路由入口、阶段四 Bilibili transcript 入口和阶段五网页文章 content 入口。

#### Scenario: 测试覆盖输入和输出边界
- **WHEN** 测试套件运行
- **THEN** 它验证 stdin JSON 解析、stdout JSON 响应、stderr 日志分离和退出码

#### Scenario: 测试覆盖公开命令入口
- **WHEN** 测试套件运行
- **THEN** 它验证已安装的 `km ingest` console script 符合 stdout JSON 和退出码契约

#### Scenario: 测试覆盖配置错误
- **WHEN** 测试套件运行
- **THEN** 它验证缺失、无效或不满足阶段二 schema 的配置会返回 `CONFIG_INVALID`

#### Scenario: 测试覆盖不支持 URL
- **WHEN** 测试套件运行
- **THEN** 它验证合法请求路由为 `unsupported` 时返回 `UNSUPPORTED_URL` 和退出码 `1`

#### Scenario: 测试覆盖 Bilibili transcript 成功
- **WHEN** 测试套件运行
- **THEN** 它使用 fake downloader 和 fake transcriber 验证 Bilibili 视频请求成功返回 `transcript_ready` 和退出码 `0`

#### Scenario: 测试覆盖网页文章 content 成功
- **WHEN** 测试套件运行
- **THEN** 它使用 fake fetcher 或 HTML fixture 验证网页文章请求成功返回 `content_ready` 和退出码 `0`

#### Scenario: 测试覆盖网页文章 content 失败
- **WHEN** 测试套件运行
- **THEN** 它验证网页抓取或解析失败时返回 `WEB_FETCH_FAILED` 或 `WEB_PARSE_FAILED` 和退出码 `2`

#### Scenario: 测试覆盖重复来源跳过
- **WHEN** 测试套件运行
- **THEN** 它验证合法请求命中 `status = 'processed'` 的重复来源时返回 `skipped_existing` 和退出码 `0`
