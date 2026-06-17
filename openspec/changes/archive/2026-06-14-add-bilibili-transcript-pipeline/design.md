## Context

当前系统已经完成 CLI 契约、本地状态层和 URL 路由。Bilibili 视频 URL 会被路由为 `bilibili_video`，但仍返回 `NOT_IMPLEMENTED`。后续领域分类、总结和 Obsidian 写入都依赖一个稳定的规范文本输入，因此阶段四需要先把 Bilibili 视频转成 `canonical/transcript.md`。

用户明确要求第四阶段是完整的 Bilibili 数据下载处理闭环：先下载元数据和字幕；没有字幕时下载音频；再用本地 Whisper 转写；最终输出视频对应的文本。本阶段仍不接入 Deep Agents 运行时，Deep Agents 放到端到端编排阶段；但本阶段会完善 `bilibili-ingest` 和新增 `whisper-transcription` skill 文件，作为未来编排的指令资产。

## Goals / Non-Goals

**Goals:**

- 对 `bilibili_video` URL 执行完整文本化流程。
- 保存 Bilibili 元数据、原始字幕或音频、规范 transcript 和 asset manifest。
- 优先使用字幕；只有没有可用字幕时才下载音频并调用本地 OpenVINO GenAI Whisper。
- 通过 typed Python tools 封装 Bilibili 下载和 Whisper 转写，不让 agent 自行执行 shell 或写文件。
- 成功时返回 `transcript_ready` 阶段性成功响应。
- 失败时返回稳定错误 envelope 和明确错误码。
- 单元测试使用 fixture/fake downloader/fake transcriber，不依赖真实网络、真实 OpenVINO GPU runtime 或真实 Whisper 模型。

**Non-Goals:**

- 不实现网页文章采集。
- 不做领域分类、中文总结或 LLM 调用。
- 不写 Obsidian 笔记。
- 不将来源记录写入 SQLite `processed`；真正处理完成留到 Obsidian 阶段。
- 不接入 LangChain Deep Agents 运行时。
- 不要求单元测试访问真实 Bilibili、加载真实 Whisper 模型或访问真实 Intel GPU。

## Decisions

1. 阶段四以 Bilibili 到文本闭环为一个 OpenSpec change。

   字幕路径和无字幕 Whisper fallback 是同一个业务承诺：给定 Bilibili 视频，尽最大可能产出可总结文本。把音频下载和 Whisper 拆到后续阶段会让阶段四成功条件不完整，后续阶段无法稳定依赖它。

2. 先字幕，后音频，避免不必要的大文件下载。

   如果 Bilibili 提供可用字幕，本阶段直接保存原始字幕并清洗成规范 transcript，不下载音频。只有没有字幕或字幕不可用时，才下载音频并转写。这符合用户原始策略，也降低执行时间和素材体积。

3. 下载器和转写器都通过可替换接口封装。

   实现上应定义 downloader/transcriber 边界，例如 `BilibiliDownloader` 和 `WhisperTranscriber` 协议或等价 wrapper。CLI 使用真实实现，单元测试注入 fake。这样可以测试 pipeline 逻辑，不依赖真实网络、Bilibili 登录状态、ffmpeg 或本地模型。

4. Bilibili 下载工具优先封装成熟工具，而不是手写站点协议。

   Bilibili 页面结构、字幕接口和音频地址都可能变化。阶段四应通过受控 Python wrapper 使用成熟下载能力，并把输出规范化为项目内部模型。替代方案是直接解析 Bilibili API，但维护成本高，且容易把站点细节扩散到 pipeline。

5. Whisper 作为本地 OpenVINO GenAI 能力，不走远程 API。

   这符合已确认的混合模式：音频转写走本地 Whisper，其他 AI 能力后续走远程 API。阶段四首选 `openvino-genai` 的 `WhisperPipeline`，目标设备默认设为 `GPU`。在 OpenVINO 设备命名中，Intel 集成显卡通常是 `GPU.0`，`GPU` 是 `GPU.0` 的别名，因此该默认值表达“使用 Intel Xe 集成显卡加速”。替代方案是 `openai-whisper` 或 `faster-whisper`，但它们不能自然表达 Intel Xe iGPU 加速目标，且会把后续优化路径带向 CUDA 或 CPU。

6. 不做静默 CPU fallback。

   用户明确希望使用 Intel Xe 集成显卡本地加速。如果 OpenVINO GenAI、Intel GPU runtime、目标设备或模型目录不可用，系统应返回 `WHISPER_UNAVAILABLE`，而不是悄悄改用 CPU 跑完。CPU fallback 可以作为未来显式配置项，但不应是阶段四默认行为。

7. 成功响应使用 `transcript_ready`，而不是 `created`。

   本阶段只创建规范文本和素材，不做总结、不写 Obsidian、不记录 `processed`。`created` 容易被误解为完整知识笔记已完成，因此使用阶段性状态更准确。

8. `source_id` 和素材目录继续来自阶段二 `normalized_url`。

   即使 Bilibili 短链未来被展开，本阶段不改变阶段二权威目录策略。若下载器能解析 canonical page URL，可写入元数据文件，但不改变本次请求的素材目录。

## Risks / Trade-offs

- Bilibili 下载可能受登录、风控或站点变化影响 -> 下载器错误统一映射为 `BILIBILI_METADATA_FAILED` 或 `BILIBILI_TRANSCRIPT_FAILED`，测试使用 fake 保证核心 pipeline 可验证。
- OpenVINO GenAI、Intel GPU runtime、模型目录或驱动可能不可用 -> 单元测试使用 fake transcriber；运行时显式检查失败并映射为 `WHISPER_UNAVAILABLE`，不静默退回 CPU。
- Whisper 模型耗时且依赖本地环境 -> 真实 OpenVINO Whisper 作为可选集成验证，常规单元测试不加载模型。
- 音频文件可能较大 -> 只在无字幕时下载音频，保存到 `raw/`，并在 manifest 中显式记录。
- 字幕格式多样 -> pipeline 统一输出 UTF-8 Markdown transcript；原始字幕保存在 `raw/`，清洗逻辑通过 fixture 覆盖。
- 阶段性成功不写 SQLite 记录可能导致重复执行重新下载 -> 这是阶段边界取舍；完整去重写入将在 Obsidian 端到端阶段处理。

## Migration Plan

无需数据迁移。阶段四复用现有素材目录结构：

```text
<asset_store_path>/<source_id>/
  raw/
  canonical/
  summary/
```

新增文件由 pipeline 在来源目录内创建。失败时允许保留已下载的部分原始素材，便于排查；CLI 仍通过结构化错误返回失败。回滚方式是移除 Bilibili pipeline 集成，让 `bilibili_video` 分支恢复为 `NOT_IMPLEMENTED`。

## Open Questions

- 真实下载器的具体实现选型在实现前还需要确认：优先候选是封装 `yt-dlp` Python API 或受控 subprocess wrapper。
- 暂无。Whisper 后端已收敛为 OpenVINO GenAI + Intel GPU；实现时仍需确认具体模型目录准备方式和依赖安装方式。
