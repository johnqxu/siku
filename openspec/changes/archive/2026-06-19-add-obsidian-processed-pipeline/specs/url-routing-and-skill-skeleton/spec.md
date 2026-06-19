## MODIFIED Requirements

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
