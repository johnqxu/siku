## Why

阶段六已经把 Bilibili 视频和网页文章推进到 `domain_ready`，但还没有把规范文本转化为可被后续 Obsidian 入库使用的结构化中文知识总结。阶段七需要补齐文本化后的中文总结能力，并为后续阶段八的 Obsidian 写入提供稳定、可校验、可追溯的 `summary/summary.json`。

## What Changes

- 新增中文总结 pipeline，在规范文本和 `summary/domain.json` 均可用后自动执行。
- 将 `km ingest` 成功链路从 `domain_ready` 推进到 `summary_ready`。
- 新增固定 `summary.json` schema，包含标题、一句话总结、核心观点、关键概念、领域专属笔记、行动启发、后续问题、标签、来源追溯、输入信息、prompt 信息和模型信息。
- 新增领域专属 prompt 资产，按固定领域表选择对应模板，要求模型输出中文纯 JSON object。
- 新增总结任务 LLM 配置，支持 `llm.tasks.summary_generation`、模型级 `timeout_seconds`、模型级 `max_output_tokens` 和 `[summary].max_input_chars`。
- 新增评测模式：按配置并发调用 `candidate_models`，由 `primary_model` 生成权威 `summary/summary.json`，候选结果写入 `summary/evaluations/<model_ref>.json`。
- 评测只保留候选结果文件，不提供评分、排序、manifest、UI 或人工选择流程。
- 新增公开错误码：`SUMMARY_INPUT_INVALID`、`SUMMARY_INPUT_TOO_LARGE`、`SUMMARY_SCHEMA_INVALID`，并沿用 `LLM_REQUEST_FAILED` 和 `CONFIG_INVALID`。
- 新增 `skills/summary-generation/SKILL.md`，为未来 Hermes/Deep Agents 编排声明受控工具边界。
- 阶段七仍不写 Obsidian、不写 SQLite `processed` 记录、不启用 Deep Agents 运行时。

## Capabilities

### New Capabilities

- `summary-generation-pipeline`: 定义规范文本到结构化中文总结的 pipeline、summary schema、prompt 资产、评测模式、产物写入、错误映射和 `summary_ready` 响应。

### Modified Capabilities

- `cli-contract-skeleton`: 成功响应、退出码、公开错误 envelope 和协议测试从 `domain_ready` 推进到 `summary_ready`。
- `local-state-foundation`: 本地配置 schema 增加总结任务、评测配置、输入长度保护和模型级可选调用参数。
- `domain-classification-pipeline`: 领域分类成功后继续进入中文总结 pipeline，而不是停在 `domain_ready`。
- `bilibili-transcript-pipeline`: Bilibili 文本化和领域分类成功后继续进入中文总结 pipeline。
- `web-article-content-pipeline`: 网页正文抽取和领域分类成功后继续进入中文总结 pipeline。
- `url-routing-and-skill-skeleton`: 项目内 skills 骨架增加 `summary-generation` skill。

## Impact

- 影响 Python CLI 主链路、配置解析、LLM client 调用参数、素材仓库 `summary/` 目录写入和 stdout JSON 响应。
- 新增 prompt 资产目录 `prompts/summary/` 与 `skills/summary-generation/SKILL.md`。
- 新增或扩展测试覆盖配置、schema 校验、prompt 资产、单模型总结、评测模式、失败路径、CLI 链路和非目标边界。
- 不新增外部数据库 schema，不写 Obsidian，不引入 Deep Agents 运行时。
