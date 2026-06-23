# Hermes 知识导入 skill 设计

## 目标

新增一个面向 Hermes 的高层项目 skill，用于托管完整知识导入流程：接收一个 URL，调用当前稳定 CLI，并解释结构化结果，同时不向 Hermes 暴露内部流水线工具。

这个 skill 是 Hermes 的入口能力，不是内部 Deep Agents 子 skill，也不授予 Hermes 直接调用项目 Python 工具的权限。

## Skill 位置

新增 skill 文件：

```text
skills/hermes-knowledge-ingest/SKILL.md
```

这个名称刻意保留 Hermes 前缀。现有 `bilibili-ingest`、`summary-generation`、`obsidian-write` 等 skills 描述的是内部流水线能力；`hermes-knowledge-ingest` 描述 Hermes 应该调用的单一完整工作流。

## 当前调用契约

该 skill 保留当前稳定的确定性 CLI：

```bash
cd /home/xu/workspace/siku
uv run --env-file .env km ingest
```

阶段九实现后，也可以显式选择 Deep Agents 编排入口：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

Hermes 通过 stdin 传入且只传入一个 JSON object：

```json
{"url":"https://example.com/article","mode":"ingest"}
```

`url` 必填。`mode` 应为 `ingest`。这个 skill 不引入批处理、dry run、force、rerun 或交互确认。

## 轻量预检查

调用 CLI 前，skill 应指导 Hermes 确认本地执行上下文已经就绪：

- 当前工作目录是 `/home/xu/workspace/siku`。
- 该目录下存在可用的 `.env`。
- `.env` 提供 `KM_CONFIG`。
- `DEEPSEEK_API_KEY` 已通过 `.env` 或继承环境配置。

skill 不重复实现完整 CLI 校验。Obsidian 路径、素材仓库路径、模型引用、URL 合法性、下载器行为、Whisper 运行时、Deep Agents runtime 和 SQLite 错误仍由 CLI 负责，并通过 CLI 的结构化 JSON 响应封装返回。

## 重试策略

skill 不增加自己的重试循环。

CLI 是唯一可以对内部可恢复操作执行有限重试的层。如果 CLI 返回失败 JSON，skill 应把该结果交还 Hermes，并说明决策规则：

- `recoverable: true`：Hermes 可以在工作流层稍后重新排队或重试。
- `recoverable: false`：Hermes 应停止并向用户报告失败。

这样可以避免 Hermes 和 CLI 运行器之间发生双重重试。

## 输出处理

CLI stdout JSON 是事实来源。skill 不应改写事实字段，也不应隐藏路径字段。

成功响应的解释规则：

- `status: "processed_ready"` 表示该知识条目已经完成下载或解析、中文总结、Obsidian 写入和 processed 标记。
- `status: "skipped_existing"` 表示 SQLite 已经存在该规范化 URL 的 processed 记录，Hermes 不应重复导入。

失败响应的处理规则：

- 保留 `ok`、`error_code`、`message` 和 `recoverable`。
- 不得只把业务错误转换成对话式摘要。
- 不得把 stderr 当成权威结果解析。

Hermes 可以使用返回的 `note_path`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path` 等路径做任务跟踪。默认情况下，Hermes 成功后不主动读取笔记、总结、转写稿、HTML、音频或其他生成文件内容。如果后续工作流需要读取文件内容，应设计为独立的显式能力。

`km agent-ingest` 会额外返回 `orchestrator: "deep_agents"`、`trace_path` 和 `state_path`。`state.json` 是最新 agent 状态快照，`trace.jsonl` 是 append-only 运行事件；trace 只记录编排元数据和受控 tool 结果，不记录完整正文、完整 transcript、完整 HTML、完整 prompt、完整模型输出、API key、cookie 或环境变量值。

## 边界规则

Hermes 不得直接调用内部流水线工具：

- `route_url`
- `prepare_source_workspace`
- `collect_bilibili_text`
- `collect_web_article_text`
- `classify_domain`
- `generate_summary`
- `write_obsidian_note`
- `mark_source_processed`

Hermes 应把 CLI 视为稳定公开边界。Hermes 不应自行写素材仓库、SQLite、Obsidian vault 或项目 skill 文件。

skill 还应提醒 Hermes：stdout 必须只包含一个 JSON object，日志和诊断信息属于 stderr。

## agent 编排边界

选择 Deep Agents 编排入口时，命令为：

```bash
cd /home/xu/workspace/siku
uv run --extra agent --env-file .env km agent-ingest
```

这个未来变更必须显式完成。skill 不应从 `km agent-ingest` 自动回退到 `km ingest`，因为自动回退会掩盖 Deep Agents 编排失败。

Hermes 可见的输入契约和输出决策规则保持一致。Deep Agents 只在 `km agent-ingest` 内部选择下一步受控 tool；Python 状态机 guard 强制合法转换。已有规范文本、`summary/domain.json` 和 `summary/summary.json` 合法时，受控 tools 会复用产物并返回 `skipped: true`。

## 测试与审查

实现时应新增或更新测试，验证：

- `skills/hermes-knowledge-ingest/SKILL.md` 存在。
- skill 将 `uv run --env-file .env km ingest` 记录为当前命令。
- skill 记录轻量预检查要求。
- skill 禁止 Hermes 直接调用内部工具。
- skill 声明自己不执行额外重试。
- skill 记录未来切换到 `km agent-ingest`，且不允许自动回退。

人工审查应确认：这个 skill 没有暗示 Hermes 可以读取完整来源内容、写项目状态，或绕过 CLI JSON 契约。
