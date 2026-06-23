# 网页文章导入 Skill

## 适用场景

当 URL 路由结果为 `web_article` 时，使用本 skill 指导网页文章导入流程。

## 受控工具

所有 HTTP fetch、parser 选择、网页抓取、正文抽取、素材保存、总结、笔记写入和索引记录都必须通过受控 Python tools 完成。agent 路径只允许调用 `collect_web_article_text`，网页 fetch、专用 parser 选择、通用 fallback 和规范文本写入都由该受控 Python tool 内部完成。

## 工作边界

- 本 skill 只描述网页文章导入的职责边界。
- `mp.weixin.qq.com` 使用微信公众号专用 parser。
- 其他普通网页使用基于 `trafilatura` 的通用 fallback parser。
- 不得自行访问网络或解析 HTML。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 受控 collector 应保存 `raw/page.html` 和 `raw/metadata.json`，并生成用于分类和总结的 `canonical/content.md`。
- Obsidian 正文只能引用原始链接和素材路径，不嵌入完整原文。
- 首版不实现 Playwright/browser fallback、登录态/cookie 管理、CSDN 专用 parser 或知乎专用 parser。
