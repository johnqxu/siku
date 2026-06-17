## Why

阶段三已经能把普通 `http/https` URL 路由为 `web_article`，但合法网页来源仍停在 `NOT_IMPLEMENTED`。阶段五需要补齐“网页文章 -> 规范正文”的文本化闭环，让后续领域分类、中文总结和 Obsidian 写入可以统一消费 `canonical/content.md`。

## What Changes

- 新增网页文章文本化 pipeline：对 `web_article` 新来源执行 HTTP 抓取、原始 HTML 保存、正文抽取、元数据保存和规范 Markdown 正文生成。
- 首期支持微信公众号文章和通用网页 fallback：
  - `mp.weixin.qq.com` 使用微信公众号专用 parser。
  - 其他普通网页使用成熟库 `trafilatura` 执行通用正文和元数据抽取。
- 新增受控 Python tools 边界：HTTP fetcher、parser resolver、Wechat parser、generic parser、canonical content writer。
- 新增运行时依赖组合：`httpx`、`trafilatura`、`beautifulsoup4`。
- 更新 `km ingest`：当 URL 路由为 `web_article` 且未命中重复来源时，执行网页文章 content pipeline。
- 成功时返回阶段性成功响应 `ok: true`、`status: "content_ready"`、`content_type: "web_article"`、`source_url`、`asset_dir`、`canonical_text_path`、`asset_manifest`、`parser_id` 和 `fetch_method`。
- 失败时返回结构化网页错误码：`WEB_FETCH_FAILED` 或 `WEB_PARSE_FAILED`。
- 更新项目内 `skills/web-article-ingest/SKILL.md`，让 skill 指导 agent 使用受控 tools，但本阶段不接入 Deep Agents 运行时。
- 不实现 Playwright/browser fallback、登录态/cookie 管理、CSDN 专用 parser、知乎专用 parser、领域分类、LLM 总结、Obsidian 写入、SQLite `processed` 记录写入或 LangChain Deep Agents 端到端编排。

## Capabilities

### New Capabilities

- `web-article-content-pipeline`: 定义微信公众号和通用网页通过 HTTP 抓取、正文抽取、元数据保存到规范 Markdown 正文的处理闭环。

### Modified Capabilities

- `cli-contract-skeleton`: 扩展合法请求流程，使 `web_article` 新来源执行 content pipeline 并返回阶段性成功或结构化失败。
- `url-routing-and-skill-skeleton`: 澄清 `route_url` 仍然只做确定性路由，同时更新网页文章导入 skill 的职责边界，使其指向受控网页文章 pipeline。

## Impact

- 影响 `km ingest` 的 `web_article` 分支；`bilibili_video` 分支继续使用阶段四 transcript pipeline。
- 新增网页 fetcher、parser resolver、微信公众号 parser、通用 parser、canonical content writer、asset manifest 模型和测试。
- 新增 Python 依赖并通过 uv 管理：`httpx`、`trafilatura`、`beautifulsoup4`。
- 会向 `<asset_store_path>/<source_id>/raw` 和 `canonical` 写入真实素材文件。
- SQLite schema 不变；本阶段不写 `sources` 新记录，避免在尚未总结和写 Obsidian 前把来源标记为 `processed`。
