## Context

当前系统已经完成 CLI 契约、本地状态层、URL 路由和 Bilibili 视频文本化。普通网页 URL 会被路由为 `web_article`，但仍返回 `NOT_IMPLEMENTED`。后续领域分类、总结和 Obsidian 写入都需要稳定的规范文本输入，因此阶段五需要把网页文章处理成 `canonical/content.md`。

用户已确认第五阶段首期只支持微信公众号和通用网页 fallback，不支持 Playwright/browser fallback。通用网页抽取采用成熟库，不手写完整正文抽取算法。依赖组合确定为 `httpx`、`trafilatura`、`beautifulsoup4`，并继续由 uv 管理依赖和锁文件。

## Goals / Non-Goals

**Goals:**

- 对 `web_article` URL 执行网页文章到规范正文的文本化流程。
- 通过 HTTP 抓取 HTML，并将原始 HTML 保存到 `<asset_store_path>/<source_id>/raw/page.html`。
- 首期支持 `mp.weixin.qq.com` 微信公众号专用解析。
- 对其他普通网页使用 `trafilatura` 作为通用 fallback 抽取正文和元数据。
- 将标题、作者、发布时间、parser/fetch 信息等元数据保存到 `raw/metadata.json`。
- 生成 UTF-8 Markdown 文件 `canonical/content.md`，作为后续分类和总结的统一输入。
- 成功时返回 `content_ready` 阶段性成功响应。
- 失败时返回稳定错误 envelope 和明确错误码。
- 通过 typed Python tools 封装 HTTP 抓取、parser 选择、HTML 解析和规范正文写入。
- 单元测试使用 fixture/fake fetcher，不依赖真实网络。

**Non-Goals:**

- 不实现 Playwright、浏览器渲染、登录态、cookie 管理或反爬绕过。
- 不实现 CSDN、知乎或其他站点专用 parser。
- 不做领域分类、中文总结或 LLM 调用。
- 不写 Obsidian 笔记。
- 不将来源记录写入 SQLite `processed`；真正处理完成留到 Obsidian 阶段。
- 不接入 LangChain Deep Agents 运行时。
- 不要求单元测试访问真实网页。

## Decisions

1. 阶段五以网页文章到规范正文闭环为一个 OpenSpec change。

   微信公众号和通用网页都属于“网页文章 -> 规范正文”的同一业务承诺。把它们拆成两个阶段会让 `web_article` 分支长期停留在不完整状态，也会让后续领域分类需要同时处理多种未规范化输入。

2. 抓取和解析分层。

   `WebArticleFetcher` 只负责 HTTP 请求、超时、状态码、content-type 和最终 HTML；parser 不关心网络。`WebArticleParserResolver` 只根据 URL/HTML 选择 parser；具体 parser 只负责把 HTML 转为内部 `ParsedWebArticle` 模型。这样可以用 fixture 测 parser，用 fake fetcher 测 pipeline。

3. 首期只使用 HTTP fetch，不做 browser fallback。

   Playwright 可以提高动态页面兼容性，但会引入浏览器安装、运行环境、超时、截图/渲染等待和 CI 复杂度。用户已经收束本期不支持 Playwright，因此无法通过普通 HTTP 获取或解析的网页返回结构化错误，不尝试绕过。

4. 通用 fallback 使用 `trafilatura`，不自研通用正文抽取。

   普通网页噪音来源很多，包括导航、广告、推荐、评论、页脚和重复模板。自研规则首期容易变成高维护成本。`trafilatura` 的能力更贴近“主正文 + 元数据”的需求；本项目仍保留外层 wrapper，避免第三方库的数据结构扩散到 CLI 响应和后续 pipeline。

5. 微信公众号使用专用 parser。

   微信公众号文章 DOM 结构相对固定，标题、作者/公众号名、发布时间和正文容器有明确候选位置。专用 parser 可以比通用 fallback 更好地保留正文、图片占位、段落和代码/引用结构，并减少推荐、版权、脚本等噪音。

6. 成功响应使用 `content_ready`，而不是 `created`。

   本阶段只创建规范正文和素材，不做总结、不写 Obsidian、不记录 `processed`。`created` 容易被误解为完整知识笔记已完成，因此使用阶段性状态更准确。

7. `canonical/content.md` 不嵌入原始 HTML。

   素材仓库中的 `raw/page.html` 保存原始页面；`canonical/content.md` 只保存清洗后的标题、来源链接、元数据摘要和正文 Markdown。后续 Obsidian 笔记仍只引用原始链接和素材路径，不把完整原文放入 Obsidian 正文。

8. `source_id` 和素材目录继续来自阶段二 `normalized_url`。

   阶段五不改变 URL 规范化、去重查询或素材目录策略。若网页内存在 canonical URL，可写入 `raw/metadata.json`，但不改变本次请求的素材目录。

## Risks / Trade-offs

- 部分微信公众号文章需要登录、cookie 或浏览器渲染 -> 本阶段返回 `WEB_FETCH_FAILED` 或 `WEB_PARSE_FAILED`，不尝试绕过；browser fallback 留给后续增强。
- 通用网页正文抽取可能误删或保留噪音 -> 使用 `trafilatura` 降低基线风险，并通过 fixture 覆盖典型成功和失败路径；后续可为高价值站点添加专用 parser。
- 网页编码、压缩和 content-type 不一致 -> HTTP fetcher 负责统一解码和 HTML 判断；无法安全识别为 HTML 时返回 `WEB_FETCH_FAILED`。
- 原始 HTML 可能较大 -> 保存在外部素材仓库 `raw/`，不写入 Obsidian；manifest 明确记录文件路径。
- 阶段性成功不写 SQLite 记录可能导致重复执行重新抓取 -> 这是阶段边界取舍；完整去重写入将在 Obsidian 端到端阶段处理。
- 第三方库行为升级可能影响抽取结果 -> 通过 uv 锁文件固定版本，并用 fixture 测试约束项目可见行为。

## Migration Plan

无需数据迁移。阶段五复用现有素材目录结构：

```text
<asset_store_path>/<source_id>/
  raw/
  canonical/
  summary/
```

新增文件由网页文章 pipeline 在来源目录内创建。失败时允许保留已抓取的 `raw/page.html`，便于排查；CLI 仍通过结构化错误返回失败。回滚方式是移除 `web_article` pipeline 集成，让 `web_article` 分支恢复为 `NOT_IMPLEMENTED`。

## Open Questions

- 暂无。阶段五范围已收敛为 HTTP fetch、微信公众号专用 parser、`trafilatura` 通用 fallback、规范正文输出，不包含 browser fallback。
