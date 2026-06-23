# siku 项目探索总览

更新时间：2026-06-19

## 文档定位

本文记录 siku 项目从脑暴到阶段九实现后的整体探索结果。它不是运行手册，也不是某个阶段的 OpenSpec 提案，而是项目级长期总览。

- `README.md`：面向使用和当前实现状态，说明如何配置、运行和测试。
- `docs/project-overview.md`：面向长期理解，说明项目定位、架构边界、阶段路线和现状。
- `docs/decision-log.md`：记录讨论过的问题、选项和最终决策。
- `openspec/changes/**`：记录每一阶段的具体提案、设计、任务和归档历史。
- `docs/superpowers/specs/**`：记录早期 Superpowers 脑暴设计快照。

## 项目定位

siku 是一个面向 Hermes agent 的知识导入 CLI。它接收一个 URL，自动识别内容类型，采集或转写内容，生成结构化中文总结，写入 Obsidian，并把原始素材保存在可配置的外部素材仓库中。

它不是 Codex Skill，也不是给人类交互式使用的聊天工具。Hermes 未来应把它当成一个稳定的命令行能力，通过 JSON stdin/stdout 调用。

核心调用形态：

```bash
uv run --env-file .env km ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
```

阶段九新增 agent 编排入口：

```bash
uv run --extra agent --env-file .env km agent-ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
```

当前已实现的稳定入口是 `km ingest`。`km agent-ingest` 已实现为可选 Deep Agents 编排入口，需要安装 `agent` extra。

## 核心目标

- 每次处理一个 URL，便于 Hermes 做单条任务调度、重试和错误处理。
- 输入输出使用稳定 JSON 契约，stdout 只输出一个 JSON object。
- 支持 Bilibili 视频和网页文章两个首期内容来源。
- Bilibili 优先使用字幕；没有字幕时下载音频并使用本地 Whisper 转写。
- 网页文章首期支持微信公众号专用解析和通用网页 fallback parser。
- 文本化之后自动执行领域分类、中文总结、Obsidian 写入和 SQLite processed 标记。
- 原始素材和中间产物保存在 Obsidian vault 外部的素材仓库中。
- Obsidian note 只保存总结、来源链接和素材路径引用，不嵌入完整原文或完整转写稿。
- 使用 uv 管理 Python 项目、依赖、锁文件和项目虚拟环境。
- 使用 OpenSpec 管理阶段提案，使用 Superpowers 工作流做脑暴、TDD 和 code review。

## 非目标

- 首版不支持批处理。批量调度应由 Hermes 或上层系统逐条调用 CLI。
- 首版不做写入前人工确认，默认全自动写入。
- Obsidian vault 不保存原始大素材，避免 vault 变重。
- 不让 agent 直接执行 shell、直接写 SQLite、直接写素材仓库或直接写 Obsidian。
- 不把 Bilibili 内部元数据、字幕、音频和 Whisper 步骤拆成 agent 可见的细粒度工具。
- 不做 Playwright/browser fallback、登录态网页解析、CSDN 专用 parser 或知乎专用 parser。
- 不在总结阶段做固定字符数切块和多轮汇总。首版采用单次总结。
- 不在系统中实现总结质量评分、排序、UI 或人工评测记录。评测结果由人线下查看。

## 总体架构

项目采用“稳定 CLI + 受控 Python tools + 可选 Deep Agents 编排”的架构。

当前阶段八已实施路径：

```text
Hermes 或用户
  -> km ingest
    -> 读取 stdin JSON
    -> 加载配置
    -> URL 规范化
    -> SQLite processed 去重
    -> 确定性 URL 路由
    -> Bilibili 或网页文本化
    -> 领域分类
    -> 中文总结
    -> Obsidian note 写入
    -> SQLite 标记 processed
    -> stdout 返回 processed_ready 或 skipped_existing
```

阶段九已实现的 Deep Agents 路径：

```text
Hermes
  -> km agent-ingest
    -> Deep Agents runtime
      -> AgentRuntime adapter
        -> Python 状态机 guard
          -> 受控 Python tools
            -> 下载、解析、转写、LLM、Obsidian、SQLite
```

Deep Agents 只负责决定下一步调用哪个受控 tool。所有副作用必须由 Python tools 完成。状态机 guard 是安全边界，prompt 和 skill 不是安全边界。

## Hermes、Deep Agents、Skills 和 Tools 边界

### Hermes

Hermes 只调用 CLI。

- 当前调用 `km ingest`。
- 可调用 `km agent-ingest`。
- Hermes 不直接调用项目内部 tools。
- Hermes 不读取项目内部 Deep Agents trace 或推理过程。

### Deep Agents

Deep Agents 是项目内部的编排器。

- 只在 `km agent-ingest` 内部运行。
- 读取项目内 `skills/*.md` 作为指令资产。
- 只接收 URL、状态摘要、路径、tool schema、状态机规则和错误处理规则。
- 不接收完整 transcript、完整网页正文、完整 HTML、完整 prompt、完整模型输出、API key 或 cookie。

### Skills

项目内 `skills/` 是给 Hermes/Deep Agents 使用的版本化指令资产，不是 Codex 的 `.codex/skills/`。

当前项目 skills：

```text
skills/url-routing/SKILL.md
skills/bilibili-ingest/SKILL.md
skills/web-article-ingest/SKILL.md
skills/whisper-transcription/SKILL.md
skills/domain-classification/SKILL.md
skills/summary-generation/SKILL.md
skills/obsidian-write/SKILL.md
```

每个 skill 描述“什么时候使用能力、应该遵守哪些规则”。skill 不授予副作用权限。

### Python Tools

Python tools 是真实能力边界。

阶段九中等粒度 agent tools：

```text
route_url
prepare_source_workspace
collect_bilibili_text
collect_web_article_text
classify_domain
generate_summary
write_obsidian_note
mark_source_processed
```

这个粒度刻意不再细拆 Bilibili 内部步骤，避免把下载器、字幕、音频和 Whisper 的复杂度暴露给 agent。

## 数据与产物模型

### 配置

配置默认读取 `~/.config/km/config.toml`，也可以通过 `KM_CONFIG` 指定。

关键配置：

- `vault_path`：Obsidian vault 路径，必须已存在。
- `inbox_dir`：vault 内相对路径，不能是绝对路径，不能包含 `..`。
- `asset_store_path`：外部素材仓库路径，必须位于 vault 外部。
- `[whisper]`：Whisper OpenVINO 模型目录、模型尺寸和设备。
- `[llm.models.<ref>]`：统一定义 OpenAI-compatible 模型。
- `[llm.tasks]`：按任务引用模型。
- `[summary]` 和 `[summary.evaluation]`：控制总结输入截断和双模型评测。

阶段九新增：

```toml
[llm.tasks]
agent_orchestration = "deepseek_v4_flash"
```

### 素材仓库

每个来源使用 `sha256(normalized_url).hexdigest()` 作为 `source_id`。

典型目录：

```text
<asset_store_path>/
  index.sqlite
  <source_id>/
    raw/
    canonical/
    summary/
    agent/
```

阶段九 agent 状态文件：

```text
<asset_dir>/agent/state.json
<asset_dir>/agent/trace.jsonl
```

### SQLite 索引

SQLite 是长期去重和业务状态索引。它记录来源是否已处理、note 路径、素材目录、领域、标题和最近错误。

已确认原则：

- SQLite 是权威索引，不使用单个 JSON 文件做长期索引。
- `processed` 命中时返回 `skipped_existing`。
- 阶段九 agent trace 不进入 SQLite，仍保存在素材目录下。
- 阶段九不升级 SQLite schema。

### 规范文本

Bilibili 输出：

```text
canonical/transcript.md
```

网页文章输出：

```text
canonical/content.md
```

后续领域分类和总结都只读取规范文本，不直接读取原始 HTML 或原始音频。

### 领域分类

领域分类结果：

```text
summary/domain.json
```

固定领域表：

```text
AI
编程
产品
商业
学习
心理学
投资
写作
生活
菜谱
其他
```

只允许选择一个主领域。跨领域、证据不足或低置信度归入 `其他`。

### 中文总结

权威总结：

```text
summary/summary.json
```

评测候选：

```text
summary/evaluations/<model_ref>.json
```

`summary.json` 是分析之后的结构化总结输出物。它包含标题、一句话总结、核心要点、关键概念、领域专属笔记、可行动启发、延伸问题、标签、来源、输入、prompt 和模型追溯信息。

其中 `questions` 是模型根据内容提出的后续思考问题或待追问问题，用于 Obsidian 笔记中的延伸思考，不代表系统必须自动回答这些问题。

### Obsidian note

Obsidian note 写入：

```text
<vault_path>/<inbox_dir>/YYYY-MM-DD-safe-title.md
```

原则：

- 正文只放总结、原始链接和素材路径引用。
- 不嵌入完整原文、完整 transcript、完整 HTML 或完整 prompt。
- 同 `source_id` 重试覆盖同一 note 并保留旧 `created_at`。
- 不同来源同名时使用 `-<source_id前8位>` 兜底。

## 阶段路线回顾

### 阶段一：CLI 契约骨架

目标：建立面向 Hermes 的稳定命令行协议。

产出：

- `km ingest` 命令。
- JSON stdin/stdout。
- `ok`、`status`、`error_code`、`message`、`recoverable` 等 envelope。
- 退出码约定：`0` 成功，`1` 输入或配置错误，`2` 可恢复处理失败。

### 阶段二：本地状态基础

目标：建立素材仓库、去重索引和配置边界。

产出：

- `vault_path`、`inbox_dir`、`asset_store_path`。
- `asset_store_path` 必须位于 vault 外部。
- `source_id = sha256(normalized_url)`。
- `<source_id>/raw`、`canonical`、`summary` 目录。
- SQLite `index.sqlite` 和 `sources` 表。
- 重复来源 `skipped_existing`。
- 使用 uv 管理项目和虚拟环境。

### 阶段三：URL 路由与项目 skills

目标：在本地状态之后识别内容类型，并建立项目内 skill 资产。

产出：

- 确定性 URL 路由：`bilibili_video`、`web_article`、`unsupported`。
- 不访问网络，不展开短链。
- 新增 `skills/url-routing/SKILL.md` 等项目内 skills。

### 阶段四：Bilibili 文本化

目标：打通 Bilibili 视频到规范转写文本的闭环。

产出：

- 受控 `yt-dlp` wrapper。
- Bilibili 元数据保存到 `raw/metadata.json`。
- 优先使用字幕生成 `canonical/transcript.md`。
- 无字幕时下载音频并使用本地 Whisper 转写。
- Whisper 使用 OpenVINO + Intel Xe GPU 加速。
- 模型下载或导出到当前项目配置的模型目录，不依赖其他项目路径。
- 参考了 `/home/xu/workspace/hot_pulse` 的技术思路，但不复用其模型路径。

### 阶段五：网页文章文本化

目标：打通网页文章到规范正文的闭环。

产出：

- HTTP fetch 保存 `raw/page.html`。
- 微信公众号专用 parser。
- `trafilatura` 通用 fallback parser。
- `raw/metadata.json`。
- `canonical/content.md`。

明确不做：

- Playwright/browser fallback。
- 登录态和 cookie 管理。
- CSDN、知乎等专用 parser。

### 阶段六：领域分类

目标：文本化后自动选择固定主领域，为后续 prompt 选择提供依据。

产出：

- `summary/domain.json`。
- 固定领域表，后续加入 `菜谱`。
- 只允许模型从固定领域表中选一个主领域。
- 分类 prompt 使用规范文本前 12000 个字符。
- 领域配置和模型引用统一放在 `[llm.models]` 与 `[llm.tasks]`。

### 阶段七：中文总结

目标：根据领域生成结构化中文总结。

产出：

- `summary/summary.json`。
- 按领域选择 `prompts/summary/domains/*.md`。
- 长短文本都采用单次总结。
- 默认 `summary.max_input_chars = 0`，不主动截断。
- 支持评测模式：同时调用多个候选模型，主模型写入权威 `summary.json`。
- 评测只输出候选 JSON，不做自动评分或排序。

已确认默认评测策略：

- `summary.evaluation.enabled = true`。
- 候选模型使用 `deepseek_v4_flash` 和 `deepseek_v4_pro` 这类模型引用名。
- 主输出使用 `deepseek_v4_pro`。
- 代码只使用模型引用名，不硬编码具体供应商。

### 阶段八：Obsidian 写入与 processed 状态

目标：从总结结果到 Obsidian note，再到 SQLite `processed` 状态形成闭环。

产出：

- 校验 `summary/summary.json`。
- 渲染 Obsidian Markdown。
- 写入 `<vault_path>/<inbox_dir>`。
- note 正文不嵌入完整原文。
- SQLite 标记 `status = "processed"`。
- 端到端成功返回 `processed_ready`。
- 重复导入返回 `skipped_existing`。

当前 `add-obsidian-processed-pipeline` 任务已完成，但在 2026-06-17 仍显示为未归档 active change。

### 阶段九：Deep Agents 编排

目标：新增 `km agent-ingest`，验证“skills + 受控 tools + 状态机 guard”的 agent 编排形态。

当前状态：

- `km agent-ingest` 已实现。
- `agent` optional extra 已加入 `deepagents` 和 `langchain-openai`。
- 默认自动化测试使用 `FakeAgentRuntime`，不依赖真实 Deep Agents runtime 或远程模型。
- `openspec validate add-deep-agents-ingest-orchestration` 已通过。
- `openspec validate --all` 已通过。

阶段九关键设计：

- Hermes 只调用 `km agent-ingest`。
- Deep Agents 在项目内部编排 tools。
- `km ingest` 保留为确定性基线。
- agent 路径失败不自动 fallback 到 `km ingest`。
- 新增 `agent` optional extra。
- 新增 `[llm.tasks] agent_orchestration`。
- 新增 `AgentRuntime`、`DeepAgentsRuntime` 和 `FakeAgentRuntime`。
- 新增 `agent/state.json` 和 `agent/trace.jsonl`。
- 默认复用已有合法产物。
- 网络/API/下载错误最多重试一次。
- `max_tool_steps = 12`。

## 当前实现状态

截至 2026-06-19：

已实现：

- uv 项目管理。
- `km ingest` CLI。
- 本地配置加载和校验。
- URL 规范化和 `source_id`。
- 外部素材仓库。
- SQLite 去重和 processed 状态。
- Bilibili 文本化，包括字幕优先和 Whisper fallback。
- 网页文章文本化，包括微信公众号 parser 和 `trafilatura` fallback。
- 领域分类。
- 中文总结。
- 双模型评测输出。
- Obsidian note 写入。
- 端到端 `processed_ready`。
- `km agent-ingest`。
- Deep Agents runtime 集成。
- AgentRuntime 适配层。
- agent tools。
- 状态机 guard。
- agent state/trace。
- skill loader。

## 后续演进方向

短期：

- 归档已完成的阶段八提案。
- 对 `km agent-ingest` 做更多真实 URL 手动验证。

中期：

- 增加更多内容源，例如 PDF、YouTube、播客或社交媒体。
- 针对 CSDN、知乎等高噪声网页增加专用 parser。
- 设计显式重跑能力，例如 `force` 或 `rerun_from`。
- 为 agent trace 设计更好的调试查看工具。

长期：

- 让 Hermes 通过 `km agent-ingest` 稳定调用知识导入能力。
- 将 skills 演进为跨 agent 可复用的知识导入指令资产。
- 在不破坏 CLI 契约的前提下持续扩展内容解析、总结模板和知识管理策略。
