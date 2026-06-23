# Hermes 知识导入 Skill

## 适用场景

当 Hermes 需要托管完整知识导入流程时，使用本 skill：给定一个 URL，通过项目 CLI 完成下载或解析、领域分类、中文总结、Obsidian 写入和 SQLite `processed` 标记。

本 skill 是 Hermes 的高层入口，不是内部 Deep Agents 子 skill。Hermes 不直接编排项目内部流水线工具，也不直接写素材仓库、SQLite 或 Obsidian。

## 当前调用命令

默认稳定入口是确定性 `km ingest`：

```bash
cd /home/xu/workspace/siku
uv run --env-file .env km ingest
```

需要由项目内部 Deep Agents 托管编排时，显式使用 agent 入口：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

Hermes 通过 stdin 传入单个 JSON object：

```json
{"url":"https://example.com/article","mode":"ingest"}
```

`url` 必填，`mode: "ingest"` 固定表示导入模式。本 skill 不引入批处理、dry run、force、rerun 或交互确认。

## 轻量预检查

调用 CLI 前，Hermes 应确认：

- 当前工作目录是 `/home/xu/workspace/siku`。
- 该目录下存在可用的 `.env`。
- `.env` 提供 `KM_CONFIG`。
- `DEEPSEEK_API_KEY` 已通过 `.env` 或继承环境配置。

本 skill 不重复实现完整 CLI 校验。Obsidian 路径、素材仓库路径、URL 合法性、Whisper 运行时、下载器、Deep Agents runtime 和 SQLite 错误仍由 CLI 负责，并通过结构化 stdout JSON 返回。

## 输出处理

stdout JSON 是事实来源。stderr 只用于日志和诊断，不得当成权威结果解析。

成功状态：

- `status: "processed_ready"` 表示该 URL 已完成完整导入，可以使用 `note_path` 做后续任务跟踪。
- `status: "skipped_existing"` 表示 SQLite 已有 processed 记录，Hermes 不应重复导入。

失败状态：

- 保留 CLI 返回的 `ok`、`error_code`、`message` 和 `recoverable`。
- 不得只把业务错误转换成对话式摘要。
- `recoverable: true` 表示 Hermes 可以在工作流层稍后重新排队或重试。
- `recoverable: false` 表示 Hermes 应停止并向用户报告失败。

Hermes 可以使用 `note_path`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path` 等路径做任务跟踪。默认情况下，Hermes 成功后不主动读取笔记、总结、转写稿、HTML、音频或其他生成文件内容。

`km agent-ingest` 响应还会包含 `orchestrator: "deep_agents"`、`trace_path` 和 `state_path`。这些路径用于调试和任务跟踪；Hermes 默认不主动读取完整 trace 或 state 内容。

## 重试边界

本 skill 不增加自己的重试循环。

CLI 是唯一可以对内部可恢复操作执行有限重试的层。Hermes 只能根据最终 stdout JSON 的 `recoverable: true` 在工作流层稍后重试，避免和 CLI 内部重试叠加。

## 禁止行为

Hermes 不得直接调用内部流水线工具：

- `route_url`
- `prepare_source_workspace`
- `collect_bilibili_text`
- `collect_web_article_text`
- `classify_domain`
- `generate_summary`
- `write_obsidian_note`
- `mark_source_processed`

Hermes 不得自行访问网络下载内容，不得自行调用 LLM，不得自行写入素材仓库、SQLite 或 Obsidian。

## agent 入口边界

选择 `km agent-ingest` 必须是显式决定。本 skill 不得从 `km agent-ingest` 自动回退到 `km ingest`，因为自动回退会掩盖 Deep Agents 编排失败。

无字幕 Bilibili 且需要本地 Whisper GPU 转写时，Hermes 应使用：

```bash
uv run --extra agent --extra gpu --env-file .env km agent-ingest
```
