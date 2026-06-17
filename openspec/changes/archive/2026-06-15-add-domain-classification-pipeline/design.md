## Context

当前系统已经完成 CLI 契约、本地状态基础、URL 路由、Bilibili 视频文本化和网页文章文本化。阶段四和阶段五分别产出 `canonical/transcript.md` 与 `canonical/content.md`，但都明确不执行领域分类、总结或 Obsidian 写入。

阶段六的目标是把领域分类作为独立基础层落稳。分类结果是后续总结提示词选择、Obsidian 标签、frontmatter 和长期查询的重要输入。用户已确认本阶段采用方案 B：只做领域分类，不做总结；分类只允许一个主领域；低置信度归入 `其他`；使用受控 LLM client，不接入 Deep Agents 运行时。

## Goals / Non-Goals

**Goals:**

- 从阶段四/五生成的规范文本中识别一个主领域。
- 使用固定领域表和 `taxonomy_version: 1` 保证分类结果可追溯。
- 使用集中式 LLM 模型定义和任务引用，让不同环节可选择不同模型。
- 通过 OpenAI-compatible 受控 LLM client 调用远程模型。
- 校验模型响应 schema，并把分类结果写入 `summary/domain.json`。
- 在 `km ingest` 中由 Python 确定性 pipeline 自动接在文本化之后执行，成功返回 `domain_ready`。
- 新增 `skills/domain-classification/SKILL.md`，为未来 Deep Agents 编排保留指令资产。

**Non-Goals:**

- 不生成中文总结，不选择总结模板，不写 `summary/summary.json`。
- 不写 Obsidian 笔记，不生成最终 `created` 响应。
- 不写 SQLite `processed` 记录，也不在本阶段更新 SQLite `domain` 字段。
- 不接入 LangChain Deep Agents 运行时，不让 agent 编排分类。
- 不生成 `summary/domain.md`。
- 不支持多主领域、辅助领域或自由标签。
- 不实现复杂重试、模型 fallback 或多模型投票。

## Decisions

### 1. 阶段六只做单一主领域分类

本阶段只从固定领域表中选择一个主领域：

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

不输出辅助领域。这样后续总结模板选择和 Obsidian 标签生成都有明确输入，避免阶段六演变成自由标签系统。

### 2. 低置信度归入 `其他`

分类必须成功选择一个领域。内容跨领域、证据不足或模型置信度较低时，输出 `domain: "其他"`，并在 `reason` 中说明原因。只有 LLM 请求失败或响应 schema 不合法时才返回错误。

这个选择优先保证自动化 CLI 的可推进性。严格阈值失败会让大量模糊内容卡在分类阶段，且对后续总结阶段帮助有限。

### 2.1 分类输入长度控制

阶段六分类 prompt 只使用规范文本前 12000 个字符。超长文本会在 prompt 中明确说明已经截断，避免长视频转写稿或长网页正文直接触发远程模型上下文上限，也控制单次分类成本。

阶段六不把截断信息写入 `domain.json`，因为 `domain.json` 只表达模型分类结果和模型追溯字段。后续如果需要更强可审计性，可以在分类产物中增加输入摘要或截断元数据。

### 3. 使用集中式 LLM 模型定义和任务引用

配置采用两层结构：

```toml
[llm.models.deepseek_flash]
provider = "openai_compatible"
base_url = "https://api.deepseek.com/v1"
model = "deepseek-v4-flash"
api_key_env = "DEEPSEEK_API_KEY"

[llm.models.gpt_mini]
provider = "openai_compatible"
base_url = "https://api.openai.com/v1"
model = "gpt-4.1-mini"
api_key_env = "OPENAI_API_KEY"

[llm.tasks]
domain_classification = "deepseek_flash"
```

`llm.models` 集中定义模型，`llm.tasks` 为每个业务环节选择模型引用。阶段六只要求 `domain_classification` 引用存在且有效；后续总结可以复用同一结构选择其他模型。

### 4. 首版只支持 `openai_compatible`

OpenAI 和 DeepSeek 都可以走 OpenAI-compatible chat completions 风格接口。本阶段不引入 provider plugin 系统，只校验 `provider = "openai_compatible"`。不支持的 provider 返回 `CONFIG_INVALID`。

这样既满足当前模型配置需求，也避免过早抽象。

### 5. 当前由 Python 确定性 pipeline 编排

阶段六自动接在文本化之后执行：

```text
bilibili_video:
  transcript pipeline -> domain classification -> domain_ready

web_article:
  content pipeline -> domain classification -> domain_ready
```

这不是 Deep Agents 编排。当前阶段仍由 `km ingest` 源代码按固定顺序调用受控 tools。未来接入 Deep Agents 后，Deep Agent 可以调用同一个 `classify_domain` tool；副作用仍由 Python tools 执行。

### 6. `domain.json` 是唯一分类产物

阶段六只写：

```text
summary/domain.json
```

结构为：

```json
{
  "taxonomy_version": 1,
  "domain": "AI",
  "confidence": 0.86,
  "reason": "内容主要讨论大模型 Agent 架构和工具调用。",
  "model_ref": "deepseek_flash",
  "model": "deepseek-v4-flash"
}
```

不生成 `domain.md`。人类可读内容留给后续 Obsidian 笔记阶段。

### 7. 错误码拆分为请求失败和 schema 失败

- `LLM_REQUEST_FAILED`: 网络、超时、鉴权、远程服务错误或非成功 HTTP 状态。
- `LLM_SCHEMA_INVALID`: 模型返回非 JSON、缺字段、字段类型错误、`domain` 不在固定领域表中、`confidence` 不可解析为有限数字。

两者都是可恢复处理失败，退出码为 `2`。

## Risks / Trade-offs

- LLM 分类不稳定 -> 固定领域表、严格 schema 校验和 `taxonomy_version` 降低长期不一致风险。
- 低置信度归入 `其他` 可能损失细分信息 -> 后续可以通过重新分类或人工整理补充，但自动化 pipeline 不会被模糊内容阻塞。
- 长文本截断可能遗漏后半部分的主领域线索 -> 当前阶段优先保证自动化成功率和成本可控；后续可演进为分块投票或正文摘要后再分类。
- 不写 SQLite `domain` 字段会让阶段性分类结果只存在文件中 -> 保持索引语义干净，等 Obsidian 写入成功时再写完整 `processed` 记录。
- OpenAI-compatible 接口在不同厂商之间可能有细节差异 -> 阶段六只使用最小 chat completions 能力，并通过 fake LLM client 做单元测试。
- 自动接在文本化之后会改变成功响应状态 -> 通过 CLI 契约 delta spec 和测试明确 `domain_ready` 是新的阶段性成功。
