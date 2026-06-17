# web-article-content-pipeline Specification

## Purpose
定义网页文章来源到规范正文的阶段五处理能力，包括受控 HTTP 抓取、微信公众号专用解析、通用网页 fallback 解析、素材保存、规范正文输出和公开错误映射。
## Requirements
### Requirement: 网页文章 content pipeline 入口
系统 SHALL 为 `web_article` 来源提供网页文章到规范正文的处理 pipeline，并在规范正文生成后由当前 Python 确定性 pipeline 继续执行领域分类和中文总结。

#### Scenario: 网页文章进入 content pipeline
- **WHEN** `km ingest` 请求通过本地状态层和 URL 路由，且路由结果为 `web_article`
- **THEN** 系统执行网页文章 content pipeline，而不是返回 `NOT_IMPLEMENTED`

#### Scenario: content 成功后进入领域分类
- **WHEN** 网页文章 content pipeline 产出规范正文
- **THEN** 系统继续执行领域分类 pipeline

#### Scenario: 领域分类成功后进入中文总结
- **WHEN** 网页文章 content pipeline 和领域分类 pipeline 均成功
- **THEN** 系统继续执行中文总结 pipeline，并在成功时返回 `summary_ready`

#### Scenario: pipeline 不执行更后续知识处理
- **WHEN** 网页文章 content pipeline、领域分类 pipeline 和中文总结 pipeline 均成功
- **THEN** 系统 MUST NOT 执行 Obsidian 写入、SQLite `processed` 记录写入或 Deep Agents 端到端编排

### Requirement: HTTP 网页抓取
系统 SHALL 通过受控 HTTP fetcher 抓取网页 HTML，并保存原始 HTML。

#### Scenario: 原始 HTML 被保存到 raw
- **WHEN** HTTP 抓取成功且响应可被识别为 HTML
- **THEN** 系统在 `<asset_store_path>/<source_id>/raw/page.html` 保存原始 HTML

#### Scenario: HTTP 抓取记录 fetch_method
- **WHEN** HTTP 抓取成功
- **THEN** pipeline 结果记录 `fetch_method: "http"`

#### Scenario: 抓取失败返回结构化错误
- **WHEN** HTTP 请求失败、超时、状态码不可用或响应不能被识别为 HTML
- **THEN** 系统返回 `ok: false` 且 `error_code: "WEB_FETCH_FAILED"`

#### Scenario: 不使用浏览器 fallback
- **WHEN** HTTP 抓取失败或网页需要浏览器渲染才能得到正文
- **THEN** 系统 MUST NOT 启动 Playwright、浏览器渲染、登录态或 cookie fallback

### Requirement: 网页 parser 选择
系统 SHALL 根据 URL 和 HTML 选择微信公众号专用 parser 或通用网页 fallback parser。

#### Scenario: 微信公众号 URL 使用专用 parser
- **WHEN** `normalized_url` 的 host 为 `mp.weixin.qq.com`
- **THEN** 系统选择 `parser_id: "wechat_article"`

#### Scenario: 非微信公众号网页使用通用 parser
- **WHEN** `normalized_url` 是 `web_article` 且 host 不是 `mp.weixin.qq.com`
- **THEN** 系统选择 `parser_id: "generic_article"`

#### Scenario: parser 选择不交给 agent 自行判断
- **WHEN** 网页文章 content pipeline 执行 parser 选择
- **THEN** parser 选择由受控 Python tool 完成，而不是由 agent 直接解析 DOM 或自行决定写入格式

### Requirement: 微信公众号文章解析
系统 SHALL 使用微信公众号专用 parser 从可访问的微信公众号 HTML 中抽取正文和元数据。

#### Scenario: 微信公众号正文被抽取
- **WHEN** 微信公众号 HTML 包含可解析正文容器
- **THEN** parser 输出标题、正文 Markdown 和 `parser_id: "wechat_article"`

#### Scenario: 微信公众号元数据被抽取
- **WHEN** 微信公众号 HTML 包含公众号名称、作者或发布时间等元数据
- **THEN** parser 将可用元数据写入 `raw/metadata.json`

#### Scenario: 微信公众号解析失败返回结构化错误
- **WHEN** 微信公众号 HTML 已保存但无法抽取有效标题或正文
- **THEN** 系统返回 `ok: false` 且 `error_code: "WEB_PARSE_FAILED"`

### Requirement: 通用网页 fallback 解析
系统 SHALL 使用成熟正文抽取库处理非微信公众号普通网页。

#### Scenario: 通用网页正文被抽取
- **WHEN** 通用网页 HTML 包含可解析文章正文
- **THEN** 系统通过 `trafilatura` 或其受控 wrapper 输出标题、正文 Markdown 和 `parser_id: "generic_article"`

#### Scenario: 通用网页元数据被抽取
- **WHEN** 通用网页 HTML 包含可解析标题、作者、日期或站点元数据
- **THEN** parser 将可用元数据写入 `raw/metadata.json`

#### Scenario: 通用网页解析失败返回结构化错误
- **WHEN** 通用网页 HTML 已保存但成熟正文抽取库无法抽取有效标题或正文
- **THEN** 系统返回 `ok: false` 且 `error_code: "WEB_PARSE_FAILED"`

### Requirement: 规范正文与 asset manifest
系统 SHALL 为网页文章 content pipeline 产出规范正文和素材清单。

#### Scenario: content_ready 成功响应
- **WHEN** 网页文章 content pipeline 成功生成 `canonical/content.md`
- **THEN** stdout JSON 包含 `ok: true`、`status: "content_ready"`、`content_type: "web_article"`、`source_url`、`asset_dir`、`canonical_text_path`、`asset_manifest`、`parser_id` 和 `fetch_method`

#### Scenario: asset_manifest 记录网页素材
- **WHEN** pipeline 成功
- **THEN** `asset_manifest` 记录 `raw/page.html`、`raw/metadata.json` 和 `canonical/content.md`

#### Scenario: canonical content 是规范 Markdown
- **WHEN** pipeline 成功
- **THEN** `canonical/content.md` 是 UTF-8 Markdown 文件，并包含可供后续分类和总结使用的正文文本

#### Scenario: canonical content 引用原始链接
- **WHEN** pipeline 成功
- **THEN** `canonical/content.md` 包含原始来源 URL 引用，但不嵌入原始 HTML

### Requirement: 受控 tool 边界
系统 SHALL 通过受控 Python tools 执行网页抓取、parser 选择、正文抽取和规范正文写入。

#### Scenario: tools 封装副作用
- **WHEN** pipeline 需要访问网络或写入文件
- **THEN** 它通过 `fetch_web_article`、`resolve_web_article_parser`、`parse_web_article` 或 `write_canonical_content` 等受控 tools 完成

#### Scenario: skills 不直接执行副作用
- **WHEN** 阅读 `skills/web-article-ingest/SKILL.md`
- **THEN** skill 文件 MUST 指示 agent 使用受控 Python tools，而不是自行访问网络、解析 HTML 或写入素材仓库

### Requirement: 测试替身与 fixture
系统 SHALL 使用测试替身和 HTML fixture 验证网页文章 content pipeline 的核心行为。

#### Scenario: 单元测试不依赖真实网络
- **WHEN** 单元测试运行
- **THEN** 网页 HTTP 抓取行为使用 fixture 或 fake fetcher，而不是访问真实网页

#### Scenario: 单元测试覆盖微信公众号解析
- **WHEN** 单元测试运行
- **THEN** 它使用微信公众号 HTML fixture 验证标题、元数据、正文和 `canonical/content.md` 输出

#### Scenario: 单元测试覆盖通用 fallback 解析
- **WHEN** 单元测试运行
- **THEN** 它使用通用网页 HTML fixture 验证 `trafilatura` wrapper 的成功和失败路径

