## 1. 测试先行

- [x] 1.1 新增网页 pipeline 单元测试，覆盖微信公众号路径：HTTP fixture、保存 `raw/page.html`、保存 `raw/metadata.json`、生成 `canonical/content.md`，返回 `parser_id: "wechat_article"` 和 `fetch_method: "http"`。
- [x] 1.2 新增网页 pipeline 单元测试，覆盖通用 fallback 路径：普通 HTML fixture 通过 `trafilatura` wrapper 抽取正文，生成 `canonical/content.md`，返回 `parser_id: "generic_article"`。
- [x] 1.3 新增失败路径测试，覆盖 HTTP 抓取失败、非 HTML 响应、微信公众号解析失败和通用 parser 解析失败。
- [x] 1.4 新增 CLI 协议测试，覆盖 `web_article` 请求成功返回 `content_ready` 和退出码 `0`。
- [x] 1.5 更新 CLI 协议测试，确认网页抓取或解析失败返回 `WEB_FETCH_FAILED` 或 `WEB_PARSE_FAILED` 和退出码 `2`。
- [x] 1.6 更新 skills 资产测试，确认 `skills/web-article-ingest/SKILL.md` 指示使用受控 Python tools，不允许 agent 自行访问网络、解析 HTML 或写入素材仓库。

## 2. 依赖、模型、错误码与响应

- [x] 2.1 使用 uv 将 `httpx`、`trafilatura`、`beautifulsoup4` 加入项目依赖，并更新 `uv.lock`。
- [x] 2.2 定义网页抓取结果、网页解析结果、网页元数据、canonical content 和 asset manifest 的 Python 模型。
- [x] 2.3 新增公开错误码 helper：`WEB_FETCH_FAILED` 和 `WEB_PARSE_FAILED`。
- [x] 2.4 新增 `content_ready` 成功响应 builder，输出 `content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`asset_manifest`、`parser_id` 和 `fetch_method`。

## 3. HTTP 抓取与 parser 选择

- [x] 3.1 定义 `WebArticleFetcher` 边界，测试中可注入 fake fetcher。
- [x] 3.2 实现受控 HTTP fetcher，处理超时、状态码、HTML content-type 判断和响应文本解码。
- [x] 3.3 实现原始 HTML 保存到 `<asset_store_path>/<source_id>/raw/page.html`。
- [x] 3.4 实现 `resolve_web_article_parser`，将 `mp.weixin.qq.com` 选择为 `wechat_article`，其他 `web_article` 选择为 `generic_article`。
- [x] 3.5 确认阶段五不调用 Playwright、浏览器渲染、登录态或 cookie fallback。

## 4. 微信公众号 parser

- [x] 4.1 实现 `WechatArticleParser`，从微信公众号 HTML fixture 抽取标题、正文 Markdown 和可用元数据。
- [x] 4.2 将微信公众号可用元数据写入 `raw/metadata.json`。
- [x] 4.3 在无法抽取有效标题或正文时返回 `WEB_PARSE_FAILED`。

## 5. 通用 fallback parser

- [x] 5.1 实现 `GenericArticleParser`，通过 `trafilatura` 受控 wrapper 抽取标题、正文 Markdown 和可用元数据。
- [x] 5.2 将通用网页可用元数据写入 `raw/metadata.json`。
- [x] 5.3 在 `trafilatura` 无法抽取有效标题或正文时返回 `WEB_PARSE_FAILED`。

## 6. 网页文章 pipeline 与 CLI 集成

- [x] 6.1 实现 `collect_web_article`，编排 HTTP fetch、parser 选择、正文抽取、素材保存和 canonical content 写入。
- [x] 6.2 生成 UTF-8 Markdown 文件 `canonical/content.md`，包含原始 URL 引用和可供后续分类总结使用的正文文本，不嵌入原始 HTML。
- [x] 6.3 在 `km ingest` 的 `web_article` 分支调用网页文章 content pipeline。
- [x] 6.4 成功时返回 `content_ready` 和退出码 `0`。
- [x] 6.5 保持重复来源跳过优先于网页文章 content pipeline。
- [x] 6.6 保持 `bilibili_video` 分支继续调用阶段四 transcript pipeline。

## 7. Skills 与文档

- [x] 7.1 更新 `skills/web-article-ingest/SKILL.md`，写明 HTTP fetch、微信公众号 parser、通用 fallback parser、素材输出约束和本阶段非目标。
- [x] 7.2 更新 README，记录阶段五能力边界、依赖、成功响应和错误码。
- [x] 7.3 更新 Superpowers 设计文档，记录阶段五网页文章文本化方案。

## 8. 验证

- [x] 8.1 运行 `UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v`。
- [x] 8.2 运行 `openspec validate add-web-article-content-pipeline`。
- [x] 8.3 检查第五阶段 OpenSpec artifacts 不包含占位符、矛盾或未决问题。
