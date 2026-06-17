## Context

项目当前已经具备 `km ingest` CLI、本地素材仓库、URL 路由、Bilibili/网页文本化、领域分类和 `summary/domain.json` 写入。阶段七要在现有 Python 确定性 pipeline 中继续执行中文总结，产出结构化 `summary/summary.json`，供阶段八 Obsidian 写入读取。

现有约束保持不变：CLI 通过 JSON stdin/stdout 工作，运行时配置由本地 TOML 提供，LLM 通过 OpenAI-compatible client 调用，测试不得依赖真实网络模型。阶段七仍然不是最终入库阶段，因此不写 Obsidian、不写 SQLite `processed`、不启用 Deep Agents 编排。

## Goals / Non-Goals

**Goals:**

- 在文本化和领域分类成功后自动执行中文总结，并返回 `summary_ready`。
- 定义稳定、可校验、可追溯的 `summary/summary.json` schema。
- 支持按领域选择 prompt 模板，固定领域表与阶段六保持一致。
- 支持单模型模式和配置驱动的评测模式；评测模式并发调用候选模型，主模型产出权威 summary。
- 将失败映射为公开错误码，并保证失败不覆盖旧的正式 `summary.json`。
- 为未来 Hermes/Deep Agents 提供 `skills/summary-generation/SKILL.md`，但只声明受控 tool 边界。

**Non-Goals:**

- 不做 chunk、map-reduce 或多轮总结。
- 不做自动评分、排序、候选选择、评测 manifest、人工评测记录或 UI。
- 不写 Obsidian 笔记，不写 SQLite `processed` 记录。
- 不引入 LangChain Deep Agents 运行时编排。
- 不把 DeepSeek 模型名硬编码在代码中；DeepSeek V4 Pro/Flash 只作为推荐配置示例。

## Decisions

### 1. 总结接入现有 `km ingest` 链路

阶段七不新增公开子命令。`km ingest` 在 Bilibili 或网页文本化成功后先执行领域分类，再执行总结，最终成功响应从 `domain_ready` 推进到 `summary_ready`。

原因：Hermes 未来只需要稳定调用一个导入入口；阶段七仍是端到端导入链路中的一个内部步骤。内部实现可以暴露可测试的 Python 函数或受控 tool，例如 `generate_summary(...)`，供 CLI 和未来 skill 复用。

### 2. 单次总结，不做 chunk

阶段七对长短文本都采用单次总结。默认 `[summary].max_input_chars = 0`，表示不主动截断；如果显式配置 `max_input_chars > 0`，系统按字符数截断并在输出 `input.truncated` 中记录。若未主动截断但模型/API 返回上下文超限，映射为 `SUMMARY_INPUT_TOO_LARGE`。

原因：当前目标是降低复杂度并验证主链路；长上下文模型可以承接多数输入。chunk 策略会引入额外 schema、汇总误差和测试复杂度，留到后续阶段再评估。

### 3. 固定 summary schema 与系统字段覆盖

`summary.json` 使用 `schema_version: 1`。模型只负责内容字段：`title`、`one_sentence_summary`、`core_points`、`key_concepts`、`domain_notes`、`actionable_insights`、`questions`、`tags`。系统字段由本地上下文覆盖，包括 `schema_version`、`domain`、`model_ref`、`model`、`source`、`input` 和 `prompt`。

原因：模型不可信任路径、领域、模型引用和 prompt 元数据；这些字段必须由系统上下文生成，保证阶段八读取时可追溯。

### 4. 领域专属 prompt 资产

prompt 放在项目资产中，而不是写成大型 Python 字符串：

```text
prompts/summary/common.md
prompts/summary/domains/ai.md
prompts/summary/domains/programming.md
prompts/summary/domains/product.md
prompts/summary/domains/business.md
prompts/summary/domains/learning.md
prompts/summary/domains/psychology.md
prompts/summary/domains/investing.md
prompts/summary/domains/writing.md
prompts/summary/domains/life.md
prompts/summary/domains/recipe.md
prompts/summary/domains/other.md
```

`prompt_id` 使用 `summary.<domain_key>.v1`，例如 `summary.ai.v1`。只改 prompt 也升级 prompt 版本；改 JSON schema 才升级 `schema_version`。

### 5. 严格 JSON 与 schema 校验

模型输出只接受纯 JSON object。Markdown 代码块、前后解释文本、数组或字符串都视为 `SUMMARY_SCHEMA_INVALID`。schema 校验严格字段、宽松内容：必要字段必须存在且类型正确；数组数量主要由 prompt 建议，不作为硬限制。`domain_notes` 必须包含对应领域的固定字段，缺字段直接失败，不自动补 `"原文未明确说明"`。

硬校验包括：

- `domain` 必须等于 `summary/domain.json` 的主领域。
- `title` 必须是非空字符串，且不能包含 `/ \ : * ? " < > |`。
- `one_sentence_summary` 必须是非空字符串。
- `tags` 最多 5 个，只允许 `knowledge/`、`topic/`、`tool/`、`source/`、`workflow/` 前缀，不允许空值或深层层级。
- `key_concepts` 必须是 `{name, explanation}` 对象数组。
- `core_points`、`actionable_insights`、`questions`、`tags` 必须是字符串数组。

中文输出由 prompt 约束，不做中文比例硬校验；专有名词、工具名、模型名、代码/API 名称可以保留英文。

### 6. 评测模式配置驱动

运行时配置示例推荐启用评测：

```toml
[llm.models.deepseek_v4_flash]
provider = "openai_compatible"
base_url = "..."
model = "..."
api_key_env = "DEEPSEEK_API_KEY"
timeout_seconds = 120
max_output_tokens = 8192

[llm.models.deepseek_v4_pro]
provider = "openai_compatible"
base_url = "..."
model = "..."
api_key_env = "DEEPSEEK_API_KEY"
timeout_seconds = 120
max_output_tokens = 8192

[llm.tasks]
summary_generation = "deepseek_v4_pro"

[summary]
max_input_chars = 0

[summary.evaluation]
enabled = true
candidate_models = ["deepseek_v4_flash", "deepseek_v4_pro"]
primary_model = "deepseek_v4_pro"
```

如果缺少 `[summary.evaluation]` 或 `enabled = false`，系统只调用 `llm.tasks.summary_generation`。如果 `enabled = true`，`candidate_models` 和 `primary_model` 必须存在，且 `primary_model` 必须包含在候选列表中。候选模型引用只能包含文件名安全字符 `a-z A-Z 0-9 _ -`。

评测模式使用 `ThreadPoolExecutor` 并发调用候选模型，不引入 async 框架、不使用 LangChain、不做流式输出、不做取消。

### 7. 产物写入与失败保留

权威结果写入：

```text
summary/summary.json
```

评测结果写入：

```text
summary/evaluations/<model_ref>.json
```

评测关闭时不创建 `summary/evaluations/`。评测开启时不清空目录，只覆盖当前 `candidate_models` 对应文件。所有正式 JSON 都先写临时文件，再原子替换目标路径，避免阶段八读到半成品。

如果主模型或单模型失败，不写也不覆盖 `summary/summary.json`。评测模式下，已成功的非主候选仍写入候选文件，失败候选写失败记录。非主候选失败不影响整体成功；主模型失败导致整体失败并返回退出码 `2`。

### 8. 错误码边界

- `SUMMARY_INPUT_INVALID`：缺规范文本、缺或非法 `domain.json`、领域不在固定表、上游输入不满足总结前置条件。
- `SUMMARY_INPUT_TOO_LARGE`：模型/API 明确返回上下文超限。
- `SUMMARY_SCHEMA_INVALID`：模型输出不是合法纯 JSON object，或字段缺失、类型错误、非法 tag/title/domain_notes。
- `LLM_REQUEST_FAILED`：网络、超时、鉴权、服务端错误或普通非成功响应。
- `CONFIG_INVALID`：模型引用、评测配置、文件名安全字符、API key 环境变量或 provider 配置错误。

`SUMMARY_INPUT_INVALID`、`SUMMARY_INPUT_TOO_LARGE`、`SUMMARY_SCHEMA_INVALID` 和 `LLM_REQUEST_FAILED` 为可恢复业务失败，退出码为 `2`。`CONFIG_INVALID` 退出码为 `1`。

## Risks / Trade-offs

- **模型偶尔输出非纯 JSON** → prompt 明确要求纯 JSON，测试用 fake client 覆盖失败路径；首版不做自动提取，保持行为简单可测。
- **长文本超出真实模型上下文** → 默认不主动截断以利用长上下文模型；API 超限映射为 `SUMMARY_INPUT_TOO_LARGE`，用户可配置 `max_input_chars` 保护。
- **评测模式增加成本和时延** → 只在配置启用时并发调用候选模型；非主候选失败不阻断主路径。
- **不做自动评分导致结果选择仍需人工** → 这是有意边界，阶段七只产出候选，人工线下评测，不把评测系统化。
- **旧评测文件可能残留** → stdout 只返回当前候选路径；不清空目录避免误删人工对比材料。
- **严格 schema 可能导致更多失败** → 失败早暴露 prompt 或模型稳定性问题，避免阶段八基于残缺数据写入 Obsidian。
