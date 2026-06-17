## 1. 测试先行

- [x] 1.1 新增 Bilibili pipeline 单元测试，覆盖有字幕路径：保存元数据、保存原始字幕、生成 `canonical/transcript.md`，且不下载音频。
- [x] 1.2 新增 Bilibili pipeline 单元测试，覆盖无字幕路径：下载音频、调用 fake Whisper、生成 `canonical/transcript.md`。
- [x] 1.3 新增失败路径测试，覆盖元数据失败、音频下载失败、OpenVINO GenAI/Intel GPU 不可用和 Whisper 转写失败。
- [x] 1.4 新增 CLI 协议测试，覆盖 Bilibili 请求成功返回 `transcript_ready` 和退出码 `0`，网页文章仍返回 `NOT_IMPLEMENTED`。
- [x] 1.5 新增 skills 资产测试，确认 `bilibili-ingest` 和 `whisper-transcription` 指示使用受控 Python tools。
- [x] 1.6 新增 OpenVINO Whisper transcriber 单元测试，确认默认设备请求 `GPU` 或等价 `GPU.0`，且不会静默 CPU fallback。

## 2. 模型、错误码与资产清单

- [x] 2.1 定义 Bilibili 元数据、字幕资产、音频资产、转写结果、canonical transcript 和 asset manifest 的 Python 模型。
- [x] 2.2 新增公开错误码 helper：`BILIBILI_METADATA_FAILED`、`BILIBILI_TRANSCRIPT_FAILED`、`WHISPER_UNAVAILABLE`。
- [x] 2.3 新增 `transcript_ready` 成功响应 builder，输出 `content_type`、`source_url`、`asset_dir`、`canonical_text_path` 和 `asset_manifest`。

## 3. Bilibili 下载与字幕路径

- [x] 3.1 定义 Bilibili downloader 边界，测试中可注入 fake downloader。
- [x] 3.2 实现元数据保存到 `<asset_store_path>/<source_id>/raw/`。
- [x] 3.3 实现原始字幕保存和字幕清洗到 `canonical/transcript.md`。
- [x] 3.4 确认有字幕路径不会下载音频。

## 4. 音频下载与 Whisper fallback

- [x] 4.1 实现无字幕时下载音频到 `<asset_store_path>/<source_id>/raw/`。
- [x] 4.2 定义 OpenVINO GenAI Whisper transcriber 边界，默认目标设备为 `GPU`/`GPU.0`，测试中可注入 fake transcriber。
- [x] 4.3 实现 Whisper 转写结果写入 `canonical/transcript.md`。
- [x] 4.4 将 OpenVINO GenAI、Intel GPU runtime、模型目录不可用和转写失败映射为公开错误 envelope。

## 5. CLI 集成

- [x] 5.1 在 `km ingest` 的 `bilibili_video` 分支调用 Bilibili transcript pipeline。
- [x] 5.2 成功时返回 `transcript_ready` 和退出码 `0`。
- [x] 5.3 保持 `web_article` 新来源返回 `NOT_IMPLEMENTED` 和退出码 `2`。
- [x] 5.4 保持重复来源跳过优先于 Bilibili pipeline。

## 6. Skills 与文档

- [x] 6.1 更新 `skills/bilibili-ingest/SKILL.md`，写明元数据、字幕、音频 fallback 和素材输出约束。
- [x] 6.2 创建 `skills/whisper-transcription/SKILL.md`，写明 OpenVINO GenAI、Intel Xe 集成显卡加速、本地 Whisper 转写职责、输入输出和非目标。
- [x] 6.3 更新 README 和 Superpowers 设计文档，记录阶段四能力边界、成功响应和错误码。

## 7. 验证

- [x] 7.1 运行 `UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v`。
- [x] 7.2 运行 `openspec validate add-bilibili-transcript-pipeline`。
- [x] 7.3 检查阶段四 OpenSpec artifacts 不包含占位符、矛盾或未决问题。
