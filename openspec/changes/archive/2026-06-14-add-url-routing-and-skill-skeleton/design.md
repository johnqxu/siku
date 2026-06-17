## Context

阶段一已经建立 `km ingest` 的 JSON stdin/stdout 契约，阶段二已经建立配置校验、URL 规范化、素材仓库目录和 SQLite 重复来源查询。当前合法新来源在未命中重复记录后直接返回 `NOT_IMPLEMENTED`，还没有稳定机制判断该 URL 应进入 Bilibili 视频、普通网页文章，还是不支持路径。

阶段三的目标是在采集、转写、总结和 Obsidian 写入之前，先建立一个可测试、无网络副作用的路由层。该层同时作为未来 LangChain Deep Agents skills 调用受控 Python tools 的边界：agent 可以通过 typed tool 获取内容类型，但具体下载、解析和写入仍由后续阶段实现。

## Goals / Non-Goals

**Goals:**

- 定义确定性 URL router，将规范化后的 URL 分类为 `bilibili_video`、`web_article` 或 `unsupported`。
- 支持首版 Bilibili 视频路由：`www.bilibili.com/video/<id>`、`bilibili.com/video/<id>`、`m.bilibili.com/video/<id>` 和 `b23.tv/<id>`。
- 对非 Bilibili 的普通 `http/https` URL 提供 `web_article` fallback。
- 为 URL 合法但当前不支持的来源新增 `UNSUPPORTED_URL` 错误码。
- 建立项目内 `skills/` 文件骨架，并明确这些文件是未来 Hermes/Deep Agents 的指令资产，不是 Codex 本地技能。
- 定义 `route_url` typed tool 边界和路由结果模型，供后续 collectors 复用。

**Non-Goals:**

- 不引入 LangChain Deep Agents 运行时依赖。
- 不下载网页、Bilibili 页面、音频或视频。
- 不展开 `b23.tv` 短链，也不访问网络识别真实目标。
- 不调用 Whisper、LLM 或 Obsidian 写入。
- 不向 SQLite 插入新的来源记录；阶段二的重复查询语义保持不变。
- 不实现 Bilibili/web collectors，只预留边界。

## Decisions

1. Router 使用确定性标准库实现，而不是 agent 推理。

   URL 路由属于协议层和幂等状态层之间的稳定决策，必须可测试、可复现。使用 `urllib.parse` 解析 host/path，并基于明确规则返回 typed result。替代方案是让 LLM/agent 判断内容类型，但这会让同一 URL 的结果受提示词、模型版本和上下文影响，不适合作为 CLI 契约的一部分。

2. `b23.tv` 直接路由为 `bilibili_video`，但不在本阶段展开短链。

   用户首版重点是 Bilibili 视频，`b23.tv` 是常见入口。阶段三只识别短链形态，为后续 Bilibili collector 保留网络展开或解析责任。替代方案是在 router 内发起网络请求展开短链，但这会让路由层变成 IO 层，增加失败模式，并违反本阶段无采集副作用的边界。

3. Bilibili 非 `/video/<id>` 路径返回 `unsupported`，而不是落入 `web_article`。

   Bilibili 的专栏、直播、动态和用户页都可能需要不同采集策略。将它们错误归为普通网页文章，会让后续 collector 走错路径。阶段三先保守返回 `UNSUPPORTED_URL`，未来如需要支持 Bilibili 专栏，可以新增明确内容类型。

4. 非 Bilibili 的 `http/https` URL 默认路由为 `web_article`。

   普通网页采集会在后续阶段负责正文抽取和失败处理。router 不尝试判断网页是否真的是文章，以避免提前引入网络请求或复杂启发式。替代方案是先维护域名白名单，但这会降低工具对长尾知识来源的覆盖。

5. `UNSUPPORTED_URL` 作为非可恢复失败，退出码为 `1`。

   该错误表示输入 URL 语法有效，但当前版本没有对应处理能力；原样重试不会改变结果。因此响应 `recoverable` 为 `false`，CLI 退出码为 `1`。可恢复处理失败仍保留给已进入业务处理但受暂未实现或临时失败影响的场景，例如当前阶段支持内容类型仍返回 `NOT_IMPLEMENTED` 和退出码 `2`。

6. 项目内 skills 放在仓库根目录 `skills/`，与 `.codex/skills/` 分离。

   `.codex/skills/` 是当前研发助手使用的本地技能，不应混入产品运行时指令资产。`skills/url-routing/SKILL.md`、`skills/bilibili-ingest/SKILL.md` 和 `skills/web-article-ingest/SKILL.md` 将作为未来 Hermes/Deep Agents 可加载的版本化说明文件。

## Risks / Trade-offs

- `b23.tv` 未展开可能误判非视频短链 -> 本阶段只承诺“短链形态路由”，后续 Bilibili collector 负责展开并在不匹配时返回采集失败。
- `web_article` fallback 可能包含非文章页面 -> 后续网页采集阶段通过正文抽取结果决定是否失败；router 不承担语义判定。
- 新增项目内 `skills/` 容易与研发环境技能混淆 -> 在 skills 文件和 README 中明确其用途是 Hermes/Deep Agents 指令资产。
- `UNSUPPORTED_URL` 使用退出码 `1` 可能与输入/配置错误同码 -> 公开 `error_code` 是细分原因的权威字段，退出码只表达是否可重试。

## Migration Plan

阶段三不需要数据迁移。实现时先增加 router 单元测试和 CLI 协议测试，再添加路由模块、错误码和 skills 文件。已有阶段二 SQLite schema 保持不变，`content_type` 字段继续预留给后续真正写入来源记录的阶段。

回退策略是移除 router 调用后恢复为阶段二行为：合法新来源未命中重复记录时直接返回 `NOT_IMPLEMENTED`。

## Open Questions

- 暂无。Bilibili 专栏、直播、动态和其他平台 URL 在本阶段统一视为不支持，后续阶段按优先级新增内容类型。
