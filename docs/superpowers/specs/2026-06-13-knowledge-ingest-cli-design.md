# 知识导入 CLI 设计

## 目标

构建一个面向 Hermes agent 的 Python 命令行知识导入工具。Hermes 通过 stdin 传入一个 URL 的 JSON 请求；工具识别内容类型，采集或转写内容，将其总结成中文知识笔记，把原始素材保存到可配置的文件系统素材仓库，将总结笔记写入 Obsidian，并通过 stdout 返回机器可读 JSON。

这个工具需要适合 agent 调用：输入输出 schema 稳定，文件系统行为确定，错误结构化，stdout 不输出对话式文本。

## 范围

首版支持：

- 每次调用处理一个 URL。
- 网页文章和可读网页文档。
- Bilibili 视频 URL。
- Bilibili 转文字策略：优先使用已有字幕；如果没有字幕，则下载音频并用本地 Whisper 转写。
- 摘要、标题、标签和领域判断说明始终使用中文。
- 自动写入 Obsidian。
- 原始素材保存在 Obsidian vault 外部，路径可配置。
- 使用 SQLite 做去重和长期元数据索引。
- 使用 LangChain Deep Agents 作为受边界约束的编排层。

未来版本可以增加 YouTube、PDF、播客、社交媒体、批量导入、dry run 和更丰富的重试流程。

## 非目标

- 首版不做批处理。
- 写入笔记前不做人类确认。
- Obsidian 笔记正文不嵌入完整原文或完整转写稿。
- 首版不做 Git 形式的素材仓库。
- agent 不能自由执行 shell。
- Hermes 不直接看到内部 Deep Agent 推理过程。

## 脑暴形成的设计决策

这个工具是给 Hermes agent 使用的 CLI，不是 Codex Skill。Hermes 应该把它当成一个稳定的命令行能力，通过 JSON stdin/stdout 交互，而不是把它当成一个对话式助手。

主接口采用 JSON stdin/stdout，而不是 shell flags，因为 Hermes 需要稳定解析、结构化错误和紧凑的调用契约。未来可以增加给人类使用的 shell flags 包装，但它不是权威 agent 接口。

首版每次只处理一个 URL。批量导入交给 Hermes 编排，这样重试、局部失败和进度都能按单个来源推理。

架构采用 AI-native bounded pipeline，而不是纯确定性流水线或纯自主 agent：

- 纯确定性流水线更容易测试，但在内容处理策略、领域分类和笔记模板选择上不够灵活。
- 纯自主 agent 更灵活，但对文件写入、原始素材保存、去重和 Hermes 稳定集成来说风险太高。
- 选定方案让 Deep Agents 负责规划和选择 skills，让 Python tools 负责所有副作用。

LangChain Deep Agents skills 作为可复用的指令包使用。每个 skill 都要配套受控 tool，因为 skill 本身不应该下载文件、修改 SQLite、调用 Whisper 或写 Obsidian 笔记。每项能力表示为：

```text
skill = 什么时候以及如何使用能力
tool = 能力的 typed Python 实现
```

原始素材保存在 Obsidian vault 外部，避免 vault 变重。Obsidian 笔记只包含来源链接和本地素材引用，不包含完整原始内容。素材仓库路径可配置，用户可以把大文件放在合适的磁盘上。

SQLite 是权威索引，而不是 JSON 索引。JSON 对小原型可以接受，但知识库变大后会变脆弱，因为每次查找和写入都要读写整个文件。SQLite 提供索引查找、事务写入、失败记录，并为未来查询留出空间。

阶段二已确定本地状态基础：`vault_path`、`inbox_dir` 和 `asset_store_path` 是必填配置；`inbox_dir` 必须是 vault 内相对路径，不能是绝对路径或包含 `..`；`asset_store_path` 必须位于 Obsidian vault 外部。CLI 会在合法请求中规范化 URL，使用完整 `sha256(normalized_url).hexdigest()` 作为 `source_id`，初始化 `<asset_store_path>/index.sqlite` 和 `<source_id>/raw`、`canonical`、`summary` 目录。SQLite 初始 schema 使用 `PRAGMA user_version = 1`，重复来源命中时返回 `skipped_existing`，其 `source_url` 来自已处理记录的 `original_url`。

阶段三已确定最小 URL 路由层：CLI 在本地状态初始化和重复来源查询之后调用 `route_url(normalized_url)`，把来源分类为 `bilibili_video`、`web_article` 或 `unsupported`。该 router 只使用标准库解析 URL，不访问网络、不下载内容、不展开 `b23.tv` 短链。Bilibili `/video/<id>` 和 `b23.tv/<id>` 路由为 `bilibili_video`，非 Bilibili 的普通 `http/https` URL 路由为 `web_article`，Bilibili 非视频路径和空 `b23.tv` 路径返回 `UNSUPPORTED_URL`。阶段三仍不实现 collector、Deep Agents 运行时、Whisper、LLM 或 Obsidian 写入。

阶段四已确定 Bilibili 视频到规范文本闭环：`bilibili_video` 新来源不再停在 `NOT_IMPLEMENTED`，而是通过受控 `yt-dlp` wrapper 获取元数据并优先使用字幕生成 `canonical/transcript.md`；没有字幕时下载音频到 `raw/`，再通过 OpenVINO GenAI Whisper 在 Intel Xe 集成显卡上本地转写。OpenVINO 目标设备默认是 `GPU`，可显式配置为 `GPU.0`；阶段四不静默回退到 CPU，相关 runtime、模型目录或 GPU 不可用时返回 `WHISPER_UNAVAILABLE`。成功响应使用 `status: "transcript_ready"`，只表示规范文本已生成，不表示总结、Obsidian 写入或 SQLite `processed` 记录已完成。

阶段五已确定网页文章到规范正文闭环：`web_article` 新来源不再停在 `NOT_IMPLEMENTED`，而是通过受控 HTTP fetcher 抓取 HTML，保存 `raw/page.html`，再根据来源选择 parser。`mp.weixin.qq.com` 使用微信公众号专用 parser，其他普通网页使用基于 `trafilatura` 的通用 fallback parser；元数据写入 `raw/metadata.json`，规范正文写入 `canonical/content.md`。阶段五依赖 `httpx`、`trafilatura` 和 `beautifulsoup4`，但不实现 Playwright/browser fallback、登录态/cookie 管理、CSDN 专用 parser 或知乎专用 parser。成功响应使用 `status: "content_ready"`，只表示规范正文已生成，不表示总结、Obsidian 写入或 SQLite `processed` 记录已完成。

阶段六已确定文本化后的领域分类闭环：Bilibili 和网页文章在生成规范文本后，由当前 Python 确定性 pipeline 自动继续执行领域分类。分类只允许从固定领域表中选择一个单一主领域，低置信度、跨领域或证据不足归入 `其他`。分类 prompt 只使用规范文本前 12000 个字符，超长文本会在 prompt 中说明已截断。分类结果写入 `summary/domain.json`，不生成 `summary/domain.md`。

阶段七已确定中文总结闭环：领域分类成功后继续执行单次中文总结。总结读取规范文本和 `summary/domain.json`，按固定领域表选择 `prompts/summary/common.md` 和 `prompts/summary/domains/*.md`，要求模型输出纯 JSON object，校验后写入 `summary/summary.json`。默认 `[summary].max_input_chars = 0` 表示不主动截断；显式配置正整数时按字符数截断并记录。评测模式由 `[summary.evaluation]` 配置驱动，推荐同时调用 `deepseek_v4_flash` 和 `deepseek_v4_pro`，以 `deepseek_v4_pro` 作为主输出；代码只使用模型引用名，不硬编码 DeepSeek。评测候选写入 `summary/evaluations/<model_ref>.json`，不做评分、排序、manifest、UI 或人工选择记录。`summary_ready` 仅保留为内部阶段结果，CLI 端到端成功路径会继续进入阶段八。

阶段八已确定 Obsidian processed 闭环：中文总结成功后读取并校验 `summary/summary.json`，用确定性 Python renderer 写入 Obsidian Markdown note，再把 SQLite `sources` 标记为 `processed`，最终 stdout 返回 `status: "processed_ready"`。note 写入 `<vault_path>/<inbox_dir>/YYYY-MM-DD-safe-title.md`；同 `source_id` 重试会覆盖同一路径并保留 `created_at`，不同来源同名时使用 `-<source_id前8位>` 兜底。Obsidian 正文只包含总结、原始链接和素材路径引用，不嵌入完整原文、完整 transcript、原始 HTML 或完整 prompt。阶段八仍不接入 LangChain Deep Agents 运行时；Deep Agents 只通过项目内 `skills/obsidian-write/SKILL.md` 预留未来编排入口。

固定领域分类表刻意保持小而稳定。稳定分类比完全自由分类更有利于标签一致性和提示词选择。首版加入 `菜谱`，因为菜谱是一类独立的长期知识，需要不同的总结字段。

项目使用 `uv` 进行 Python 项目管理、依赖解析、锁文件管理和虚拟环境管理。`pyproject.toml` 是项目元数据、依赖声明、`km` console script 和 `uv_build` 构建配置入口，`uv.lock` 固定依赖解析结果，`.python-version` 固定本地开发默认 Python 为 `3.11`。开发者通过 `uv sync` 创建或同步 `.venv/` 项目虚拟环境，通过 `uv run ...` 在该环境中运行测试和 CLI；`.venv/` 不进入版本控制。

## CLI 契约

主命令：

```bash
km ingest
```

Hermes 通过 stdin 传入 JSON：

```json
{
  "url": "https://www.bilibili.com/video/BV...",
  "mode": "ingest"
}
```

`url` 必填，且去除首尾空白后不能为空。`mode` 默认是 `ingest`，为未来模式保留。

配置从本地配置文件读取，不放在调用 payload 中：

```toml
vault_path = "/Users/xu/Obsidian"
inbox_dir = "Inbox/Knowledge"
asset_store_path = "/Users/xu/KnowledgeAssets"

[llm.models.deepseek_v4_flash]
provider = "openai_compatible"
base_url = "https://api.deepseek.com/v1"
model = "deepseek-v4-flash"
api_key_env = "DEEPSEEK_API_KEY"
timeout_seconds = 120
max_output_tokens = 8192

[llm.models.deepseek_v4_pro]
provider = "openai_compatible"
base_url = "https://api.deepseek.com/v1"
model = "deepseek-v4-pro"
api_key_env = "DEEPSEEK_API_KEY"
timeout_seconds = 120
max_output_tokens = 8192

[llm.tasks]
domain_classification = "deepseek_v4_flash"
summary_generation = "deepseek_v4_pro"

[summary]
max_input_chars = 0

[summary.evaluation]
enabled = true
candidate_models = ["deepseek_v4_flash", "deepseek_v4_pro"]
primary_model = "deepseek_v4_pro"

[whisper]
model_dir = "/Users/xu/models/whisper-openvino"
device = "GPU"
```

stdout 永远只包含一个 JSON 对象。日志写入 stderr。

成功示例：

```json
{
  "ok": true,
  "status": "processed_ready",
  "content_type": "bilibili_video",
  "source_url": "https://www.bilibili.com/video/BV...",
  "asset_dir": "/Users/xu/KnowledgeAssets/8f3a91c2b7",
  "canonical_text_path": "/Users/xu/KnowledgeAssets/8f3a91c2b7/canonical/transcript.md",
  "domain_path": "/Users/xu/KnowledgeAssets/8f3a91c2b7/summary/domain.json",
  "summary_path": "/Users/xu/KnowledgeAssets/8f3a91c2b7/summary/summary.json",
  "note_path": "/Users/xu/Obsidian/Inbox/Knowledge/2026-06-15-Agent-工具调用的设计边界.md",
  "domain": "AI",
  "title": "Agent 工具调用的设计边界"
}
```

重复导入示例：

```json
{
  "ok": true,
  "status": "skipped_existing",
  "note_path": "/Users/xu/Obsidian/Inbox/Knowledge/2026-06-13-agent-tool-calling.md",
  "asset_dir": "/Users/xu/KnowledgeAssets/8f3a91c2b7",
  "source_url": "https://www.bilibili.com/video/BV..."
}
```

失败示例：

```json
{
  "ok": false,
  "error_code": "BILIBILI_TRANSCRIPT_FAILED",
  "message": "Bilibili 视频没有可用字幕，且本地 Whisper 转写失败。",
  "recoverable": true
}
```

退出码：

- `0`：成功，包括跳过重复来源。
- `1`：输入无效、配置无效或不可恢复的协议错误。
- `2`：可恢复的处理失败。

## 架构

长期架构会使用 LangChain Deep Agents 作为受边界约束的编排层，底层由确定性的 Python tools 支撑。当前已实施阶段仍由 `km ingest` 的 Python 源代码按固定顺序编排，Deep Agents 运行时尚未接入。

当前阶段八流程：

```text
读取 stdin JSON
-> 加载配置
-> 规范化 URL
-> 查询 SQLite 去重索引
-> 确定性 URL 路由
-> 执行 Bilibili 或网页文章文本化 tool
-> 执行领域分类 tool
-> 执行中文总结 tool
-> 写入 Obsidian note
-> 写入 SQLite processed 状态
-> 返回 processed_ready
```

未来 Deep Agents 端到端编排流程：

```text
读取 stdin JSON
-> 加载配置
-> 规范化 URL
-> 查询 SQLite 去重索引
-> 创建 Knowledge Deep Agent
-> agent 选择 skills 并调用受控 tools
-> 校验最终结果 schema
-> 通过 stdout 返回 JSON
```

AI 负责判断和编排。Python tools 负责下载、转写、写文件、更新索引等副作用和不可随意执行的动作。

未来接入后，Hermes 不观察内部 Deep Agent 过程。CLI 负责把 agent 决策、tool 结果和内部异常转换成最终 stdout JSON schema。这样即使内部 skills 或 tools 演进，外部契约也能保持稳定。

CLI 应该优先在调用 Deep Agent 前完成简单且廉价的确定性检查，例如 JSON schema 校验、配置校验、URL 规范化和重复查询。Deep Agent 未来用于需要判断的地方：模糊路由、领域分类和选择合适的知识模板。

## Deep Agent Skills

每个 skill 是一个规则包，用来指导 agent。Skills 不直接产生副作用。

```text
skills/
  url-routing/
    SKILL.md
  bilibili-ingest/
    SKILL.md
  web-article-ingest/
    SKILL.md
  domain-classification/
    SKILL.md
  summary-generation/
    SKILL.md
  knowledge-note/
    SKILL.md
  obsidian-write/
    SKILL.md
```

`url-routing` 说明如何识别网页文章和 Bilibili 视频，并为未来 PDF、播客、YouTube 和社交媒体路由留出空间。

`bilibili-ingest` 定义字幕优先流程、本地 Whisper fallback 和必需素材输出。

`web-article-ingest` 定义原始 HTML 保存、可读正文抽取、元数据捕获和规范文本输出。

`domain-classification` 定义固定领域分类表：

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

`summary-generation` 定义中文结构化总结规则、单次总结策略、评测模式和 `summary/summary.json` schema 边界。

`knowledge-note` 定义中文知识卡片格式：一句话摘要、核心观点、关键概念、领域笔记、可操作启发和追问问题。

`obsidian-write` 定义 frontmatter、Inbox 位置、来源引用、素材引用和文件命名规则。

Skills 是项目内可版本化资产。未来实现应该让它们以文件形式可读、可测试，而不是把大段提示词硬编码进 Python 函数。

项目内 `skills/` 与研发环境的 `.codex/skills/` 分离。`skills/` 面向未来 Hermes/Deep Agents 运行时；`.codex/skills/` 只服务当前研发助手。项目内 skill 只能指导 agent 调用受控 Python tools，不得自行写入素材仓库、SQLite 或 Obsidian。

## 受控 Tools

Tools 是暴露给 Deep Agent 的 typed Python 函数。

```text
normalize_url(url) -> NormalizedUrl
check_duplicate(normalized_url) -> DuplicateResult
collect_web_article(url, asset_dir) -> CollectedContent
collect_bilibili_video(url, asset_dir) -> CollectedContent
transcribe_with_whisper(audio_path) -> Transcript
classify_domain(text, taxonomy) -> DomainResult
generate_summary(canonical_text_path, domain_path, model_refs) -> SummaryResult
write_assets(asset_dir, files) -> AssetManifest
write_obsidian_note(note) -> NoteWriteResult
record_ingest_index(record) -> IndexResult
```

agent 不能自由写文件、执行 shell 或修改索引，必须通过这些 tools 完成。

## 规范内容模型

采集器返回稳定的中间表示：

```json
{
  "content_type": "bilibili_video",
  "title": "Original title",
  "author": "Author or uploader",
  "published_at": null,
  "source_url": "https://www.bilibili.com/video/BV...",
  "canonical_text_path": "/Users/xu/KnowledgeAssets/8f3a91c2b7/canonical/transcript.md",
  "canonical_text": "Text used for classification and summarization",
  "asset_manifest": {
    "metadata": "/Users/xu/KnowledgeAssets/8f3a91c2b7/source.json",
    "audio": "/Users/xu/KnowledgeAssets/8f3a91c2b7/raw/audio.m4a",
    "subtitle_or_transcript": "/Users/xu/KnowledgeAssets/8f3a91c2b7/canonical/transcript.md"
  }
}
```

后续领域分类、总结、笔记渲染和索引都依赖这个模型，而不是依赖不同来源的细节。

规范文本是唯一传给分类和总结的文本。原始 HTML、原始字幕和原始音频会被保存用于追溯，但不直接交给笔记渲染器。

## Bilibili 工作流

长期完整工作流：

```text
url-routing skill 识别为 Bilibili
-> bilibili-ingest skill 指导计划
-> collect_bilibili_video 获取元数据和字幕
-> 如果存在字幕，清洗为规范转写稿
-> 如果不存在字幕，下载音频并调用 transcribe_with_whisper
-> 保存元数据和规范转写稿
-> 分类领域
-> 总结内容
-> 写入 Obsidian 笔记
-> 记录 SQLite 索引
```

如果存在字幕，首版默认不下载音频。如果没有字幕，音频会作为原始素材保存，因为它是转写稿的来源材料。

当前阶段八已经执行到“写入 Obsidian 笔记”和“记录 SQLite processed 状态”，随后返回 `processed_ready`。

## 网页文章工作流

长期完整工作流：

```text
url-routing skill 识别为网页文章
-> web-article-ingest skill 指导计划
-> collect_web_article 保存原始 HTML
-> 抽取标题、作者、发布日期和可读正文
-> 保存规范 Markdown 内容
-> 分类领域
-> 总结内容
-> 写入 Obsidian 笔记
-> 记录 SQLite 索引
```

当前阶段八已经执行到“写入 Obsidian 笔记”和“记录 SQLite processed 状态”，随后返回 `processed_ready`。

## 素材仓库

素材仓库是 Obsidian vault 外部的可配置目录：

```text
KnowledgeAssets/
  index.sqlite
  8f3a91c2b7/
    source.json
    raw/
    canonical/
    summary/
```

来源目录名来自 `sha256(normalized_url)`，即使标题变化也保持稳定。

网页文章素材：

```text
raw/page.html
raw/metadata.json
canonical/content.md
summary/domain.json
summary/summary.json
```

Bilibili 素材：

```text
source.json
raw/video.info.json
raw/subtitle.srt
raw/audio.m4a
canonical/transcript.md
summary/domain.json
summary/summary.json
```

只写入当前工作流实际产生的素材。例如找到可用字幕时，不要求存在 `raw/audio.m4a`。

阶段四成功时，`asset_manifest` 记录真实产生的素材：字幕路径成功时记录 `metadata`、`subtitle` 和 `canonical_text`；Whisper fallback 成功时记录 `metadata`、`audio` 和 `canonical_text`。

阶段五成功时，`asset_manifest` 记录真实产生的素材：`html`、`metadata` 和 `canonical_text`。`parser_id` 记录 `wechat_article` 或 `generic_article`，`fetch_method` 当前固定为 `http`。

阶段六成功时，分类结果写入 `summary/domain.json`。阶段七成功时，结构化中文总结写入 `summary/summary.json`。如果启用评测模式，候选结果或失败记录写入 `summary/evaluations/<model_ref>.json`；评测目录不会被清空，当前候选文件会被覆盖。阶段八成功时，Obsidian note 写入 vault inbox，SQLite `sources.status` 更新为 `processed`。

## SQLite 索引

SQLite 是权威索引。每个来源目录中的 `source.json` 是便于人类查看和恢复的快照。

初始 SQLite schema 版本使用 `PRAGMA user_version = 1`。工具打开数据库时，如果发现 `user_version` 高于当前支持版本，应拒绝继续处理并返回配置错误，避免旧版本工具误写未来 schema。

初始 schema：

```sql
CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  normalized_url TEXT NOT NULL UNIQUE,
  original_url TEXT NOT NULL,
  content_type TEXT NOT NULL,
  domain TEXT,
  title TEXT,
  note_path TEXT,
  asset_dir TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT
);

CREATE INDEX idx_sources_domain ON sources(domain);
CREATE INDEX idx_sources_created_at ON sources(created_at);
CREATE INDEX idx_sources_status ON sources(status);
```

重复查询：

```sql
SELECT note_path, asset_dir
FROM sources
WHERE normalized_url = ? AND status = 'processed';
```

工具会用 `status = 'failed'` 和结构化错误字段记录失败尝试，为未来重试流程保留失败上下文。

## Obsidian 笔记

笔记写入：

```text
<vault_path>/<inbox_dir>/YYYY-MM-DD-safe-title.md
```

Frontmatter：

```yaml
---
title: "中文标题"
source_id: "8f3a91c2b7..."
source_url: "https://..."
content_type: "bilibili_video"
domain: "AI"
tags:
  - "knowledge/AI"
  - "source/bilibili"
created_at: "2026-06-15T10:30:00+08:00"
updated_at: "2026-06-15T10:30:00+08:00"
asset_dir: "/Users/xu/KnowledgeAssets/8f3a91c2b7"
canonical_text: "/Users/xu/KnowledgeAssets/8f3a91c2b7/canonical/transcript.md"
domain_path: "/Users/xu/KnowledgeAssets/8f3a91c2b7/summary/domain.json"
summary_path: "/Users/xu/KnowledgeAssets/8f3a91c2b7/summary/summary.json"
summary_model_ref: "deepseek_v4_pro"
status: "processed"
---
```

正文：

```markdown
# 中文标题

## 一句话摘要

## 核心观点

## 关键概念

## 领域笔记

## 可操作启发

## 值得追问的问题

## 来源与素材
- 原始链接：
- 素材目录：
- 正文/转写稿：
```

正文只包含总结和引用，不嵌入完整原始内容或完整转写稿。

`领域笔记` 由选中的领域模板渲染。阶段七固定字段表：

- `AI`：核心问题、模型或方法、工具或系统、数据或评测、工作流影响、能力边界、可复现说明。
- `编程`：问题背景、技术机制、工具或框架、实现细节、调试与验证、性能或安全、适用边界。
- `产品`：用户痛点、使用场景、产品假设、关键功能、工作流影响、指标或反馈、风险。
- `商业`：商业模式、目标用户、价值主张、增长路径、成本结构、竞争与壁垒、风险。
- `学习`：学习目标、方法步骤、适用场景、练习设计、反馈机制、常见误区、复盘方式。
- `心理学`：核心概念、机制解释、证据或论证、适用场景、干预方法、局限、伦理风险。
- `投资`：核心论点、关键假设、资产或标的、风险因素、估值或价格、需要监控的信号、反方观点。
- `写作`：主题、论证结构、表达技巧、素材使用、叙事节奏、可复用模式、修改建议。
- `生活`：具体情境、核心原则、行动步骤、工具或资源、注意事项、风险、可持续做法。
- `菜谱`：菜品特点、食材、步骤、时间与火候、技巧说明、替代方案、失败排查。
- `其他`：主题、背景、关键信息、适用场景、注意事项、延伸方向。

## AI 输出

领域分类输出：

```json
{
  "taxonomy_version": 1,
  "domain": "AI",
  "confidence": 0.86,
  "reason": "内容主要讨论大模型 Agent 架构和工具调用",
  "model_ref": "deepseek_v4_flash",
  "model": "deepseek-v4-flash"
}
```

总结输出：

```json
{
  "schema_version": 1,
  "domain": "AI",
  "title": "Agent 工具调用的设计边界",
  "one_sentence_summary": "这份内容说明了 Agent 应该负责判断和编排，确定性工具应该负责下载、转写、写文件等副作用。",
  "core_points": [
    "Agent 适合做内容理解、领域判断和总结结构选择。",
    "下载、转写、查重和写入应由受控工具执行。",
    "结构化 JSON 输出可以让 Hermes 稳定处理结果和错误。"
  ],
  "key_concepts": [
    {"name": "受控工具", "explanation": "由程序定义输入输出和副作用边界的工具函数。"}
  ],
  "domain_notes": {
    "核心问题": "如何划分 Agent 判断和工具副作用边界。",
    "模型或方法": "使用 Deep Agents 的 skill 指导流程，用 Python tools 执行实际动作。",
    "工具或系统": "受控 Python tools、Hermes CLI、结构化 JSON。",
    "数据或评测": "原文未明确说明",
    "工作流影响": "让 Hermes 稳定处理结果和错误。",
    "能力边界": "Agent 不能自由执行 shell 或直接写文件。",
    "可复现说明": "通过固定 CLI 契约和测试替身复现。"
  },
  "actionable_insights": ["把每个高风险动作包装成可测试的 typed tool。"],
  "questions": ["未来是否需要让 Hermes 看到部分中间状态以支持进度展示？"],
  "tags": ["knowledge/AI", "source/bilibili"],
  "source": {
    "url": "https://www.bilibili.com/video/BV...",
    "content_type": "bilibili_video",
    "asset_dir": "/Users/xu/KnowledgeAssets/<source_id>",
    "canonical_text_path": "/Users/xu/KnowledgeAssets/<source_id>/canonical/transcript.md",
    "domain_path": "/Users/xu/KnowledgeAssets/<source_id>/summary/domain.json"
  },
  "input": {
    "canonical_text_path": "/Users/xu/KnowledgeAssets/<source_id>/canonical/transcript.md",
    "domain_path": "/Users/xu/KnowledgeAssets/<source_id>/summary/domain.json",
    "strategy": "single_pass",
    "truncated": false,
    "max_input_chars": 0
  },
  "prompt": {
    "prompt_id": "summary.ai.v1",
    "domain": "AI"
  },
  "model_ref": "deepseek_v4_pro",
  "model": "deepseek-v4-pro"
}
```

CLI 在写文件前校验模型输出 schema。领域分类的非 JSON、缺字段、非法领域、字段类型错误或非有限 `confidence` 会变成 `LLM_SCHEMA_INVALID`。中文总结的非纯 JSON object、代码块、缺字段、非法 `domain_notes`、非法 `tags`、非法 `title` 或非法 `key_concepts` 会变成 `SUMMARY_SCHEMA_INVALID`。模型/API 上下文超限会变成 `SUMMARY_INPUT_TOO_LARGE`。

## 错误处理

初始错误码：

- `CONFIG_INVALID`
- `INPUT_INVALID`
- `UNSUPPORTED_URL`
- `FETCH_FAILED`
- `BILIBILI_METADATA_FAILED`
- `BILIBILI_TRANSCRIPT_FAILED`
- `WHISPER_UNAVAILABLE`
- `WEB_FETCH_FAILED`
- `WEB_PARSE_FAILED`
- `LLM_REQUEST_FAILED`
- `LLM_SCHEMA_INVALID`
- `SUMMARY_INPUT_INVALID`
- `SUMMARY_INPUT_TOO_LARGE`
- `SUMMARY_SCHEMA_INVALID`
- `NOTE_WRITE_FAILED`
- `INDEX_WRITE_FAILED`

返回给 Hermes 的错误：

```json
{
  "ok": false,
  "error_code": "CONFIG_INVALID",
  "message": "人类可读的错误信息",
  "recoverable": false
}
```

CLI 将内部异常映射为稳定错误码。内部 traces 记录到 stderr，不写入 stdout。

## 测试策略

测试覆盖：

- CLI 协议：stdin 解析、stdout JSON、stderr 日志、退出码。
- 配置加载和校验。
- URL 规范化和重复检测。
- SQLite schema 创建、查询、成功写入和失败尝试记录。
- Markdown 渲染快照。
- 使用 mocked HTTP 响应测试网页采集器。
- 使用 mocked `yt-dlp` 响应测试 Bilibili 采集器。
- 使用 fake transcriber 测试 Whisper 封装。
- 使用 fixture JSON 测试 LLM 分类和总结 schema 校验。
- 使用 fake collectors 和 fake LLM responses 测试端到端成功路径。

真实网络和真实 Whisper 测试应该是可选集成测试，不作为必需单元测试。
