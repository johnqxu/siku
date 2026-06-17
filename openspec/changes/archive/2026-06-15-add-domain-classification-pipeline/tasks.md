## 1. 测试先行

- [x] 1.1 新增 LLM 配置测试，覆盖 `[llm.models.<ref>]`、`[llm.tasks] domain_classification`、引用不存在、缺字段、环境变量缺失和不支持 provider。
- [x] 1.2 新增领域分类 schema 测试，覆盖合法分类结果、非 JSON、缺字段、非法领域和非法 `confidence`。
- [x] 1.3 新增领域分类 pipeline 成功测试，覆盖读取 `canonical/transcript.md` 或 `canonical/content.md`、调用 fake LLM client、写入 `summary/domain.json`。
- [x] 1.4 新增低置信度/模糊内容测试，确认模型返回 `domain: "其他"` 时 pipeline 成功，不因低置信度失败。
- [x] 1.5 新增领域分类失败路径测试，覆盖 `LLM_REQUEST_FAILED` 和 `LLM_SCHEMA_INVALID`。
- [x] 1.6 更新 CLI 协议测试，确认 Bilibili 成功路径从 `transcript_ready` 推进到 `domain_ready`。
- [x] 1.7 更新 CLI 协议测试，确认网页文章成功路径从 `content_ready` 推进到 `domain_ready`。
- [x] 1.8 更新 skills 资产测试，确认 `skills/domain-classification/SKILL.md` 存在并要求使用受控 Python tools。

## 2. 配置、模型与错误码

- [x] 2.1 扩展配置模型，支持 `[llm.models.<ref>]` 和 `[llm.tasks] domain_classification`。
- [x] 2.2 校验领域分类引用的 LLM 模型定义，要求 `provider`、`base_url`、`model`、`api_key_env` 为非空字符串。
- [x] 2.3 校验 `api_key_env` 对应环境变量存在且非空。
- [x] 2.4 限制阶段六首版只接受 `provider = "openai_compatible"`。
- [x] 2.5 新增领域分类结果模型，包含 `taxonomy_version`、`domain`、`confidence`、`reason`、`model_ref` 和 `model`。
- [x] 2.6 新增公开错误码 helper：`LLM_REQUEST_FAILED` 和 `LLM_SCHEMA_INVALID`。
- [x] 2.7 新增 `domain_ready` 成功响应 builder。

## 3. LLM client 与领域分类 tool

- [x] 3.1 实现 OpenAI-compatible LLM client 边界，测试中可注入 fake client。
- [x] 3.2 实现领域分类 prompt，要求模型从固定领域表中选择一个主领域，并用中文输出 `reason`。
- [x] 3.3 实现 `classify_domain` 受控 tool，读取规范文本、调用 LLM client、校验结果并补充追溯字段。
- [x] 3.4 将 LLM 请求异常、超时、非成功 HTTP 状态映射为 `LLM_REQUEST_FAILED`。
- [x] 3.5 将非 JSON、缺字段、非法领域和非法字段类型映射为 `LLM_SCHEMA_INVALID`。
- [x] 3.6 确保阶段六不创建 LangChain Deep Agent，不让 agent 编排分类。

## 4. 领域分类产物

- [x] 4.1 实现 `summary/domain.json` 写入，使用 UTF-8 JSON。
- [x] 4.2 确认 `domain.json` 包含 `taxonomy_version: 1`、`domain`、`confidence`、`reason`、`model_ref` 和 `model`。
- [x] 4.3 确认阶段六不生成 `summary/domain.md`。
- [x] 4.4 确认阶段六不写 SQLite `processed` 记录，也不更新 SQLite `domain` 字段。

## 5. CLI pipeline 集成

- [x] 5.1 在 `bilibili_video` 成功生成 `canonical/transcript.md` 后自动调用领域分类 pipeline。
- [x] 5.2 在 `web_article` 成功生成 `canonical/content.md` 后自动调用领域分类 pipeline。
- [x] 5.3 成功时返回 `domain_ready` 和退出码 `0`。
- [x] 5.4 保持重复来源跳过优先于文本化和领域分类 pipeline。
- [x] 5.5 保持文本化阶段失败时直接返回原有错误，不调用领域分类。
- [x] 5.6 保持 `unsupported` URL 返回 `UNSUPPORTED_URL` 和退出码 `1`。

## 6. Skills 与文档

- [x] 6.1 新增 `skills/domain-classification/SKILL.md`，记录固定领域表、单一主领域、低置信度归入 `其他` 和受控 tool 约束。
- [x] 6.2 更新 README，记录阶段六能力边界、LLM 配置结构、`domain_ready` 响应和错误码。
- [x] 6.3 更新 Superpowers 设计文档，记录阶段六领域分类方案和 LLM 模型引用配置。

## 7. 验证

- [x] 7.1 运行 `UV_CACHE_DIR=.uv-cache uv --no-config run python -m unittest discover -s tests -v`。
- [x] 7.2 运行 `openspec validate add-domain-classification-pipeline`。
- [x] 7.3 运行 `openspec validate --all`。
- [x] 7.4 检查阶段六 OpenSpec artifacts 不包含占位符、矛盾或未决问题。
