## 1. TDD 测试基线

- [x] 1.1 新增总结配置解析测试，覆盖 `[llm.tasks] summary_generation`、`[summary].max_input_chars`、`[summary.evaluation]`、候选模型、主模型、模型引用不存在和引用名非法。
- [x] 1.2 新增模型级调用参数测试，覆盖 `timeout_seconds`、`max_output_tokens` 的有效值、默认值和非法值。
- [x] 1.3 新增 prompt 资产测试，确认 `prompts/summary/common.md` 和所有领域模板存在。
- [x] 1.4 新增领域模板测试，确认每个模板包含该领域 `domain_notes` 固定字段。
- [x] 1.5 新增 summary schema 成功测试，覆盖合法 summary JSON、系统字段覆盖、`source`、`input`、`prompt` 和模型追溯字段。
- [x] 1.6 新增 summary schema 失败测试，覆盖非纯 JSON、代码块、缺字段、非法 `domain`、非法 `domain_notes`、非法 `tags`、非法 `title` 和非法 `key_concepts`。
- [x] 1.7 新增单模型总结成功测试，确认写入 `summary/summary.json` 并返回 `summary_ready`。
- [x] 1.8 新增评测模式成功测试，确认两个候选模型并发执行，主模型写入权威 summary，候选结果写入 `summary/evaluations/`。
- [x] 1.9 新增非主候选失败测试，确认整体仍成功并写入失败候选记录。
- [x] 1.10 新增主模型失败测试，确认整体失败、不覆盖旧 `summary/summary.json`，并保留评测候选文件。
- [x] 1.11 新增非评测模式失败测试，确认失败时不覆盖旧 `summary/summary.json`。
- [x] 1.12 新增输入失败测试，覆盖缺规范文本、缺 `summary/domain.json`、非法 domain JSON 和固定领域表不匹配，返回 `SUMMARY_INPUT_INVALID`。
- [x] 1.13 新增上下文超限映射测试，确认模型/API 超限错误返回 `SUMMARY_INPUT_TOO_LARGE`。
- [x] 1.14 新增 CLI 链路测试，确认 Bilibili 成功路径从 `domain_ready` 推进到 `summary_ready`。
- [x] 1.15 新增 CLI 链路测试，确认网页文章成功路径从 `domain_ready` 推进到 `summary_ready`。
- [x] 1.16 新增非目标边界测试，确认阶段七不写 Obsidian、不写 SQLite `processed` 记录、不启用 Deep Agents。
- [x] 1.17 新增 summary skill 资产测试，确认 `skills/summary-generation/SKILL.md` 存在并要求使用受控 Python 总结工具。

## 2. 配置与 LLM client 扩展

- [x] 2.1 扩展配置模型，支持 `[llm.tasks] summary_generation`。
- [x] 2.2 扩展 `[summary] max_input_chars`，缺省或 `0` 表示不主动截断。
- [x] 2.3 扩展 `[summary.evaluation] enabled`、`candidate_models` 和 `primary_model`。
- [x] 2.4 校验 `summary_generation`、`candidate_models` 和 `primary_model` 引用存在的 `[llm.models.<ref>]`。
- [x] 2.5 校验 `primary_model` 必须包含在 `candidate_models` 中。
- [x] 2.6 校验评测候选模型引用只包含 `a-z`、`A-Z`、`0-9`、`_` 和 `-`。
- [x] 2.7 扩展模型定义，支持可选 `timeout_seconds`，缺省为 `120`。
- [x] 2.8 扩展模型定义，支持可选 `max_output_tokens`，缺省为 `8192`。
- [x] 2.9 将 `timeout_seconds` 和 `max_output_tokens` 传入 OpenAI-compatible LLM client 调用边界。

## 3. Prompt 资产

- [x] 3.1 新增 `prompts/summary/common.md`，要求中文输出、纯 JSON object、固定 schema 和不可嵌入原文。
- [x] 3.2 新增 `prompts/summary/domains/ai.md`。
- [x] 3.3 新增 `prompts/summary/domains/programming.md`。
- [x] 3.4 新增 `prompts/summary/domains/product.md`。
- [x] 3.5 新增 `prompts/summary/domains/business.md`。
- [x] 3.6 新增 `prompts/summary/domains/learning.md`。
- [x] 3.7 新增 `prompts/summary/domains/psychology.md`。
- [x] 3.8 新增 `prompts/summary/domains/investing.md`。
- [x] 3.9 新增 `prompts/summary/domains/writing.md`。
- [x] 3.10 新增 `prompts/summary/domains/life.md`。
- [x] 3.11 新增 `prompts/summary/domains/recipe.md`。
- [x] 3.12 新增 `prompts/summary/domains/other.md`。
- [x] 3.13 实现 prompt 选择与组装，按领域映射到 `summary.<domain_key>.v1`。

## 4. Summary schema 与校验

- [x] 4.1 新增 summary 内容结果模型，包含 `title`、`one_sentence_summary`、`core_points`、`key_concepts`、`domain_notes`、`actionable_insights`、`questions` 和 `tags`。
- [x] 4.2 新增 summary 系统追溯模型，包含 `schema_version`、`domain`、`model_ref`、`model`、`source`、`input` 和 `prompt`。
- [x] 4.3 实现纯 JSON object 解析，拒绝代码块、解释文本、数组和字符串。
- [x] 4.4 实现固定领域 `domain_notes` 字段表和校验。
- [x] 4.5 实现 `title` 非空和路径非法字符校验。
- [x] 4.6 实现 `tags` 数量、前缀、空值和深层层级校验。
- [x] 4.7 实现 `key_concepts`、`core_points`、`actionable_insights` 和 `questions` 类型校验。
- [x] 4.8 实现系统字段覆盖，忽略模型输出中的系统字段。
- [x] 4.9 新增公开错误 helper：`SUMMARY_INPUT_INVALID`、`SUMMARY_INPUT_TOO_LARGE` 和 `SUMMARY_SCHEMA_INVALID`。

## 5. 总结 pipeline 实现

- [x] 5.1 实现 `generate_summary` 受控 Python tool，读取规范文本和 `summary/domain.json`。
- [x] 5.2 实现 `SUMMARY_INPUT_INVALID` 输入校验，覆盖缺文件、非法 JSON、非法领域和缺必要上下文。
- [x] 5.3 实现单次总结输入策略，支持 `max_input_chars` 主动截断并记录 `input.truncated`。
- [x] 5.4 实现模型/API 上下文超限到 `SUMMARY_INPUT_TOO_LARGE` 的映射。
- [x] 5.5 实现单模型模式，调用 `llm.tasks.summary_generation` 并写入权威 `summary/summary.json`。
- [x] 5.6 实现评测模式，使用 `ThreadPoolExecutor` 并发调用 `candidate_models`。
- [x] 5.7 实现候选结果文件写入 `summary/evaluations/<model_ref>.json`。
- [x] 5.8 实现候选失败记录 JSON，包含 `ok: false`、`model_ref`、`model`、`error_code`、`message` 和 `recoverable`。
- [x] 5.9 实现主模型成功时写入权威 `summary/summary.json`。
- [x] 5.10 实现主模型失败时整体失败且不覆盖旧权威 summary。
- [x] 5.11 实现非主候选失败不阻断主路径。
- [x] 5.12 实现临时文件写入和原子替换。
- [x] 5.13 实现评测关闭时不创建 `summary/evaluations/`。
- [x] 5.14 实现评测开启时只覆盖当前候选文件，不清空评测目录。

## 6. CLI 集成

- [x] 6.1 新增 `summary_ready` 成功响应 builder。
- [x] 6.2 在 Bilibili 成功生成规范文本并完成领域分类后自动调用中文总结 pipeline。
- [x] 6.3 在网页文章成功生成规范正文并完成领域分类后自动调用中文总结 pipeline。
- [x] 6.4 成功时返回 `summary_ready` 和退出码 `0`。
- [x] 6.5 评测模式成功时在 stdout JSON 中包含 `evaluation_dir`。
- [x] 6.6 保持重复来源跳过优先于文本化、领域分类和中文总结 pipeline。
- [x] 6.7 保持文本化或领域分类失败时直接返回对应错误，不调用中文总结。
- [x] 6.8 保持不支持 URL 返回 `UNSUPPORTED_URL` 和退出码 `1`。

## 7. 文档与 skill

- [x] 7.1 新增 `skills/summary-generation/SKILL.md`，记录受控 Python 总结工具、单次总结、评测模式和非目标边界。
- [x] 7.2 更新 README，记录阶段七能力边界、推荐 DeepSeek V4 Pro/Flash 评测配置、`summary_ready` 响应和错误码。
- [x] 7.3 更新 Superpowers 设计文档，记录阶段七中文总结方案、summary schema 和评测配置。
- [x] 7.4 更新配置示例，使用 `deepseek_v4_flash` 和 `deepseek_v4_pro` 模型引用名。

## 8. 验证

- [x] 8.1 运行 `UV_CACHE_DIR=.uv-cache uv --no-config run python -m unittest discover -s tests -v`。
- [x] 8.2 运行 `openspec validate add-summary-generation-pipeline`。
- [x] 8.3 运行 `openspec validate --all`。
- [x] 8.4 检查阶段七 OpenSpec artifacts 不包含占位符、矛盾或未决问题。
