## Why

阶段三已经能把 Bilibili 视频 URL 路由为 `bilibili_video`，但合法新来源仍停在 `NOT_IMPLEMENTED`。阶段四需要把 Bilibili 视频处理成后续领域分类和总结可依赖的规范文本，形成“元数据/字幕/音频/Whisper -> canonical transcript”的闭环。

## What Changes

- 新增 Bilibili 视频文本化 pipeline：下载元数据，优先获取字幕；无字幕时下载音频并使用本地 Whisper 转写。
- Whisper 本地转写采用 OpenVINO GenAI 后端，默认使用 Intel Xe 集成显卡加速，目标设备为 `GPU` 或等价的 `GPU.0`。
- 新增规范中间模型：Bilibili 元数据、字幕资产、音频资产、Whisper 转写结果、`canonical/transcript.md` 和 asset manifest。
- 新增受控 Python tools 边界：`collect_bilibili_video`、`download_bilibili_audio`、`transcribe_with_whisper`、`write_canonical_transcript`。
- 更新 `km ingest`：当 URL 路由为 `bilibili_video` 且未命中重复来源时，执行 Bilibili transcript pipeline。
- 成功时返回阶段性成功响应 `ok: true`、`status: "transcript_ready"`、`content_type: "bilibili_video"`、`source_url`、`asset_dir`、`canonical_text_path` 和 `asset_manifest`。
- 失败时返回结构化 Bilibili/Whisper 错误码，例如 `BILIBILI_METADATA_FAILED`、`BILIBILI_TRANSCRIPT_FAILED`、`WHISPER_UNAVAILABLE`。
- 更新项目内 `skills/bilibili-ingest/SKILL.md`，新增 `skills/whisper-transcription/SKILL.md`，让 skill 指导 agent 使用受控 tools，但本阶段不接入 Deep Agents 运行时。
- 不实现网页文章采集、领域分类、LLM 总结、Obsidian 写入、SQLite `processed` 记录写入或 LangChain Deep Agents 端到端编排。

## Capabilities

### New Capabilities

- `bilibili-transcript-pipeline`: 定义 Bilibili 视频元数据/字幕/音频/Whisper 到规范文本的完整处理闭环。

### Modified Capabilities

- `cli-contract-skeleton`: 扩展合法请求流程，使 `bilibili_video` 新来源执行 transcript pipeline 并返回阶段性成功或结构化失败。

## Impact

- 影响 `km ingest` 的 `bilibili_video` 分支；`web_article` 仍返回 `NOT_IMPLEMENTED`。
- 新增 Bilibili collector、Whisper wrapper、canonical transcript writer、asset manifest 模型和测试。
- 可能新增运行时依赖或外部可执行程序约定：Bilibili 下载工具应通过受控 Python wrapper 使用，Whisper 必须走本地 OpenVINO GenAI 执行环境和 Intel GPU runtime。
- 会向 `<asset_store_path>/<source_id>/raw` 和 `canonical` 写入真实素材文件。
- SQLite schema 不变；本阶段不写 `sources` 新记录，避免在尚未总结和写 Obsidian 前把来源标记为 `processed`。
