# URL 路由 Skill

## 适用场景

当 Hermes 或未来 Deep Agents 需要判断一个已经规范化的 URL 应进入哪条导入路径时，使用本 skill。

## 受控工具

必须通过受控 Python tools 调用 `route_url(normalized_url)` 获取路由结果。路由结果的 `content_type` 只能是：

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
