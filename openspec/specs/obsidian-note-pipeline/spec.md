# obsidian-note-pipeline Specification

## Purpose
定义从结构化中文总结到 Obsidian Markdown 笔记、SQLite processed 标记和 processed_ready 响应的阶段八闭环。

## Requirements
### Requirement: Obsidian note pipeline 入口
系统 SHALL 在中文总结成功后执行 Obsidian note pipeline，并将端到端成功状态推进到 `processed_ready`。

#### Scenario: summary 后进入 Obsidian note pipeline
- **WHEN** `km ingest` 文本化、领域分类和中文总结均成功，且 `summary/summary.json` 已写入
- **THEN** 系统继续执行 Obsidian note pipeline，而不是在 CLI 端到端成功路径停留在 `summary_ready`

#### Scenario: pipeline 由 Python 确定性编排
- **WHEN** Obsidian note pipeline 执行
- **THEN** 系统通过当前 Python 确定性 pipeline 调用受控 tools，MUST NOT 创建 LangChain Deep Agent 或让 agent 编排写入步骤

#### Scenario: 不重新调用 LLM
- **WHEN** Obsidian note pipeline 执行
- **THEN** 系统 MUST NOT 调用 LLM 重新生成、改写或补充 Obsidian note 内容
### Requirement: summary 输入校验
系统 SHALL 在写入 Obsidian 前校验 `summary/summary.json` 与当前 pipeline 上下文一致。

#### Scenario: summary.json 必须存在且合法
- **WHEN** Obsidian note pipeline 读取 `summary/summary.json`
- **THEN** 该文件 MUST 存在、是合法 JSON object，且包含 `schema_version: 1`

#### Scenario: source url 必须匹配当前来源
- **WHEN** Obsidian note pipeline 校验 `summary/summary.json`
- **THEN** `source.url` MUST 等于当前 `original_url` 或 `normalized_url` 之一

#### Scenario: source 路径必须匹配当前上下文
- **WHEN** Obsidian note pipeline 校验 `summary/summary.json`
- **THEN** `source.asset_dir`、`source.canonical_text_path` 和 `source.domain_path` MUST 与当前 pipeline 路径一致

#### Scenario: summary schema 不合法返回输入错误
- **WHEN** `summary/summary.json` 缺失、不是合法 JSON object、schema version 不匹配、source 上下文不一致，或内容字段不满足 summary schema
- **THEN** 系统返回 `ok: false` 且 `error_code: "SUMMARY_INPUT_INVALID"`，并且 MUST NOT 写 Obsidian note 或 SQLite `processed`
### Requirement: Obsidian Markdown 渲染
系统 SHALL 从 `summary/summary.json` 渲染固定结构的中文 Obsidian Markdown 笔记。

#### Scenario: frontmatter 使用固定 YAML 子集
- **WHEN** 系统渲染 Obsidian note
- **THEN** note MUST 包含 YAML frontmatter，且 frontmatter 只使用字符串和字符串数组

#### Scenario: frontmatter 字段完整
- **WHEN** 系统渲染 Obsidian note
- **THEN** frontmatter 包含 `title`、`source_id`、`source_url`、`content_type`、`domain`、`tags`、`created_at`、`updated_at`、`asset_dir`、`canonical_text`、`domain_path`、`summary_path`、`summary_model_ref` 和 `status`

#### Scenario: frontmatter 字符串安全转义
- **WHEN** frontmatter 字段包含引号、反斜杠、冒号、换行或其他可能破坏 YAML 的字符
- **THEN** 系统使用 JSON 风格双引号字符串转义写入

#### Scenario: 正文使用 summary 内容结构
- **WHEN** 系统渲染 Obsidian note 正文
- **THEN** 正文包含 H1 标题、`一句话摘要`、`核心观点`、`关键概念`、`领域笔记`、`可操作启发`、`值得追问的问题` 和 `来源与素材` 章节

#### Scenario: 关键概念按名称和说明渲染
- **WHEN** `summary/summary.json` 包含 `key_concepts`
- **THEN** 系统将每个概念渲染为包含概念名称和说明的 Markdown 列表项

#### Scenario: domain_notes 按字段顺序渲染
- **WHEN** `summary/summary.json` 包含 `domain_notes`
- **THEN** 系统按 JSON 中字段顺序将每个字段渲染为 `领域笔记` 下的三级标题和对应内容

#### Scenario: tags 不在正文重复渲染
- **WHEN** 系统渲染 Obsidian note
- **THEN** `tags` 只写入 frontmatter，MUST NOT 在正文中重复生成标签列表

#### Scenario: 不嵌入完整原文或 prompt
- **WHEN** 系统渲染 Obsidian note
- **THEN** 正文 MUST NOT 嵌入完整规范文本、完整 transcript、完整网页正文、原始 HTML 或完整 prompt 文本
### Requirement: Obsidian 文件命名
系统 SHALL 使用可读且幂等的 Markdown 文件命名规则。

#### Scenario: 默认文件名使用日期和 safe title
- **WHEN** 系统为新 note 计算文件名
- **THEN** 默认文件名为 `YYYY-MM-DD-safe-title.md`

#### Scenario: safe title 清洗非法字符
- **WHEN** `title` 包含 `/`、`\`、`:`、`*`、`?`、`"`、`<`、`>` 或 `|`
- **THEN** 系统从 `safe-title` 中移除这些字符

#### Scenario: safe title 折叠空白
- **WHEN** `title` 包含连续空白字符
- **THEN** 系统将连续空白折叠成单个 `-`

#### Scenario: safe title 长度限制
- **WHEN** 清洗后的 `safe-title` 超过 80 个字符
- **THEN** 系统将其截断到 80 个字符以内

#### Scenario: safe title 为空时使用 untitled
- **WHEN** `title` 清洗后为空
- **THEN** 系统使用 `untitled` 作为 `safe-title`

#### Scenario: 同名同 source_id 覆盖
- **WHEN** 默认目标 note 已存在，且其 frontmatter `source_id` 等于当前 `source_id`
- **THEN** 系统复用同一路径并整篇覆盖 note

#### Scenario: 同名不同 source_id 使用兜底文件名
- **WHEN** 默认目标 note 已存在，但其 frontmatter `source_id` 不等于当前 `source_id` 或不可识别
- **THEN** 系统使用 `YYYY-MM-DD-safe-title-<source_id前8位>.md` 作为目标文件名

#### Scenario: 兜底文件名冲突且不同 source_id 返回错误
- **WHEN** 兜底目标 note 也已存在，且其 frontmatter `source_id` 不等于当前 `source_id`
- **THEN** 系统返回 `ok: false` 且 `error_code: "OBSIDIAN_WRITE_FAILED"`
### Requirement: Obsidian 写入位置
系统 SHALL 只将 note 写入配置的 Obsidian inbox 目录。

#### Scenario: vault_path 必须存在
- **WHEN** Obsidian note pipeline 执行
- **THEN** `vault_path` MUST 已存在、是目录且可写，否则系统返回 `ok: false` 且 `error_code: "CONFIG_INVALID"`

#### Scenario: inbox_dir 自动创建
- **WHEN** `<vault_path>/<inbox_dir>` 不存在
- **THEN** 系统创建该目录

#### Scenario: inbox_dir 不可写返回写入错误
- **WHEN** `<vault_path>/<inbox_dir>` 无法创建、不是目录或不可写
- **THEN** 系统返回 `ok: false` 且 `error_code: "OBSIDIAN_WRITE_FAILED"`

#### Scenario: 不写领域子目录
- **WHEN** Obsidian note pipeline 写入 note
- **THEN** 系统只写入 `<vault_path>/<inbox_dir>/`，MUST NOT 自动创建领域子目录、移动已有笔记、写入 MOC、写入 backlinks 或写入 daily note
### Requirement: Obsidian note 原子写入
系统 SHALL 通过临时文件和原子替换写入 Obsidian note。

#### Scenario: note 原子替换
- **WHEN** Obsidian note 内容渲染成功
- **THEN** 系统先写入临时文件，再原子替换为目标 `.md` 文件

#### Scenario: 同 source_id 覆盖保留 created_at
- **WHEN** 系统覆盖已有同 `source_id` note，且旧 frontmatter 包含 `created_at`
- **THEN** 新 note 保留旧 `created_at`，并刷新 `updated_at`

#### Scenario: 新建 note 使用当前时间
- **WHEN** 系统创建新的 Obsidian note
- **THEN** `created_at` 和 `updated_at` 使用当前本地时区 ISO 8601 时间

#### Scenario: 写入失败返回结构化错误
- **WHEN** note 临时文件写入、原子替换或目标路径处理失败
- **THEN** 系统返回 `ok: false` 且 `error_code: "OBSIDIAN_WRITE_FAILED"`
### Requirement: SQLite processed 标记
系统 SHALL 在 Obsidian note 写入成功后将来源记录写入或更新为 `processed`。

#### Scenario: processed 记录字段
- **WHEN** Obsidian note 写入成功
- **THEN** 系统向 `sources` 写入或更新 `id`、`normalized_url`、`original_url`、`content_type`、`domain`、`title`、`note_path`、`asset_dir`、`created_at`、`updated_at`、`status`、`error_code` 和 `error_message`

#### Scenario: processed 状态清空错误
- **WHEN** 系统成功写入 SQLite processed 记录
- **THEN** `status` 为 `processed`，且 `error_code` 和 `error_message` 为 null

#### Scenario: 已有记录保留 created_at
- **WHEN** `sources` 中已存在同一 `id` 或 `normalized_url` 的记录
- **THEN** 系统保留原 `created_at` 并刷新 `updated_at`

#### Scenario: SQLite schema 不升级
- **WHEN** 阶段八写入 processed 记录
- **THEN** 系统继续使用 `PRAGMA user_version = 1`，MUST NOT 迁移或新增 SQLite 字段

#### Scenario: SQLite 写入失败返回 index 错误
- **WHEN** Obsidian note 已写入成功但 SQLite processed 记录写入失败
- **THEN** 系统返回 `ok: false` 且 `error_code: "INDEX_WRITE_FAILED"`，并在 stdout JSON 中包含已写入 note 的 `note_path`

#### Scenario: index 失败记录 failed
- **WHEN** 阶段八 Obsidian 写入或 SQLite processed 写入失败且 SQLite 仍可写入失败上下文
- **THEN** 系统将该来源记录为 `status: "failed"`，并写入 `error_code`、`error_message`、`asset_dir` 和已知字段

#### Scenario: failed 不阻止重试
- **WHEN** `sources` 表存在同一 `normalized_url` 且 `status = "failed"` 的记录
- **THEN** 系统 MUST NOT 将该来源视为已处理重复来源，下一次请求仍可重新执行完整 pipeline
### Requirement: processed_ready 响应
系统 SHALL 在 Obsidian note 和 SQLite processed 记录均写入成功后返回 `processed_ready`。

#### Scenario: processed_ready 成功响应
- **WHEN** Obsidian note pipeline 成功写入 note 并标记 SQLite processed
- **THEN** stdout JSON 包含 `ok: true`、`status: "processed_ready"`、`content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path`、`note_path`、`domain` 和 `title`

#### Scenario: processed_ready 不暴露评测字段
- **WHEN** 系统返回 `processed_ready`
- **THEN** stdout JSON MUST NOT 包含 `summary_model_ref`、`evaluation_enabled`、`evaluation_dir`、`taxonomy_version` 或 `model_ref`

#### Scenario: processed_ready 不输出正文
- **WHEN** 系统返回 `processed_ready`
- **THEN** stdout JSON MUST NOT 嵌入 Obsidian note 正文、`summary/summary.json` 正文内容或规范文本正文
### Requirement: 阶段八错误码
系统 SHALL 为 Obsidian note pipeline 提供稳定公开错误码。

#### Scenario: Obsidian 写入失败可恢复
- **WHEN** Obsidian note pipeline 因 inbox 创建、note 写入、原子替换或不可安全处理的路径冲突失败
- **THEN** 系统返回 `ok: false`、`error_code: "OBSIDIAN_WRITE_FAILED"`、`recoverable: true`，且退出码为 `2`

#### Scenario: SQLite processed 写入失败可恢复
- **WHEN** Obsidian note 已写入但 SQLite processed 写入失败
- **THEN** 系统返回 `ok: false`、`error_code: "INDEX_WRITE_FAILED"`、`recoverable: true`、`note_path`，且退出码为 `2`

#### Scenario: vault 配置错误返回 CONFIG_INVALID
- **WHEN** `vault_path` 不存在、不是目录或不可写
- **THEN** 系统返回 `ok: false`、`error_code: "CONFIG_INVALID"`，且退出码为 `1`
### Requirement: obsidian-write skill 资产
系统 SHALL 维护项目内 Obsidian 写入 skill 文件，供未来 Hermes/Deep Agents 编排复用。

#### Scenario: obsidian-write skill 文件存在
- **WHEN** 检查仓库内 skill 资产
- **THEN** `skills/obsidian-write/SKILL.md` 存在，并说明只在 `summary/summary.json` 已存在且校验通过后使用

#### Scenario: skill 指向受控 tools
- **WHEN** 阅读 `skills/obsidian-write/SKILL.md`
- **THEN** skill 文件 MUST 指示 agent 使用 `render_obsidian_note`、`write_obsidian_note`、`mark_source_processed` 或等价受控 Python tools

#### Scenario: skill 不直接执行副作用
- **WHEN** 阅读 `skills/obsidian-write/SKILL.md`
- **THEN** skill 文件 MUST 禁止 agent 自行拼 Markdown 写入 Obsidian、自行更新 SQLite、把原文或完整 transcript 塞进正文，或重新调用 LLM 生成笔记
### Requirement: Obsidian note pipeline 测试替身
系统 SHALL 使用单元测试和 CLI 契约测试验证 Obsidian note pipeline。

#### Scenario: 渲染测试覆盖 note 结构
- **WHEN** 测试套件运行
- **THEN** 它验证 frontmatter、正文章节、字段转义、正文不嵌入原文或 prompt

#### Scenario: 命名测试覆盖冲突规则
- **WHEN** 测试套件运行
- **THEN** 它验证 safe-title 清洗、空标题 fallback、长度限制、同 `source_id` 覆盖和不同 `source_id` 兜底

#### Scenario: 写入测试覆盖原子行为
- **WHEN** 测试套件运行
- **THEN** 它验证 inbox 创建、临时文件原子替换、同 `source_id` 覆盖保留 `created_at`

#### Scenario: SQLite 测试覆盖 processed 和 failed
- **WHEN** 测试套件运行
- **THEN** 它验证 processed 写入、`INDEX_WRITE_FAILED`、failed 不阻止重试，以及 SQLite schema version 不升级

#### Scenario: CLI 测试覆盖端到端 processed_ready
- **WHEN** 测试套件运行
- **THEN** 它验证 Bilibili 和网页文章成功路径返回 `processed_ready`，写入 Obsidian note，并使重复 URL 返回 `skipped_existing`
