# Bilibili 导入 Skill

## 适用场景

当 URL 路由结果为 `bilibili_video` 时，使用本 skill 指导后续 Bilibili 视频导入流程。

## 受控工具

所有副作用必须通过受控 Python tools 完成。agent 路径只允许调用 `collect_bilibili_text`，Bilibili 元数据、字幕、音频下载、Whisper 转写和规范文本写入都由该受控 Python tool 内部完成。

## 工作边界

- 本 skill 只描述流程和约束，不直接下载 Bilibili 页面、字幕、音频或视频。
- 不得自行调用 shell。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 没有字幕时，应通过 `collect_bilibili_text` 内部下载音频，并使用 `whisper-transcription` skill 指导 OpenVINO GenAI + Intel Xe 集成显卡本地转写。
- Obsidian 正文只能引用原始链接和素材路径，不嵌入完整转写稿。
