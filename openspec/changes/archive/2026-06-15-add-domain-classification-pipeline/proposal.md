## Why

阶段四和阶段五已经能把 Bilibili 视频和网页文章统一转换为可供后续处理的规范文本，但后续中文总结、Obsidian 标签和领域模板选择仍缺少稳定的领域分类基础。阶段六需要先把“规范文本 -> 单一主领域”的能力独立落稳，避免把分类和总结耦合在同一个阶段里。

## What Changes

- 新增领域分类 pipeline：读取 `canonical/transcript.md` 或 `canonical/content.md`，调用受控 LLM client，从固定领域表中选择一个主领域。
- 固定领域表版本为 `taxonomy_version: 1`，领域只能是 `AI`、`编程`、`产品`、`商业`、`学习`、`心理学`、`投资`、`写作`、`生活`、`菜谱`、`其他`。
- 低置信度、跨领域或证据不足时不失败，而是归入 `其他`，并在 `reason` 中说明原因。
- 新增集中式 LLM 配置模型：`[llm.models.<ref>]` 定义模型，`[llm.tasks] domain_classification = "<ref>"` 选择分类任务使用的模型。
- 首版 LLM provider 只支持 `openai_compatible`，用于兼容 OpenAI、DeepSeek 等 OpenAI-compatible API。
- 领域分类结果写入 `summary/domain.json`，不生成 `summary/domain.md`。
- `domain.json` 记录 `taxonomy_version`、`domain`、`confidence`、`reason`、`model_ref` 和实际 `model`。
- 更新 `km ingest`：Bilibili transcript 或网页 content 成功后，由当前 Python 确定性 pipeline 自动继续执行领域分类，并返回 `domain_ready`。
- 新增公开错误码 `LLM_REQUEST_FAILED` 和 `LLM_SCHEMA_INVALID`，分别表示远程模型调用失败和模型响应 schema 不合法。
- 新增项目内 `skills/domain-classification/SKILL.md`，作为未来 Hermes/Deep Agents 使用的指令资产，但本阶段不接入 LangChain Deep Agents 运行时。
- 不实现中文总结、Obsidian 写入、SQLite `processed` 记录写入、SQLite `domain` 字段更新或 Deep Agents 端到端编排。

## Capabilities

### New Capabilities

- `domain-classification-pipeline`: 定义从规范文本到单一主领域分类结果的处理能力，包括固定领域表、LLM 配置引用、受控 LLM 调用、schema 校验、`summary/domain.json` 输出和 `domain_ready` 响应。

### Modified Capabilities

- `cli-contract-skeleton`: 扩展合法请求成功响应和错误码，使文本化成功后继续执行领域分类并返回 `domain_ready`。
- `local-state-foundation`: 扩展配置 schema，支持集中式 LLM 模型定义和任务引用。
- `bilibili-transcript-pipeline`: 将 Bilibili transcript 成功后的下一步从“停止在 `transcript_ready`”调整为自动进入领域分类。
- `web-article-content-pipeline`: 将网页 content 成功后的下一步从“停止在 `content_ready`”调整为自动进入领域分类。
- `url-routing-and-skill-skeleton`: 扩展项目内 skills 骨架，加入 `skills/domain-classification/SKILL.md`。

## Impact

- 影响 `km ingest` 的 `bilibili_video` 和 `web_article` 成功路径：成功状态从阶段四/五的 `transcript_ready` / `content_ready` 推进到阶段六的 `domain_ready`。
- 新增 LLM 配置解析与校验、OpenAI-compatible HTTP client、领域分类模型、分类 prompt、schema 校验和 `summary/domain.json` 写入。
- 新增或更新错误模型、CLI 响应模型和协议测试。
- 可能新增运行时依赖或使用已有 `httpx` 作为 LLM HTTP client；依赖仍通过 uv 管理。
- 当前仍由 Python 源代码确定性编排；Deep Agents 只在 skills 资产层预留，不进入运行时。
