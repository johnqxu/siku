## MODIFIED Requirements

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

#### Scenario: 项目内 skills 不绕过受控 tools
- **WHEN** 阅读任一项目内 `SKILL.md`
- **THEN** 该文件 MUST 指示 agent 通过受控 Python tools 工作，而不是自行写入素材仓库、SQLite 或 Obsidian
