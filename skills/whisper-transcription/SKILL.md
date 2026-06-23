# Whisper 转写 Skill

## 适用场景

当 Bilibili 视频没有可用字幕，且 `collect_bilibili_text` 已经在受控 Python tool 内部下载音频后，使用本 skill 指导本地 Whisper 转写流程。Whisper 不作为 Hermes 或 Deep Agents 直接调用能力暴露。

## 受控工具

必须通过受控 Python tools 调用 `transcribe_with_whisper(audio_path)` 或等价封装。阶段四默认后端是 OpenVINO + optimum-intel `OVModelForSpeechSeq2Seq`，目标设备为 `GPU` 或等价的 `GPU.0`，用于 Intel Xe 集成显卡加速。模型必须导出/缓存到当前项目配置的 `whisper.model_dir/<model_size>/`，不得复用其他项目的模型目录。

## 工作边界

- 不得自行执行 shell。
- 不得自行访问网络。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 不得静默回退到 CPU；Intel GPU、OpenVINO/optimum-intel、模型目录或 runtime 不可用时，应返回 `WHISPER_UNAVAILABLE`。
- 转写结果只交给 Bilibili 受控 pipeline 写入 `canonical/transcript.md`。
- 不做远程转写，不由 agent 直接调用 Whisper。
