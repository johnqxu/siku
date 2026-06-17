## Why

阶段二已经建立本地状态基础，但合法新来源仍会直接停在 `NOT_IMPLEMENTED`，系统还不能判断 URL 应进入哪条后续导入路径。阶段三需要先建立稳定的内容类型路由和 skill/tool 边界，为 Bilibili 采集、网页采集和后续 Deep Agents 编排提供可测试的入口。

## What Changes

- 新增确定性 URL router，根据 `normalized_url` 将来源分类为 `bilibili_video`、`web_article` 或 `unsupported`。
- 对 Bilibili 视频 URL 建立首版识别规则，覆盖 `www.bilibili.com/video/<BV...>`、`bilibili.com/video/<BV...>`、`m.bilibili.com/video/<BV...>` 和 `b23.tv/<id>` 短链形态。
- 对普通 `http/https` 网页 URL 建立 `web_article` fallback；明确排除已知不支持或无法路由的 URL。
- 新增公开错误码 `UNSUPPORTED_URL`，用于 URL 合法但当前工具不支持处理的来源。
- 建立项目内 skills 文件骨架：`skills/url-routing/SKILL.md`、`skills/bilibili-ingest/SKILL.md`、`skills/web-article-ingest/SKILL.md`。
- 定义 typed tool 边界：新增 `route_url` 及内容类型路由结果模型；为后续 collectors 预留模型接口，但不实现采集。
- 更新 `km ingest`：通过本地状态层后先执行 URL 路由；`unsupported` 返回 `UNSUPPORTED_URL`，`bilibili_video` 和 `web_article` 仍返回 `NOT_IMPLEMENTED`。
- 不引入 LangChain Deep Agents 运行时依赖，不下载网页或 Bilibili 内容，不调用 Whisper、LLM 或 Obsidian 写入。

## Capabilities

### New Capabilities

- `url-routing-and-skill-skeleton`: 定义内容类型路由、URL router、skills 文件骨架和 typed tool 边界。

### Modified Capabilities

- `cli-contract-skeleton`: 扩展合法请求流程，使本地状态层后先进行 URL 路由，并新增 `UNSUPPORTED_URL` 失败响应。

## Impact

- 影响 `km ingest` 的合法请求处理流程：本地状态初始化和重复查询之后，进入确定性 URL 路由。
- 新增 Python 路由模块和测试，继续使用标准库，不新增运行时依赖。
- 新增项目内 `skills/` 目录及 `SKILL.md` 文件，用于版本化后续 Deep Agents 指令资产。
- 保持 Hermes 外部 JSON stdin/stdout 契约；stdout 仍只输出单个 JSON 对象。
- 后续 Bilibili 和网页采集阶段将依赖本阶段的 `content_type` 和 skill/tool 边界。
