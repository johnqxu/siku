# siku 思库

siku 是一个面向 Hermes agent 的知识导入 CLI。它接收单个 URL，采集或转写正文，生成结构化中文总结，写入 Obsidian，并把原始素材、中间产物和去重状态保存在 Obsidian vault 外部。

当前默认入口是 `km agent-ingest`，由项目内部 Deep Agents 编排受控 Python tools，提供 agent 编排、state/trace 可观测性和自动产物复用。同时也保留 `km ingest` 作为确定性调试/验证基线。输入和输出都使用 JSON，方便 Hermes 或其他上层调度器做重试、错误处理和状态跟踪。

## 当前能力

- 支持 Bilibili 视频 URL 和普通网页文章 URL。
- Bilibili 优先使用字幕；没有字幕时下载音频并使用 OpenVINO Whisper 本地转写。
- 网页文章支持微信公众号专用解析和 `trafilatura` 通用解析。
- 文本化后自动执行领域分类、中文总结、Obsidian note 写入和 SQLite `processed` 标记。
- 已处理过的 `normalized_url` 会返回 `skipped_existing`，避免重复写入。
- 可选 `agent` extra 提供 `km agent-ingest`，写入 `<asset_dir>/agent/state.json` 和 `<asset_dir>/agent/trace.jsonl` 便于观察 agent 编排。

## 快速开始

同步基础依赖：

```bash
uv sync
```

创建 `.env`：

```bash
cp .env.example .env
```

编辑 `.env`，至少填入：

```dotenv
DEEPSEEK_API_KEY=your-deepseek-api-key-here
KM_CONFIG=/home/xu/.config/siku/config.toml
```

创建 `KM_CONFIG` 指向的 TOML 配置文件。完整示例见下方“配置”。

运行一次网页导入（推荐 — Deep Agents 编排）：

```bash
uv run --extra agent --env-file .env km agent-ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
```

运行一次网页导入（确定性调试）：

```bash
uv run --env-file .env km ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
```

运行测试：

```bash
uv run python -m unittest discover -s tests -v
```

如果当前环境的默认 uv 缓存目录不可写，改用项目内缓存：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m unittest discover -s tests -v
```

## 配置

配置默认读取 `~/.config/km/config.toml`，推荐通过 `.env` 显式指定：

```dotenv
KM_CONFIG=/home/xu/.config/siku/config.toml
DEEPSEEK_API_KEY=your-deepseek-api-key-here
```

`DEEPSEEK_API_KEY` 是示例 LLM 配置使用的 API key 环境变量。实际变量名由 TOML 中的 `api_key_env` 决定。

TOML 示例：

```toml
vault_path = "/home/xu/Obsidian"
inbox_dir = "Inbox/Knowledge"
asset_store_path = "/home/xu/KnowledgeAssets"

[whisper]
model_dir = "/home/xu/models/whisper-openvino"
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
agent_orchestration = "deepseek_v4_flash"
domain_classification = "deepseek_v4_flash"
summary_generation = "deepseek_v4_pro"

[summary]
max_input_chars = 0

[summary.evaluation]
enabled = true
candidate_models = ["deepseek_v4_flash", "deepseek_v4_pro"]
primary_model = "deepseek_v4_pro"
```

关键约束：

- `vault_path` 必须是已存在且可写的 Obsidian vault。
- `inbox_dir` 必须是 vault 内相对路径，不能是绝对路径，也不能包含 `..`。
- `asset_store_path` 必须位于 vault 外部。
- `[llm.tasks]` 引用的模型必须存在于 `[llm.models]`。
- `agent_orchestration` 只用于 Deep Agents 编排模型，不改变领域分类或中文总结模型。
- `api_key_env` 指向的环境变量必须存在且非空。
- `summary.max_input_chars = 0` 表示总结阶段不主动截断输入。

LLM 配置说明：

- `[llm.models.<name>]` 定义一个可被任务引用的模型。`<name>` 是本地引用名，只能由 `[llm.tasks]` 或 `summary.evaluation` 使用，不会直接暴露给 CLI 输入。
- 每个被引用的模型必须配置 `provider`、`base_url`、`model` 和 `api_key_env`。当前只支持 `provider = "openai_compatible"`。
- `api_key_env` 写环境变量名，不写真实密钥。运行时会从 `.env` 或继承环境读取该变量；缺失或空值会返回 `CONFIG_INVALID`。
- `timeout_seconds` 和 `max_output_tokens` 可选，默认分别为 `120` 和 `8192`，都必须为正数。
- `[llm.tasks] domain_classification` 指定领域分类模型，是 `km ingest` 和 `km agent-ingest` 的业务分类模型。
- `[llm.tasks] summary_generation` 指定中文总结主模型，是 `km ingest` 和 `km agent-ingest` 的业务总结模型。
- `[llm.tasks] agent_orchestration` 指定 Deep Agents 编排模型，只在 `km agent-ingest` 启动时必需。普通 `km ingest` 不需要它；如果调用 `km agent-ingest` 但未配置，会返回 `CONFIG_INVALID`。
- `agent_orchestration` 的模型应支持 tool calling。它只决定下一步调用哪个受控 Python tool，不直接生成领域分类或中文总结正文。
- `summary.evaluation.enabled = true` 时，`candidate_models` 和 `primary_model` 也必须引用 `[llm.models]` 中存在且字段合法的模型。
- 只有被 `[llm.tasks]` 或 `summary.evaluation` 引用的模型会被解析并校验，因此可以在配置文件中保留未使用的模型草稿。

## Deep Agents 编排入口

安装 agent 可选依赖：

```bash
uv sync --extra agent
```

`agent` extra 会安装真实 Deep Agents runtime 和 OpenAI-compatible LangChain 适配依赖：

- `deepagents>=0.6.11,<0.7`
- `langchain-openai>=1.1.4,<2`

调用 `km agent-ingest`：

```bash
uv run --extra agent --env-file .env km agent-ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
```

无字幕 Bilibili 且需要本地 Whisper GPU 转写时，同时启用 `agent` 和 `gpu`：

```bash
uv run --extra agent --extra gpu --env-file .env km agent-ingest <<'JSON'
{"url":"https://www.bilibili.com/video/BV1zoGv6NE2q","mode":"ingest"}
JSON
```

`km agent-ingest` 和 `km ingest` 使用同一 stdin 契约，但编排边界不同：

- `km ingest` 由确定性 Python pipeline 直接编排。
- `km agent-ingest` 内部启动 Deep Agents runtime，由状态机 guard 约束它只能调用受控 Python tools。
- Hermes 只调用 CLI，不直接调用 `route_url`、`collect_bilibili_text`、`generate_summary` 等内部 tools。
- agent 路径失败不会自动 fallback 到 `km ingest`。
- stdin 中的 `force`、`rerun_from` 等额外字段首版会被忽略，默认复用已有合法产物。

agent 成功或拥有素材上下文的失败响应会增加：

```json
{
  "orchestrator": "deep_agents",
  "trace_path": "/home/xu/KnowledgeAssets/<source_id>/agent/trace.jsonl",
  "state_path": "/home/xu/KnowledgeAssets/<source_id>/agent/state.json"
}
```

`state.json` 保存最新 agent 状态快照，`trace.jsonl` append-only 记录每次运行的 `run_id`、tool attempt、跳过原因和完成或失败事件。trace 不写入完整正文、完整 transcript、完整 HTML、完整 prompt、完整模型输出、API key、cookie 或环境变量值。

## GPU / Whisper

无字幕 Bilibili 视频需要 GPU 可选依赖：

```bash
uv sync --extra gpu
```

导入时也要启用 extra：

```bash
uv run --extra gpu --env-file .env km ingest <<'JSON'
{"url":"https://www.bilibili.com/video/BV1zoGv6NE2q","mode":"ingest"}
JSON
```

Arch Linux 上需要系统 OpenCL/Level Zero 运行时：

```bash
sudo pacman -S intel-compute-runtime level-zero-loader
sudo usermod -a -G render $USER
```

确认 OpenVINO 能看到 Intel GPU：

```bash
uv run --extra gpu python -c "from openvino import Core; print(Core().available_devices)"
```

期望输出包含 `GPU`，例如：

```text
['CPU', 'GPU']
```

Whisper 配置说明：

- `whisper.model_dir` 默认是 `models/whisper`，建议在真实使用时配置为 `/home/xu/models/whisper-openvino` 这类 Linux 可写路径。
- 首次无字幕转写会把模型导出或缓存到 `whisper.model_dir/<model_size>/`。
- `whisper.model_size` 默认是 `medium`，可配置为 `tiny`、`small` 或 `medium` 等 HuggingFace Whisper 尺寸名。
- `whisper.device` 默认是 `GPU`，也可以显式配置为 `GPU.0`。
- 项目不允许静默 CPU fallback；`whisper.device = "CPU"` 会被拒绝，GPU runtime 不可用会返回 `WHISPER_UNAVAILABLE`。

## 处理流程

```text
stdin JSON
  -> 配置加载
  -> URL 规范化
  -> SQLite processed 去重
  -> 确定性 URL 路由
  -> Bilibili 或网页文本化
  -> 领域分类
  -> 中文总结
  -> Obsidian note 写入
  -> SQLite 标记 processed
  -> stdout JSON
```

URL 路由规则：

- `www.bilibili.com/video/<id>`、`bilibili.com/video/<id>`、`m.bilibili.com/video/<id>` 路由为 `bilibili_video`。
- `b23.tv/<id>` 路由为 `bilibili_video` 候选，短链展开交给 Bilibili collector。
- 非 Bilibili 的普通 `http/https` URL 路由为 `web_article`。
- Bilibili 非视频路径和空 `b23.tv` 路径路由为 `unsupported`。

## 输出产物

每个来源使用 `sha256(normalized_url).hexdigest()` 作为 `source_id`。素材仓库结构：

```text
<asset_store_path>/
  index.sqlite
  <source_id>/
    raw/
    canonical/
    summary/
    agent/
```

常见产物：

- `raw/metadata.json`：采集到的来源元数据。
- `raw/page.html`：网页文章原始 HTML。
- `raw/subtitle.*`：Bilibili 原始字幕。
- `raw/audio.wav`：无字幕 Bilibili 的本地音频。
- `canonical/transcript.md`：Bilibili 规范转写文本。
- `canonical/content.md`：网页文章规范正文。
- `summary/domain.json`：领域分类结果。
- `summary/summary.json`：权威中文总结。
- `agent/state.json`：agent 路径最新状态快照。
- `agent/trace.jsonl`：agent 路径 append-only 运行 trace。
- `<vault_path>/<inbox_dir>/YYYY-MM-DD-safe-title.md`：Obsidian note。

Obsidian note 只包含总结、原始链接和素材路径引用，不嵌入完整原文、完整 transcript、原始 HTML 或完整 prompt。

## CLI 响应

成功响应示例：

```json
{
  "ok": true,
  "status": "processed_ready",
  "content_type": "web_article",
  "source_url": "https://example.com/article",
  "asset_dir": "/home/xu/KnowledgeAssets/<source_id>",
  "canonical_text_path": "/home/xu/KnowledgeAssets/<source_id>/canonical/content.md",
  "domain_path": "/home/xu/KnowledgeAssets/<source_id>/summary/domain.json",
  "summary_path": "/home/xu/KnowledgeAssets/<source_id>/summary/summary.json",
  "note_path": "/home/xu/Obsidian/Inbox/Knowledge/2026-06-19-Python-调试实践.md",
  "domain": "编程",
  "title": "Python 调试实践"
}
```

重复来源跳过示例：

```json
{
  "ok": true,
  "status": "skipped_existing",
  "note_path": "/home/xu/Obsidian/Inbox/Knowledge/example.md",
  "asset_dir": "/home/xu/KnowledgeAssets/<source_id>",
  "source_url": "https://example.com"
}
```

错误响应示例：

```json
{
  "ok": false,
  "error_code": "UNSUPPORTED_URL",
  "message": "当前版本不支持处理该 URL。",
  "recoverable": false
}
```

常见错误码：

| 错误码 | 含义 | 可恢复 |
| --- | --- | --- |
| `INPUT_INVALID` | stdin JSON 或请求字段不合法 | 否 |
| `CONFIG_INVALID` | 配置文件缺失、不可读或字段不合法 | 否 |
| `UNSUPPORTED_URL` | URL 合法但当前版本不支持 | 否 |
| `BILIBILI_METADATA_FAILED` | Bilibili 元数据采集失败 | 是 |
| `BILIBILI_TRANSCRIPT_FAILED` | Bilibili 字幕、音频或文本化失败 | 是 |
| `WHISPER_UNAVAILABLE` | OpenVINO Whisper GPU 转写不可用 | 是 |
| `WEB_FETCH_FAILED` | 网页抓取失败 | 是 |
| `WEB_PARSE_FAILED` | 网页正文解析失败 | 是 |
| `LLM_REQUEST_FAILED` | LLM 请求失败 | 是 |
| `LLM_SCHEMA_INVALID` | 领域分类 LLM 返回不符合 schema | 是 |
| `SUMMARY_INPUT_INVALID` | 总结输入缺失或不合法 | 是 |
| `SUMMARY_INPUT_TOO_LARGE` | 模型/API 上下文超限 | 是 |
| `SUMMARY_SCHEMA_INVALID` | 总结 LLM 返回不符合 schema | 是 |
| `OBSIDIAN_WRITE_FAILED` | Obsidian note 写入失败 | 是 |
| `INDEX_WRITE_FAILED` | note 已写入但 SQLite processed 状态写入失败 | 是 |
| `AGENT_RUNTIME_UNAVAILABLE` | Deep Agents runtime 或 agent 模型适配不可用 | 是 |
| `AGENT_SKILL_MISSING` | agent 必需项目 skill 缺失、不可读或为空 | 是 |
| `AGENT_INVALID_TRANSITION` | agent 在当前 stage 调用了非法 tool | 是 |
| `AGENT_ORCHESTRATION_FAILED` | agent 编排未收敛、超过步数或返回无法解释结果 | 是 |

协议错误退出码为 `1`，可恢复处理失败退出码为 `2`。

## 开发

项目使用 `uv` 管理 Python 版本、依赖、锁文件和虚拟环境。

- `pyproject.toml`：项目元数据和依赖声明。
- `uv.lock`：需要提交的锁文件。
- `.python-version`：本地开发默认 Python 版本。
- `.venv/`：`uv sync` 自动创建的本地虚拟环境，不提交。
- `.uv-cache/`：受限环境中可选的项目内 uv 缓存目录，不提交。

常用命令：

```bash
uv sync
uv sync --extra agent
uv sync --extra gpu
uv sync --extra agent --extra gpu
uv run python -m unittest discover -s tests -v
uv run --extra agent --env-file .env km agent-ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
uv run --env-file .env km ingest <<'JSON'
{"url":"https://example.com/article","mode":"ingest"}
JSON
```

项目内 `skills/` 目录保存 Hermes/Deep Agents 使用的版本化指令资产。它不是当前研发环境使用的 `.codex/skills/`，也不授予 agent 直接写素材仓库、SQLite 或 Obsidian 的权限。

## 更多文档

- [项目探索总览](docs/project-overview.md)：项目定位、架构边界、阶段路线和现状。
- [决策日志](docs/decision-log.md)：关键问题、选项、最终决策和状态。
- `openspec/changes/**`：阶段提案、设计、任务和归档历史。
