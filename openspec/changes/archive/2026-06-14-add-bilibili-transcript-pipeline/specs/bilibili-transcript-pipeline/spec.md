## ADDED Requirements

### Requirement: Bilibili transcript pipeline 入口
系统 SHALL 为 `bilibili_video` 来源提供 Bilibili 视频到规范文本的处理 pipeline。

#### Scenario: Bilibili 视频进入 transcript pipeline
- **WHEN** `km ingest` 请求通过本地状态层和 URL 路由，且路由结果为 `bilibili_video`
- **THEN** 系统执行 Bilibili transcript pipeline，而不是返回 `NOT_IMPLEMENTED`

#### Scenario: pipeline 不执行后续知识处理
- **WHEN** Bilibili transcript pipeline 产出规范文本
- **THEN** 系统 MUST NOT 执行领域分类、LLM 总结、Obsidian 写入或 Deep Agents 端到端编排

### Requirement: Bilibili 元数据采集
系统 SHALL 下载并保存 Bilibili 视频元数据。

#### Scenario: 元数据被保存到 raw
- **WHEN** Bilibili 元数据采集成功
- **THEN** 系统在 `<asset_store_path>/<source_id>/raw/` 下保存元数据文件

#### Scenario: 元数据失败返回结构化错误
- **WHEN** Bilibili 元数据采集失败
- **THEN** 系统返回 `ok: false` 且 `error_code: "BILIBILI_METADATA_FAILED"`

### Requirement: 字幕优先策略
系统 SHALL 优先使用 Bilibili 可用字幕生成规范 transcript。

#### Scenario: 有可用字幕时不下载音频
- **WHEN** Bilibili 视频存在可用字幕
- **THEN** 系统保存原始字幕，生成 `canonical/transcript.md`，且 MUST NOT 下载音频

#### Scenario: 字幕被规范化为 Markdown transcript
- **WHEN** 系统从字幕生成规范文本
- **THEN** `canonical/transcript.md` 是 UTF-8 Markdown 文件，并包含可供后续分类和总结使用的正文文本

### Requirement: 无字幕时音频与 Whisper fallback
系统 SHALL 在没有可用字幕时下载音频并使用本地 OpenVINO GenAI Whisper 转写。

#### Scenario: 无字幕时下载音频
- **WHEN** Bilibili 视频没有可用字幕
- **THEN** 系统将音频文件保存到 `<asset_store_path>/<source_id>/raw/`

#### Scenario: 音频被本地 Whisper 转写
- **WHEN** 音频下载成功
- **THEN** 系统调用本地 OpenVINO GenAI Whisper 转写能力并生成 transcript 文本

#### Scenario: 默认使用 Intel GPU 设备
- **WHEN** 系统调用本地 OpenVINO GenAI Whisper 转写能力
- **THEN** 默认目标设备为 `GPU` 或等价的 `GPU.0`，用于 Intel Xe 集成显卡加速

#### Scenario: 不静默回退到 CPU
- **WHEN** 目标 Intel GPU 设备不可用或 OpenVINO GPU runtime 不可用
- **THEN** 系统返回 `ok: false` 且 `error_code: "WHISPER_UNAVAILABLE"`，而不是静默使用 CPU 转写

#### Scenario: Whisper 不可用返回结构化错误
- **WHEN** OpenVINO GenAI、Whisper 模型目录、本地模型文件或转写工具缺失
- **THEN** 系统返回 `ok: false` 且 `error_code: "WHISPER_UNAVAILABLE"`

#### Scenario: Whisper 转写失败返回结构化错误
- **WHEN** 本地 Whisper 已可用但转写过程失败
- **THEN** 系统返回 `ok: false` 且 `error_code: "BILIBILI_TRANSCRIPT_FAILED"`

### Requirement: 规范 transcript 与 asset manifest
系统 SHALL 为 Bilibili transcript pipeline 产出规范文本和素材清单。

#### Scenario: transcript_ready 成功响应
- **WHEN** Bilibili transcript pipeline 成功生成 `canonical/transcript.md`
- **THEN** stdout JSON 包含 `ok: true`、`status: "transcript_ready"`、`content_type: "bilibili_video"`、`source_url`、`asset_dir`、`canonical_text_path` 和 `asset_manifest`

#### Scenario: asset_manifest 记录实际素材
- **WHEN** pipeline 使用字幕路径成功
- **THEN** `asset_manifest` 记录元数据文件、原始字幕文件和 `canonical/transcript.md`

#### Scenario: asset_manifest 记录音频和转写素材
- **WHEN** pipeline 使用 Whisper fallback 成功
- **THEN** `asset_manifest` 记录元数据文件、音频文件和 `canonical/transcript.md`

### Requirement: 受控 tool 边界
系统 SHALL 通过受控 Python tools 执行 Bilibili 下载、音频下载、Whisper 转写和规范文本写入。

#### Scenario: tools 封装副作用
- **WHEN** pipeline 需要下载、转写或写入文件
- **THEN** 它通过 `collect_bilibili_video`、`download_bilibili_audio`、`transcribe_with_whisper` 或 `write_canonical_transcript` 等受控 tools 完成

#### Scenario: skills 不直接执行副作用
- **WHEN** 阅读 `skills/bilibili-ingest/SKILL.md` 或 `skills/whisper-transcription/SKILL.md`
- **THEN** skill 文件 MUST 指示 agent 使用受控 Python tools，而不是自行执行 shell、访问网络或写入素材仓库

### Requirement: 测试替身与可选集成测试
系统 SHALL 使用测试替身验证 Bilibili transcript pipeline 的核心行为，并将真实网络和真实 Whisper 作为可选集成测试。

#### Scenario: 单元测试不依赖真实网络
- **WHEN** 单元测试运行
- **THEN** Bilibili 下载行为使用 fixture 或 fake downloader，而不是访问真实 Bilibili

#### Scenario: 单元测试不依赖真实 Whisper 模型
- **WHEN** 单元测试运行
- **THEN** Whisper 转写行为使用 fake transcriber，而不是加载真实本地模型

#### Scenario: 单元测试覆盖 GPU 设备选择
- **WHEN** 单元测试运行
- **THEN** 它验证 OpenVINO Whisper transcriber 默认请求 `GPU` 或等价的 `GPU.0`
