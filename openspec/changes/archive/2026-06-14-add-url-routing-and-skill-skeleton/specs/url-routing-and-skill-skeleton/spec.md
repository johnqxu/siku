## ADDED Requirements

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
- **THEN** 调用方可以根据 `content_type` 选择后续 collector，但本阶段不执行 collector

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
- **THEN** `skills/web-article-ingest/SKILL.md` 存在，并说明网页文章导入的职责边界和本阶段非目标

#### Scenario: 项目内 skills 不绕过受控 tools
- **WHEN** 阅读任一项目内 `SKILL.md`
- **THEN** 该文件 MUST 指示 agent 通过受控 Python tools 工作，而不是自行写入素材仓库、SQLite 或 Obsidian
