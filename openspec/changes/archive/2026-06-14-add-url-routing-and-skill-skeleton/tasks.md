## 1. 测试先行

- [x] 1.1 新增 router 单元测试，覆盖 Bilibili 视频页、`b23.tv` 短链、普通网页和不支持 URL。
- [x] 1.2 新增 CLI 协议测试，覆盖 `UNSUPPORTED_URL` 响应、退出码 `1`、支持内容类型继续返回 `NOT_IMPLEMENTED` 和退出码 `2`。
- [x] 1.3 新增 skills 文件测试或文档资产检查，确认三个项目内 `SKILL.md` 存在且声明受控 tool 边界。

## 2. 路由模型与错误码

- [x] 2.1 新增 URL 路由模块，定义 `content_type` 枚举或 Literal、路由结果模型和 `route_url` 函数。
- [x] 2.2 在公开错误处理中新增 `UNSUPPORTED_URL`，响应 `recoverable: false`。
- [x] 2.3 保持 router 仅使用标准库解析 URL，不引入运行时依赖或网络访问。

## 3. CLI 集成

- [x] 3.1 在 `km ingest` 完成本地状态初始化和重复查询后调用 `route_url`。
- [x] 3.2 当路由结果为 `unsupported` 时输出 `UNSUPPORTED_URL` 并返回退出码 `1`。
- [x] 3.3 当路由结果为 `bilibili_video` 或 `web_article` 时继续输出 `NOT_IMPLEMENTED` 并返回退出码 `2`。
- [x] 3.4 确认重复来源跳过逻辑优先于 URL 路由，已处理记录仍返回 `skipped_existing` 和退出码 `0`。

## 4. 项目内 Skills 骨架

- [x] 4.1 创建 `skills/url-routing/SKILL.md`，说明路由 skill 的适用场景、输入输出和非目标。
- [x] 4.2 创建 `skills/bilibili-ingest/SKILL.md`，说明 Bilibili 视频导入 skill 的职责边界和后续 collector 依赖。
- [x] 4.3 创建 `skills/web-article-ingest/SKILL.md`，说明网页文章导入 skill 的职责边界和后续 collector 依赖。
- [x] 4.4 在 README 或设计文档中说明项目内 `skills/` 与 `.codex/skills/` 的区别。

## 5. 验证与文档

- [x] 5.1 更新 README 和 Superpowers 设计文档，记录阶段三的 URL 路由、错误码和 skills 资产约定。
- [x] 5.2 运行 `UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v`。
- [x] 5.3 运行 `openspec validate add-url-routing-and-skill-skeleton`。
- [x] 5.4 检查阶段三 OpenSpec artifacts 不包含占位符、矛盾或未决问题。
