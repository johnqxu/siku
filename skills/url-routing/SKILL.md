# URL 路由 Skill

## 适用场景

当 Hermes 通过 `km ingest` 或 `km agent-ingest` 导入知识时，使用本 skill 判断一个 URL 应进入哪条导入路径。两条 CLI 共享相同 URL 分类规则，但编排路径不同：`km ingest` 由确定性 Python pipeline 编排，`km agent-ingest` 由 Deep Agents 在状态机 guard 内调用受控 Python tools。

## 受控工具

必须通过受控 Python tools 调用 `route_url` 获取路由结果。agent 路径下 `route_url` 只返回 `normalized_url` 和 `content_type`，不得创建 `source_id`、初始化素材目录或访问 SQLite。路由结果的 `content_type` 只能是：

- `bilibili_video`
- `web_article`
- `unsupported`

## 工作边界

- 只能依据 URL 的 scheme、host 和 path 做确定性判断。
- 不得访问网络。
- 不得展开短链。
- 不得下载网页、音频或视频。
- 不得自行写入素材仓库、SQLite 或 Obsidian。

## 交接规则

- `bilibili_video` 交给 Bilibili 导入能力处理。
- `web_article` 交给网页文章导入能力处理。
- `unsupported` 应转换为公开错误 `UNSUPPORTED_URL`。
