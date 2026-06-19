# url-routing-and-skill-skeleton Specification

## Purpose
定义知识导入工具的确定性 URL 路由、内容类型路由结果、`route_url` 受控 tool 边界，以及面向 Hermes/Deep Agents 的项目内 skills 骨架。
## Requirements
### Requirement: 内容类型路由模型
系统 SHALL 提供确定性的 URL 路由模型，将规范化后的 URL 分类为 `bilibili_video`、`web_article` 或 `unsupported`。

#### Scenario: 路由结果包含内容类型
- **WHEN** 系统对规范化后的 URL 执行路由
- **THEN** 路由结果包含 `content_type`，且其值为 `bilibili_video`、`web_article` 或 `unsupported`

#### Scenario: 路由不访问网络
- **WHEN** 系统对任意规范化后的 URL 执行路由
- **THEN** 系统 MUST NOT 发起网络请求、下载页面或展开短链
### Requirement: Bilibili 视频 URL 路由
系统 SHALL 将首版支持的 Bilibili 视频 URL 路由为 `bilibili_video`。

#### Scenario: www Bilibili 视频页被识别
- **WHEN** `normalized_url` 的 host 为 `www.bilibili.com` 且 path 形如 `/video/<id>`
- **THEN** 路由结果的 `content_type` 为 `bilibili_video`

#### Scenario: 根域名 Bilibili 视频页被识别
- **WHEN** `normalized_url` 的 host 为 `bilibili.com` 且 path 形如 `/video/<id>`
- **THEN** 路由结果的 `content_type` 为 `bilibili_video`

#### Scenario: 移动端 Bilibili 视频页被识别
- **WHEN** `normalized_url` 的 host 为 `m.bilibili.com` 且 path 形如 `/video/<id>`
- **THEN** 路由结果的 `content_type` 为 `bilibili_video`

#### Scenario: b23 短链被识别为 Bilibili 视频候选
- **WHEN** `normalized_url` 的 host 为 `b23.tv` 且 path 包含一个非空短链标识
- **THEN** 路由结果的 `content_type` 为 `bilibili_video`
### Requirement: 普通网页 URL 路由
系统 SHALL 将非 Bilibili 的普通 `http` 或 `https` URL 路由为 `web_article`。

#### Scenario: 非 Bilibili HTTPS URL 被识别为网页文章候选
- **WHEN** `normalized_url` 为 `https://example.com/article`
- **THEN** 路由结果的 `content_type` 为 `web_article`

#### Scenario: 非 Bilibili HTTP URL 被识别为网页文章候选
- **WHEN** `normalized_url` 为 `http://example.com/article`
- **THEN** 路由结果的 `content_type` 为 `web_article`
### Requirement: 不支持 URL 路由
系统 SHALL 对 URL 语法有效但当前没有明确处理能力的来源返回 `unsupported`。

#### Scenario: Bilibili 非视频路径不落入网页 fallback
- **WHEN** `normalized_url` 的 host 为 `www.bilibili.com` 且 path 不是 `/video/<id>`
- **THEN** 路由结果的 `content_type` 为 `unsupported`

#### Scenario: 空 b23 路径不被识别为视频
- **WHEN** `normalized_url` 的 host 为 `b23.tv` 且 path 不包含短链标识
- **THEN** 路由结果的 `content_type` 为 `unsupported`
### Requirement: route_url typed tool 边界
系统 SHALL 提供 `route_url` 作为受控 Python tool 边界，供 CLI 和未来 agent skills 复用。

#### Scenario: route_url 接收规范化 URL
- **WHEN** 调用方将 `normalized_url` 传入 `route_url`
- **THEN** `route_url` 返回内容类型路由结果，而不是直接执行下载、解析、转写、总结或写入

#### Scenario: route_url 结果可被后续 collector 选择使用
- **WHEN** `route_url` 返回 `bilibili_video` 或 `web_article`
- **THEN** 调用方可以根据 `content_type` 选择后续 collector 或 pipeline

#### Scenario: route_url 不执行网页抓取
- **WHEN** `route_url` 返回 `web_article`
- **THEN** `route_url` MUST NOT 发起 HTTP 请求、下载 HTML、解析正文或写入素材仓库
### Requirement: 项目内 skills 文件骨架
系统 SHALL 在仓库根目录维护面向 Hermes/Deep Agents 的项目内 skills 文件骨架。

#### Scenario: URL 路由 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/url-routing/SKILL.md` 存在，并说明何时使用 URL 路由 tool

#### Scenario: Bilibili 导入 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/bilibili-ingest/SKILL.md` 存在，并说明 Bilibili 视频导入的职责边界和本阶段非目标

#### Scenario: 网页文章导入 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/web-article-ingest/SKILL.md` 存在，并说明网页文章导入应通过受控网页文章 pipeline 处理 HTTP 抓取、parser 选择、正文抽取和规范正文写入

#### Scenario: 领域分类 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/domain-classification/SKILL.md` 存在，并说明固定领域表、单一主领域、低置信度归入 `其他` 和受控分类 tool 边界

#### Scenario: 中文总结 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/summary-generation/SKILL.md` 存在，并说明中文总结必须通过受控 Python 总结工具执行

#### Scenario: Obsidian 写入 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/obsidian-write/SKILL.md` 存在，并说明 Obsidian note 写入必须通过受控 Python tools 执行

#### Scenario: 项目内 skills 不绕过受控 tools
- **WHEN** 阅读任一项目内 `SKILL.md`
- **THEN** 该文件 MUST 指示 agent 通过受控 Python tools 工作，而不是自行调用 LLM、写入素材仓库、SQLite 或 Obsidian
### Requirement: Hermes 完整知识导入 skill
系统 SHALL 在项目内 skills 目录维护 `hermes-knowledge-ingest` 高层 skill，作为 Hermes 调用完整知识导入流程的入口。

#### Scenario: Hermes 高层 skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/hermes-knowledge-ingest/SKILL.md` MUST 存在，并说明该 skill 面向 Hermes 调用完整知识导入流程

#### Scenario: Hermes skill 使用当前稳定 CLI
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 指示 Hermes 在 `/home/xu/workspace/siku` 下运行 `uv run --env-file .env km ingest`

#### Scenario: Hermes skill 定义 stdin 请求
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 指示 Hermes 通过 stdin 传入单个 JSON object，包含 `url` 和 `mode: "ingest"`

#### Scenario: Hermes skill 轻量预检查
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 要求 Hermes 在调用前确认当前目录、`.env`、`KM_CONFIG` 和 `DEEPSEEK_API_KEY`

#### Scenario: Hermes skill 不重复完整校验
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 Obsidian 路径、素材仓库路径、URL 合法性、Whisper 运行时、下载器和 SQLite 错误由 CLI 负责返回结构化 JSON

#### Scenario: Hermes skill 解释成功状态
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 `processed_ready` 表示完整导入完成，`skipped_existing` 表示已处理且不应重复导入

#### Scenario: Hermes skill 保留失败 envelope
- **WHEN** `km ingest` 返回失败 JSON
- **THEN** skill 文档 MUST 指示 Hermes 保留 `ok`、`error_code`、`message` 和 `recoverable`，并 MUST NOT 将业务错误只转换成对话式摘要

#### Scenario: Hermes skill 不额外重试
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 声明 skill 不增加自己的重试循环，并说明 `recoverable: true` 只允许 Hermes 在 workflow 层稍后重试

#### Scenario: Hermes skill 禁止内部工具调用
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 禁止 Hermes 直接调用 `route_url`、`collect_bilibili_text`、`collect_web_article_text`、`classify_domain`、`generate_summary`、`write_obsidian_note` 或 `mark_source_processed`

#### Scenario: Hermes skill 不读取生成内容
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 说明 Hermes 默认只使用 stdout JSON 和路径字段做任务跟踪，不主动读取 note、summary、transcript、HTML、audio 或其他生成文件内容

#### Scenario: Hermes skill 记录 agent 入口迁移
- **WHEN** 阅读 `skills/hermes-knowledge-ingest/SKILL.md`
- **THEN** 文档 MUST 记录阶段九实现后可显式切换到 `uv run --extra agent --env-file .env km agent-ingest`，且 MUST 禁止从 `km agent-ingest` 自动 fallback 到 `km ingest`
### Requirement: Hermes skill 测试覆盖
系统 SHALL 通过自动化测试覆盖 `hermes-knowledge-ingest` skill 的存在性和关键边界。

#### Scenario: 测试覆盖 Hermes skill 文件
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `skills/hermes-knowledge-ingest/SKILL.md` 存在

#### Scenario: 测试覆盖 Hermes skill 命令
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `hermes-knowledge-ingest` skill 记录当前命令 `uv run --env-file .env km ingest`

#### Scenario: 测试覆盖 Hermes skill 边界
- **WHEN** 测试套件运行
- **THEN** 它 MUST 验证 `hermes-knowledge-ingest` skill 说明轻量预检查、不额外重试、禁止内部工具调用、默认不读取生成内容，以及未来切换 `km agent-ingest` 不自动 fallback
