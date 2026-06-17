# nooliigee

## 项目文档

- [项目探索总览](docs/project-overview.md)：记录项目定位、总体架构、阶段路线、当前状态和后续演进方向。
- [决策日志](docs/decision-log.md)：记录前期讨论中的关键问题、选项、最终决策和状态。

## 知识导入 CLI 本地状态基础

当前阶段实现 `km ingest` 的协议骨架、本地状态基础、确定性 URL 路由、Bilibili 视频到规范文本的处理闭环、网页文章到规范正文的处理闭环、文本化之后的领域分类闭环、中文总结闭环，以及 Obsidian 写入和 SQLite `processed` 状态闭环，用于 Hermes agent 调用。它处理 CLI 契约、阶段二配置校验、URL 规范化、素材仓库初始化、SQLite 去重索引、重复来源跳过、内容路由、Bilibili 元数据/字幕/音频/本地 Whisper 到 `canonical/transcript.md` 的生成、微信公众号/通用网页到 `canonical/content.md` 的生成、`summary/domain.json` 和 `summary/summary.json` 的生成、Obsidian Markdown note 写入，以及 `sources.status = "processed"` 标记；不实现 Deep Agents 运行时业务能力。

## 项目管理

本工程使用 `uv` 进行 Python 项目管理、依赖解析、锁文件管理和项目虚拟环境管理。

- `pyproject.toml` 是项目元数据和依赖声明入口。
- `uv.lock` 是需要提交的锁文件，用于固定依赖解析结果。
- `.python-version` 固定本地开发默认 Python 为 `3.11`。
- `.venv/` 是 `uv sync` 自动创建和同步的项目虚拟环境，只保留在本地，不提交。
- `.uv-cache/` 是受限环境中可选的本地 uv 缓存目录，只保留在本地，不提交。

同步项目环境：

```bash
uv sync
```

运行测试：

```bash
uv run python -m unittest discover -s tests -v
```

在受限环境中，如果默认 uv 缓存目录不可写，可以使用：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v
```

示例配置：

```toml
vault_path = "/Users/xu/Obsidian"
inbox_dir = "Inbox/Knowledge"
asset_store_path = "/Users/xu/KnowledgeAssets"

[whisper]
model_dir = "/Users/xu/models/whisper-openvino"
model_size = "medium"
device = "GPU"

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
```

`asset_store_path` 必须位于 `vault_path` 外部。`inbox_dir` 必须是 vault 内相对路径，不能是绝对路径，也不能包含 `..`。

`whisper.model_dir` 默认是 `models/whisper`，`whisper.model_size` 默认是 `medium`，可配置为 `tiny`、`small` 或 `medium` 这类 HuggingFace Whisper 尺寸名。`whisper.device` 默认是 `GPU`，用于 OpenVINO + optimum-intel 的 Intel Xe 集成显卡加速；也可以显式配置为 `GPU.0`。首次遇到无字幕 Bilibili 视频时，系统会把 Whisper 模型导出/缓存到 `whisper.model_dir/<model_size>/`，不会复用其他项目的模型目录。阶段四不允许静默 CPU fallback，`whisper.device = "CPU"` 会被拒绝。

阶段六在文本化成功后执行领域分类，阶段七在领域分类成功后执行中文总结。`[llm.models.<ref>]` 集中定义可用模型，`[llm.tasks] domain_classification = "<ref>"` 指定分类任务使用哪个模型，`[llm.tasks] summary_generation = "<ref>"` 指定非评测模式和主输出使用的总结模型。首版只支持 `provider = "openai_compatible"`，被引用模型必须配置 `provider`、`base_url`、`model` 和 `api_key_env`，且 `api_key_env` 指向的环境变量必须存在且非空。模型可选配置 `timeout_seconds` 和 `max_output_tokens`，默认分别为 `120` 和 `8192`。

`[summary].max_input_chars = 0` 表示总结阶段不主动截断输入。如果启用 `[summary.evaluation]`，系统会并发调用 `candidate_models`，把 `primary_model` 的结果写入权威 `summary/summary.json`，并把候选结果或失败记录写入 `summary/evaluations/<model_ref>.json`。评测只产出候选文件，不做评分、排序、manifest、UI 或人工选择记录。

## URL 路由

阶段三在本地状态层之后执行确定性 URL 路由，不访问网络、不展开短链、不下载内容。

- `www.bilibili.com/video/<id>`、`bilibili.com/video/<id>`、`m.bilibili.com/video/<id>` 路由为 `bilibili_video`。
- `b23.tv/<id>` 路由为 `bilibili_video` 候选，短链展开留给后续 Bilibili collector。
- 非 Bilibili 的普通 `http/https` URL 路由为 `web_article`。
- Bilibili 非视频路径和空 `b23.tv` 路径路由为 `unsupported`。

项目内 `skills/` 目录保存未来 Hermes/Deep Agents 使用的版本化指令资产，例如 `skills/url-routing/SKILL.md` 和 `skills/domain-classification/SKILL.md`。这些文件不是当前研发环境使用的 `.codex/skills/`，也不允许 agent 绕过受控 Python tools 自行写入素材仓库、SQLite 或 Obsidian。

## Bilibili 文本化

阶段四对 `bilibili_video` URL 执行文本化闭环：

- 通过受控 `yt-dlp` wrapper 获取元数据。
- 优先使用可用字幕生成 `canonical/transcript.md`。
- 没有字幕时下载 WAV 音频到 `raw/`。
- 使用 OpenVINO + optimum-intel Whisper 在 Intel Xe 集成显卡上本地转写。
- 成功后继续执行领域分类、中文总结和 Obsidian 写入，并在完整处理成功时返回 `processed_ready`。

这一阶段生成规范文本和素材清单后会继续进入阶段六领域分类、阶段七中文总结和阶段八 Obsidian processed pipeline。

无字幕视频需要安装 GPU 可选依赖并启用 extra：

```bash
uv sync --extra gpu

uv run --extra gpu --env-file .env km ingest <<'JSON'
{"url":"https://www.bilibili.com/video/BV1zoGv6NE2q","mode":"ingest"}
JSON
```

Arch Linux 上还需要系统 OpenCL/Level Zero 运行时，并确认 OpenVINO 能看到 `GPU`：

```bash
sudo pacman -S intel-compute-runtime level-zero-loader
sudo usermod -a -G render $USER
uv run --extra gpu python -c "from openvino import Core; print(Core().available_devices)"
```

## 网页文章文本化

阶段五对 `web_article` URL 执行文本化闭环：

- 使用受控 HTTP fetcher 抓取网页 HTML。
- 保存原始 HTML 到 `raw/page.html`。
- `mp.weixin.qq.com` 使用微信公众号专用 parser。
- 其他普通网页使用 `trafilatura` 通用 fallback parser。
- 保存元数据到 `raw/metadata.json`。
- 生成规范正文 `canonical/content.md`。
- 成功后继续执行领域分类、中文总结和 Obsidian 写入，并在完整处理成功时返回 `processed_ready`。

本阶段依赖组合为 `httpx`、`trafilatura` 和 `beautifulsoup4`，由 uv 管理。阶段五不实现 Playwright/browser fallback、登录态/cookie 管理、CSDN 专用 parser 或知乎专用 parser；无法通过普通 HTTP 获取或解析的页面会返回 `WEB_FETCH_FAILED` 或 `WEB_PARSE_FAILED`。

这一阶段生成规范正文和素材清单后会继续进入阶段六领域分类、阶段七中文总结和阶段八 Obsidian processed pipeline。

## 领域分类

阶段六对 `bilibili_video` 和 `web_article` 的规范文本执行领域分类：

- 读取 `canonical/transcript.md` 或 `canonical/content.md`。
- 使用 `[llm.tasks] domain_classification` 引用的 OpenAI-compatible 模型。
- 分类 prompt 只使用规范文本前 12000 个字符；超长文本会在 prompt 中标明已截断。
- 只从固定领域表中选择一个主领域：`AI`、`编程`、`产品`、`商业`、`学习`、`心理学`、`投资`、`写作`、`生活`、`菜谱`、`其他`。
- 内容跨领域、证据不足或低置信度时归入 `其他`，不因为置信度低而失败。
- 写入 `summary/domain.json`，不生成 `summary/domain.md`。
- 当前仍由 Python 确定性 pipeline 自动接在文本化之后执行，不接入 LangChain Deep Agents 运行时。

`summary/domain.json` 示例：

```json
{
  "taxonomy_version": 1,
  "domain": "AI",
  "confidence": 0.86,
  "reason": "内容主要讨论大模型 Agent 架构和工具调用。",
  "model_ref": "deepseek_v4_flash",
  "model": "deepseek-v4-flash"
}
```

## 中文总结

阶段七对 `bilibili_video` 和 `web_article` 的规范文本执行单次中文总结：

- 读取 `canonical/transcript.md` 或 `canonical/content.md`。
- 读取阶段六生成的 `summary/domain.json`，按主领域选择 `prompts/summary/domains/*.md`。
- 使用 `prompts/summary/common.md` 约束模型只输出纯 JSON object。
- 写入权威总结 `summary/summary.json`。
- 默认不主动截断输入；显式配置 `max_input_chars > 0` 时按字符数截断并记录 `input.truncated`。
- 评测模式开启时，并发写入 `summary/evaluations/<model_ref>.json`，主模型成功后写入 `summary/summary.json`。
- 当前仍由 Python 确定性 pipeline 自动接在领域分类之后执行，不接入 LangChain Deep Agents 运行时。

`summary/summary.json` 包含 `schema_version`、`domain`、`title`、`one_sentence_summary`、`core_points`、`key_concepts`、`domain_notes`、`actionable_insights`、`questions`、`tags`、`source`、`input`、`prompt`、`model_ref` 和 `model`。模型只负责内容字段；系统会覆盖来源、输入、prompt 和模型追溯字段。

## Obsidian 写入与 processed 状态

阶段八在中文总结成功后自动执行：

- 读取并校验 `summary/summary.json`，确认 `schema_version`、来源 URL 和素材路径与当前 pipeline 一致。
- 将结构化总结渲染成 Obsidian Markdown，写入 `<vault_path>/<inbox_dir>/YYYY-MM-DD-safe-title.md`。
- `safe-title` 会移除 `/ \ : * ? " < > |`，折叠空白，最长 80 个字符；为空时使用 `untitled`。
- 同 `source_id` 重试会覆盖同一 note 并保留旧 `created_at`；不同来源同名时使用 `-<source_id前8位>` 兜底。
- note 正文只包含总结、原始链接和素材路径引用，不嵌入完整原文、完整 transcript、原始 HTML 或完整 prompt。
- note 写入成功后，SQLite `sources` 写入或更新为 `status = "processed"`，并清空错误字段。

`vault_path` 必须已存在、是目录且可写；`inbox_dir` 可以自动创建。Obsidian 写入失败返回 `OBSIDIAN_WRITE_FAILED`。note 已写入但 SQLite processed 状态写入失败时返回 `INDEX_WRITE_FAILED`，响应中会包含已写入的 `note_path`，方便后续重试和人工检查。

示例调用：

```bash
KM_CONFIG=/path/to/config.toml uv run km ingest <<'JSON'
{"url":"https://example.com"}
JSON
```

如果 URL 合法但当前不支持，会返回：

```json
{
  "ok": false,
  "error_code": "UNSUPPORTED_URL",
  "message": "当前版本不支持处理该 URL。",
  "recoverable": false
}
```

Bilibili 文本化、领域分类、中文总结和 Obsidian 写入成功会返回：

```json
{
  "ok": true,
  "status": "processed_ready",
  "content_type": "bilibili_video",
  "source_url": "https://www.bilibili.com/video/BV...",
  "asset_dir": "/Users/xu/KnowledgeAssets/<source_id>",
  "canonical_text_path": "/Users/xu/KnowledgeAssets/<source_id>/canonical/transcript.md",
  "domain_path": "/Users/xu/KnowledgeAssets/<source_id>/summary/domain.json",
  "summary_path": "/Users/xu/KnowledgeAssets/<source_id>/summary/summary.json",
  "note_path": "/Users/xu/Obsidian/Inbox/Knowledge/2026-06-15-AI-Agent-工具系统复盘.md",
  "domain": "AI",
  "title": "AI Agent 工具系统复盘"
}
```

网页文章文本化、领域分类、中文总结和 Obsidian 写入成功会返回：

```json
{
  "ok": true,
  "status": "processed_ready",
  "content_type": "web_article",
  "source_url": "https://example.com/article",
  "asset_dir": "/Users/xu/KnowledgeAssets/<source_id>",
  "canonical_text_path": "/Users/xu/KnowledgeAssets/<source_id>/canonical/content.md",
  "domain_path": "/Users/xu/KnowledgeAssets/<source_id>/summary/domain.json",
  "summary_path": "/Users/xu/KnowledgeAssets/<source_id>/summary/summary.json",
  "note_path": "/Users/xu/Obsidian/Inbox/Knowledge/2026-06-15-Python-调试实践.md",
  "domain": "编程",
  "title": "Python 调试实践"
}
```

CLI 端到端成功响应不暴露 `summary_model_ref`、`evaluation_enabled`、`evaluation_dir`、`taxonomy_version` 或 `model_ref`；这些追溯信息保留在素材仓库 JSON 产物中。

LLM 请求失败返回 `LLM_REQUEST_FAILED`，领域分类响应不是合法分类 JSON、字段不符合 schema，或 `confidence` 不是有限数字时返回 `LLM_SCHEMA_INVALID`。中文总结输入缺失或不合法返回 `SUMMARY_INPUT_INVALID`，模型/API 上下文超限返回 `SUMMARY_INPUT_TOO_LARGE`，总结响应不是合法纯 JSON object 或字段不符合 schema 返回 `SUMMARY_SCHEMA_INVALID`。Obsidian 写入失败返回 `OBSIDIAN_WRITE_FAILED`。note 已写入但 SQLite processed 写入失败返回 `INDEX_WRITE_FAILED`，并包含 `note_path`。这些都是可恢复处理失败，退出码为 `2`。

如果 SQLite 索引中已经存在同一 `normalized_url` 且 `status = 'processed'` 的记录，会返回：

```json
{
  "ok": true,
  "status": "skipped_existing",
  "note_path": "/Users/xu/Obsidian/Inbox/Knowledge/example.md",
  "asset_dir": "/Users/xu/KnowledgeAssets/<source_id>",
  "source_url": "https://example.com"
}
```
