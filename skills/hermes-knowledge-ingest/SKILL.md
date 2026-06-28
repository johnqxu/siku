---
name: hermes-knowledge-ingest
description: Use when the user asks to 加入到知识库, 保存到知识库, 整理到知识库, or import a URL/link into the Obsidian knowledge base through siku.
---

# Hermes 知识导入 Skill

## 适用场景

当 Hermes 需要托管完整知识导入流程时，使用本 skill：给定一个 URL，通过项目 CLI 完成下载或解析、领域分类、中文总结、Obsidian 写入和 SQLite `processed` 标记。

必须触发本 skill 的常见表达：

- “加入到知识库【标题】 https://...”
- “保存到知识库 https://...”
- “整理到知识库 https://...”
- “把这个链接入库 https://...”
- “把这个网页/视频存到 Obsidian https://...”

例如用户说“加入到知识库【厨房小白也会做的西餐❗️超浓郁匈牙利炖鸡-哔哩哔哩】 https://b23.tv/wPRipfZ”时，必须调用 `km agent-ingest`，不能用通用网页提取或 Hermes memory 代替。

本 skill 是 Hermes 的高层入口，不是内部 Deep Agents 子 skill。Hermes 不直接编排项目内部流水线工具，也不直接写素材仓库、SQLite 或 Obsidian。

当前默认通过项目内 Deep Agents 编排受控 Python tools 完成全流程。

## 当前调用命令

唯一公开导入入口是 `km agent-ingest`，由项目内 Deep Agents 编排受控 Python tools：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

无字幕 Bilibili 且需要本地 Whisper GPU 转写时，同时启用 `agent` 和 `gpu`：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --extra gpu --env-file .env km agent-ingest
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
- 如需调用 `km agent-ingest`，配置必须包含 `[llm.tasks] agent_orchestration` 模型引用。
- 如需调用 `km agent-ingest`，确认已安装 `agent` extra：`uv sync --extra agent`。
- 如需调用 `km agent-ingest` 且处理无字幕 Bilibili 视频，同时安装 `gpu` extra：`uv sync --extra agent --extra gpu`。

本 skill 不重复实现完整 CLI 校验。Obsidian 路径、素材仓库路径、URL 合法性、Whisper 运行时、下载器、Deep Agents runtime 和 SQLite 错误仍由 CLI 负责，并通过结构化 stdout JSON 返回。

## 输出处理

stdout JSON 是事实来源。stderr 只用于日志和诊断，不得当成权威结果解析。

成功状态：

- `ok: true` 且 `status: "processed_ready"` 表示该 URL 已完成完整导入，可以使用 `note_path` 做后续任务跟踪。
- `ok: true` 且 `status: "skipped_existing"` 表示 SQLite 已有 processed 记录，Hermes 不应重复导入。

只有上述 CLI stdout JSON 才能作为“已加入知识库”的依据。没有 `km agent-ingest` stdout JSON，或者 stdout JSON 不是上述成功状态时，不得回复“已加入知识库”。

失败状态：

- 保留 CLI 返回的 `ok`、`error_code`、`message` 和 `recoverable`。
- 不得只把业务错误转换成对话式摘要。
- `recoverable: true` 表示 Hermes 可以在工作流层稍后重新排队或重试。
- `recoverable: false` 表示 Hermes 应停止并向用户报告失败。

Hermes 可以使用 `note_path`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path` 等路径做任务跟踪。默认情况下，Hermes 成功后不主动读取笔记、总结、转写稿、HTML、音频或其他生成文件内容。

`km agent-ingest` 响应还会包含 `orchestrator: "deep_agents"`、`trace_path` 和 `state_path`。这些路径用于调试和任务跟踪；Hermes 默认不主动读取完整 trace 或 state 内容。

## 防止伪成功

Hermes memory 不是 Obsidian 知识库。处理“加入到知识库”“保存到知识库”“整理到知识库”这类 URL 导入请求时：

- 必须调用 `km agent-ingest`。
- 不得用 `web_extract` 抓取网页后自行总结作为导入结果。
- 不得用 `memory` 记录一段摘要后声称已经完成知识库导入。
- 不得用 Obsidian 通用 skill 绕过本项目 CLI。
- 不得因为 `web_extract`、`memory` 或普通对话成功，就回复“已加入知识库”。

如果没有调用 CLI，应该明确说明尚未导入 Obsidian，并继续通过本 skill 调用 CLI；如果 CLI 失败，原样保留结构化错误并说明未写入 Obsidian。

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

`km agent-ingest` 是唯一公开导入入口。确定性文本化、产物复用、内部重试和状态机 guard 都由该入口内部的受控 Python tools 承担。

本 skill 不得自动回退到其他入口或自行调用内部 tools，因为自动回退会掩盖 Deep Agents 编排失败。

使用 `km agent-ingest` 时，如果配置缺少 `agent` extra 或 `agent_orchestration` 模型引用，CLI 会返回对应公开错误。
