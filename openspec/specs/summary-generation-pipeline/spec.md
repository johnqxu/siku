# summary-generation-pipeline Specification

## Purpose
TBD - created by archiving change add-summary-generation-pipeline. Update Purpose after archive.
## Requirements
### Requirement: 中文总结 pipeline 入口
系统 SHALL 为已完成领域分类的新来源执行中文总结 pipeline，并在中文总结成功后继续执行 Obsidian processed pipeline。

#### Scenario: Bilibili domain 后进入总结
- **WHEN** `km ingest` 请求路由为 `bilibili_video`，Bilibili transcript pipeline 成功生成 `canonical/transcript.md`，且领域分类 pipeline 成功生成 `summary/domain.json`
- **THEN** 系统继续执行中文总结 pipeline，而不是停在 `domain_ready`

#### Scenario: 网页 domain 后进入总结
- **WHEN** `km ingest` 请求路由为 `web_article`，网页文章 content pipeline 成功生成 `canonical/content.md`，且领域分类 pipeline 成功生成 `summary/domain.json`
- **THEN** 系统继续执行中文总结 pipeline，而不是停在 `domain_ready`

#### Scenario: 总结成功后进入 Obsidian processed pipeline
- **WHEN** 中文总结 pipeline 产出 `summary/summary.json`
- **THEN** 系统继续执行 Obsidian note pipeline，并在成功时返回 `processed_ready`

#### Scenario: pipeline 不执行 Deep Agents 编排
- **WHEN** 中文总结 pipeline 和 Obsidian note pipeline 均成功
- **THEN** 系统 MUST NOT 启用 Deep Agents 端到端编排
### Requirement: summary schema
系统 SHALL 使用固定 schema 版本 1 写入结构化中文总结。

#### Scenario: summary.json 包含固定字段
- **WHEN** 中文总结成功
- **THEN** `summary/summary.json` 包含 `schema_version`、`domain`、`title`、`one_sentence_summary`、`core_points`、`key_concepts`、`domain_notes`、`actionable_insights`、`questions`、`tags`、`source`、`input`、`prompt`、`model_ref` 和 `model`

#### Scenario: schema version 为 1
- **WHEN** 中文总结成功
- **THEN** `summary/summary.json` 包含 `schema_version: 1`

#### Scenario: 系统字段由本地上下文覆盖
- **WHEN** 模型输出包含 `schema_version`、`domain`、`model_ref`、`model`、`source`、`input` 或 `prompt`
- **THEN** 系统忽略模型中的这些字段，并使用本地上下文重写

#### Scenario: source 字段不嵌入原文
- **WHEN** `summary/summary.json` 被写入
- **THEN** `source` 包含 `url`、`content_type`、`asset_dir`、`canonical_text_path` 和 `domain_path`，且 MUST NOT 嵌入规范文本全文或原始 HTML

#### Scenario: input 字段记录输入策略
- **WHEN** `summary/summary.json` 被写入
- **THEN** `input` 包含 `canonical_text_path`、`domain_path`、`strategy: "single_pass"`、`truncated` 和 `max_input_chars`

#### Scenario: prompt 字段记录 prompt 元数据
- **WHEN** `summary/summary.json` 被写入
- **THEN** `prompt` 包含 `prompt_id` 和 `domain`，且 MUST NOT 嵌入完整 prompt 文本
### Requirement: 领域专属 domain_notes
系统 SHALL 按主领域要求 `domain_notes` 包含固定字段表。

#### Scenario: AI 领域字段
- **WHEN** `domain` 为 `AI`
- **THEN** `domain_notes` MUST 包含 `核心问题`、`模型或方法`、`工具或系统`、`数据或评测`、`工作流影响`、`能力边界` 和 `可复现说明`

#### Scenario: 编程领域字段
- **WHEN** `domain` 为 `编程`
- **THEN** `domain_notes` MUST 包含 `问题背景`、`技术机制`、`工具或框架`、`实现细节`、`调试与验证`、`性能或安全` 和 `适用边界`

#### Scenario: 产品领域字段
- **WHEN** `domain` 为 `产品`
- **THEN** `domain_notes` MUST 包含 `用户痛点`、`使用场景`、`产品假设`、`关键功能`、`工作流影响`、`指标或反馈` 和 `风险`

#### Scenario: 商业领域字段
- **WHEN** `domain` 为 `商业`
- **THEN** `domain_notes` MUST 包含 `商业模式`、`目标用户`、`价值主张`、`增长路径`、`成本结构`、`竞争与壁垒` 和 `风险`

#### Scenario: 学习领域字段
- **WHEN** `domain` 为 `学习`
- **THEN** `domain_notes` MUST 包含 `学习目标`、`方法步骤`、`适用场景`、`练习设计`、`反馈机制`、`常见误区` 和 `复盘方式`

#### Scenario: 心理学领域字段
- **WHEN** `domain` 为 `心理学`
- **THEN** `domain_notes` MUST 包含 `核心概念`、`机制解释`、`证据或论证`、`适用场景`、`干预方法`、`局限` 和 `伦理风险`

#### Scenario: 投资领域字段
- **WHEN** `domain` 为 `投资`
- **THEN** `domain_notes` MUST 包含 `核心论点`、`关键假设`、`资产或标的`、`风险因素`、`估值或价格`、`需要监控的信号` 和 `反方观点`

#### Scenario: 写作领域字段
- **WHEN** `domain` 为 `写作`
- **THEN** `domain_notes` MUST 包含 `主题`、`论证结构`、`表达技巧`、`素材使用`、`叙事节奏`、`可复用模式` 和 `修改建议`

#### Scenario: 生活领域字段
- **WHEN** `domain` 为 `生活`
- **THEN** `domain_notes` MUST 包含 `具体情境`、`核心原则`、`行动步骤`、`工具或资源`、`注意事项`、`风险` 和 `可持续做法`

#### Scenario: 菜谱领域字段
- **WHEN** `domain` 为 `菜谱`
- **THEN** `domain_notes` MUST 包含 `菜品特点`、`食材`、`步骤`、`时间与火候`、`技巧说明`、`替代方案` 和 `失败排查`

#### Scenario: 其他领域字段
- **WHEN** `domain` 为 `其他`
- **THEN** `domain_notes` MUST 包含 `主题`、`背景`、`关键信息`、`适用场景`、`注意事项` 和 `延伸方向`

#### Scenario: 原文未说明字段
- **WHEN** 原文没有提供某个 `domain_notes` 字段的信息
- **THEN** 模型 SHALL 输出字符串 `原文未明确说明`
### Requirement: prompt 资产与版本
系统 SHALL 使用项目内 prompt 资产生成中文总结请求。

#### Scenario: common prompt 存在
- **WHEN** 检查总结 prompt 资产
- **THEN** `prompts/summary/common.md` 存在，并要求模型只输出纯 JSON object

#### Scenario: 每个领域模板存在
- **WHEN** 检查总结 prompt 资产
- **THEN** `prompts/summary/domains/` 下存在 `ai.md`、`programming.md`、`product.md`、`business.md`、`learning.md`、`psychology.md`、`investing.md`、`writing.md`、`life.md`、`recipe.md` 和 `other.md`

#### Scenario: 领域模板包含固定字段
- **WHEN** 检查某个领域模板
- **THEN** 模板包含该领域 `domain_notes` 必需字段

#### Scenario: prompt_id 使用稳定版本
- **WHEN** 系统选择总结 prompt
- **THEN** `prompt_id` 使用 `summary.<domain_key>.v1` 格式
### Requirement: 单次总结输入策略
系统 SHALL 对完整规范文本执行单次总结。

#### Scenario: 默认不主动截断
- **WHEN** `[summary].max_input_chars` 缺省或等于 `0`
- **THEN** 系统将完整规范文本交给总结模型，并记录 `input.truncated: false`

#### Scenario: 显式配置主动截断
- **WHEN** `[summary].max_input_chars` 大于 `0` 且规范文本长度超过该值
- **THEN** 系统只把前 `max_input_chars` 个字符交给总结模型，并记录 `input.truncated: true`

#### Scenario: 上下文超限返回公开错误
- **WHEN** 模型或 API 明确返回上下文超限
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_INPUT_TOO_LARGE"`
### Requirement: summary schema 校验
系统 SHALL 严格校验模型返回的总结 JSON。

#### Scenario: 只接受纯 JSON object
- **WHEN** 模型返回纯 JSON object
- **THEN** 系统解析并继续 schema 校验

#### Scenario: 拒绝代码块或混合文本
- **WHEN** 模型返回 Markdown 代码块、前后解释文本、数组或字符串
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_SCHEMA_INVALID"`

#### Scenario: 缺少必需字段返回 schema 错误
- **WHEN** 模型输出缺少任一内容必需字段
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_SCHEMA_INVALID"`

#### Scenario: domain 不一致返回 schema 错误
- **WHEN** 模型输出的 `domain` 与 `summary/domain.json` 的主领域不一致
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_SCHEMA_INVALID"`

#### Scenario: domain_notes 缺字段返回 schema 错误
- **WHEN** 模型输出的 `domain_notes` 缺少当前领域固定字段
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_SCHEMA_INVALID"`

#### Scenario: title 非法返回 schema 错误
- **WHEN** 模型输出的 `title` 不是非空字符串，或包含 `/`、`\`、`:`、`*`、`?`、`"`、`<`、`>`、`|`
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_SCHEMA_INVALID"`

#### Scenario: tags 非法返回 schema 错误
- **WHEN** `tags` 超过 5 个、包含空字符串、包含不支持前缀或出现第二个 `/`
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_SCHEMA_INVALID"`

#### Scenario: 数组数量不做硬限制
- **WHEN** `key_concepts`、`core_points`、`actionable_insights` 或 `questions` 的数量低于 prompt 建议值
- **THEN** 只要字段类型和元素结构合法，系统接受该结果
### Requirement: 评测模式
系统 SHALL 支持配置驱动的候选模型并发总结。

#### Scenario: 非评测模式使用 summary_generation
- **WHEN** `[summary.evaluation]` 缺省或 `enabled = false`
- **THEN** 系统只调用 `[llm.tasks] summary_generation` 引用的模型，并将成功结果写入 `summary/summary.json`

#### Scenario: 评测模式要求候选和主模型
- **WHEN** `[summary.evaluation] enabled = true`
- **THEN** 配置 MUST 包含非空 `candidate_models` 和 `primary_model`，且 `primary_model` MUST 在 `candidate_models` 中

#### Scenario: 候选模型并发执行
- **WHEN** 评测模式启用
- **THEN** 系统并发调用 `candidate_models` 中的每个模型引用

#### Scenario: 主模型写入权威 summary
- **WHEN** 评测模式启用且 `primary_model` 成功
- **THEN** 系统将主模型结果写入 `summary/summary.json`

#### Scenario: 候选结果写入 evaluations
- **WHEN** 评测模式启用
- **THEN** 每个候选模型的成功结果或失败记录写入 `summary/evaluations/<model_ref>.json`

#### Scenario: 非主候选失败不阻断主路径
- **WHEN** 评测模式启用，`primary_model` 成功，但一个或多个非主候选失败
- **THEN** 系统仍返回 `summary_ready`，并为失败候选写入错误记录

#### Scenario: 主模型失败导致整体失败
- **WHEN** 评测模式启用且 `primary_model` 失败
- **THEN** 系统返回 `ok: false`，不写也不覆盖 `summary/summary.json`，并保留候选评测文件

#### Scenario: 评测关闭不创建目录
- **WHEN** 评测模式关闭
- **THEN** 系统 MUST NOT 创建 `summary/evaluations/` 目录

#### Scenario: 评测不生成系统化评估
- **WHEN** 评测模式启用
- **THEN** 系统 MUST NOT 生成评分、排序、manifest、UI 或人工选择记录
### Requirement: summary 产物写入
系统 SHALL 使用原子写入方式保存总结产物。

#### Scenario: summary.json 原子替换
- **WHEN** 权威总结 schema 校验成功
- **THEN** 系统先写入临时文件，再原子替换为 `summary/summary.json`

#### Scenario: 失败不覆盖旧 summary
- **WHEN** 单模型模式失败，或评测模式下主模型失败
- **THEN** 系统 MUST NOT 覆盖已有 `summary/summary.json`

#### Scenario: 评测目录不清空
- **WHEN** 评测模式启用且 `summary/evaluations/` 已存在
- **THEN** 系统只覆盖本次 `candidate_models` 对应的文件，MUST NOT 清空整个目录

#### Scenario: 重复运行重新生成 summary
- **WHEN** 同一来源在未写 SQLite `processed` 前再次运行到中文总结阶段
- **THEN** 系统重新生成并在成功校验后覆盖正式总结产物
### Requirement: summary_ready 响应
系统 SHALL 保留中文总结成功响应 builder 作为内部阶段结果，但 `km ingest` 端到端成功路径 SHALL 在 Obsidian processed pipeline 成功后返回 `processed_ready`。

#### Scenario: summary_ready 成功响应 builder
- **WHEN** 中文总结 pipeline 成功写入 `summary/summary.json`
- **THEN** 内部响应 builder 可生成包含 `ok: true`、`status: "summary_ready"`、`content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path`、`domain`、`title`、`summary_model_ref` 和 `evaluation_enabled` 的阶段性响应

#### Scenario: 评测响应 builder 包含 evaluation_dir
- **WHEN** 评测模式启用且中文总结成功
- **THEN** 内部 `summary_ready` 响应 builder 可包含 `evaluation_dir`

#### Scenario: km ingest 不停在 summary_ready
- **WHEN** `km ingest` 文本化、领域分类、中文总结和 Obsidian note pipeline 均成功
- **THEN** stdout JSON 返回 `processed_ready`，而不是 `summary_ready`

#### Scenario: summary_ready 不输出总结正文
- **WHEN** 内部系统生成 `summary_ready`
- **THEN** 该响应 MUST NOT 嵌入 `summary/summary.json` 的正文内容

#### Scenario: summary_ready 不表示完整知识笔记完成
- **WHEN** 内部系统生成 `summary_ready`
- **THEN** 该响应只表示中文总结完成，不表示 Obsidian 笔记或 SQLite `processed` 记录已经完成
### Requirement: summary generation skill 资产
系统 SHALL 维护项目内中文总结 skill 文件，供未来 Hermes/Deep Agents 编排复用。

#### Scenario: summary-generation skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/summary-generation/SKILL.md` 存在，并说明中文总结必须通过受控 Python 总结工具执行

#### Scenario: skill 不直接执行副作用
- **WHEN** 阅读 `skills/summary-generation/SKILL.md`
- **THEN** skill 文件 MUST 指示 agent 不直接调用 LLM、不直接写 Obsidian、不写 SQLite `processed` 记录、不做评测评分或排序、不启用 Deep Agents 运行时编排；Obsidian 写入必须交给 `obsidian-write` skill 对应的受控 tools
### Requirement: summary 测试替身
系统 SHALL 使用测试替身验证中文总结 pipeline，不依赖真实 LLM 网络调用。

#### Scenario: 单元测试使用 fake LLM client
- **WHEN** 单元测试运行
- **THEN** 中文总结请求使用 fake LLM client 或 fixture 响应，而不是访问真实远程模型

#### Scenario: 单元测试覆盖成功路径
- **WHEN** 单元测试运行
- **THEN** 它验证 Bilibili 和网页文本化加领域分类成功后继续写入 `summary/summary.json`，并由端到端 CLI 继续返回 `processed_ready`

#### Scenario: 单元测试覆盖失败路径
- **WHEN** 单元测试运行
- **THEN** 它验证 `SUMMARY_INPUT_INVALID`、`SUMMARY_INPUT_TOO_LARGE`、`SUMMARY_SCHEMA_INVALID` 和 `LLM_REQUEST_FAILED`
