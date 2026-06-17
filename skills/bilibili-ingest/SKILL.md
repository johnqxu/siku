# Bilibili 导入 Skill

## 适用场景

当 URL 路由结果为 `bilibili_video` 时，使用本 skill 指导后续 Bilibili 视频导入流程。

## 受控工具

所有副作用必须通过受控 Python tools 完成。阶段四通过 Bilibili transcript pipeline 下载元数据、获取字幕、在无字幕时下载音频，并交给 OpenVINO GenAI Whisper 转写能力生成规范文本。

## 工作边界

- 本 skill 只描述流程和约束，不直接下载 Bilibili 页面、字幕、音频或视频。
- 不得自行调用 shell。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 没有字幕时，应通过受控 Python tools 下载音频，并使用 `whisper-transcription` skill 指导 OpenVINO GenAI + Intel Xe 集成显卡本地转写。
- Obsidian 正文只能引用原始链接和素材路径，不嵌入完整转写稿。

## 本阶段非目标

阶段四不做领域分类、LLM 总结、Obsidian 写入，也不接入 Deep Agents 运行时。
