## 1. TDD 测试基线

- [x] 1.1 新增 Obsidian renderer 测试，覆盖 frontmatter 固定字段、字符串转义、tags 数组和正文章节结构。
- [x] 1.2 新增 Obsidian renderer 边界测试，确认正文不嵌入完整原文、完整 transcript/content、原始 HTML 或完整 prompt。
- [x] 1.3 新增 safe-title 和文件命名测试，覆盖非法字符移除、空白折叠、80 字符截断、`untitled` fallback 和默认文件名。
- [x] 1.4 新增 note 冲突测试，覆盖同 `source_id` 覆盖、不同 `source_id` 使用 `-<source_id前8位>` 兜底、兜底冲突返回 `OBSIDIAN_WRITE_FAILED`。
- [x] 1.5 新增 Obsidian 写入测试，覆盖 `vault_path` 必须存在、`inbox_dir` 自动创建、不可写 inbox 返回 `OBSIDIAN_WRITE_FAILED`、临时文件原子替换。
- [x] 1.6 新增时间字段测试，覆盖新建 note 的 `created_at` / `updated_at` 和同 `source_id` 覆盖时保留旧 `created_at`。
- [x] 1.7 新增 summary 输入校验测试，覆盖缺失 summary、非法 JSON、`schema_version` 不匹配、source URL 或路径与当前上下文不一致返回 `SUMMARY_INPUT_INVALID`。
- [x] 1.8 新增 SQLite processed 写入测试，覆盖 insert、update、保留旧 `created_at`、刷新 `updated_at`、清空 `error_code` / `error_message`。
- [x] 1.9 新增 SQLite failed 写入测试，覆盖阶段八失败记录 `status = "failed"`，以及 failed 不阻止后续重复来源重试。
- [x] 1.10 新增 SQLite schema 测试，确认阶段八不升级 `PRAGMA user_version` 且不新增 schema 字段。
- [x] 1.11 新增 CLI Bilibili 成功路径测试，确认端到端从 `summary_ready` 推进到 `processed_ready`，写入 note 和 SQLite processed。
- [x] 1.12 新增 CLI 网页文章成功路径测试，确认端到端返回 `processed_ready`，写入 note 和 SQLite processed。
- [x] 1.13 新增 CLI 重复来源测试，确认 `processed` 记录使命中同 URL 时返回 `skipped_existing`，且不重新执行采集、分类、总结或 Obsidian 写入。
- [x] 1.14 新增 CLI 阶段八失败测试，覆盖 `OBSIDIAN_WRITE_FAILED` 和 `INDEX_WRITE_FAILED`，且 `INDEX_WRITE_FAILED` stdout 包含 `note_path`。
- [x] 1.15 新增 CLI 响应字段测试，确认 `processed_ready` 包含最终路径字段且不暴露 `summary_model_ref`、`evaluation_enabled`、`evaluation_dir`、`taxonomy_version` 或 `model_ref`。
- [x] 1.16 新增项目内 skill 测试，确认 `skills/obsidian-write/SKILL.md` 存在并要求使用受控 Python tools，不允许 agent 自行写 Obsidian、SQLite 或重新调用 LLM。

## 2. Obsidian renderer 与命名实现

- [x] 2.1 新增 Obsidian note 数据模型或上下文对象，承载 `source_id`、URL、路径、domain、title、summary 和时间字段。
- [x] 2.2 实现受控 YAML frontmatter 子集渲染，支持字符串和字符串数组，并使用 JSON 风格双引号转义。
- [x] 2.3 实现 Markdown 正文渲染，将 `one_sentence_summary`、`core_points`、`key_concepts`、`domain_notes`、`actionable_insights`、`questions` 和来源素材路径映射到固定章节。
- [x] 2.4 实现正文排除规则，确保不会读取或嵌入完整原文、完整 transcript/content、原始 HTML 或完整 prompt 文本。
- [x] 2.5 实现 `safe-title` 清洗、长度限制和 `untitled` fallback。
- [x] 2.6 实现默认文件名和 `-<source_id前8位>` 兜底文件名生成。
- [x] 2.7 实现已有 note frontmatter `source_id` 和 `created_at` 的轻量读取。

## 3. Obsidian 写入实现

- [x] 3.1 实现 `vault_path` 校验，要求已存在、是目录且可写，失败返回 `CONFIG_INVALID`。
- [x] 3.2 实现 `inbox_dir` 目标目录解析和创建，保留相对路径与禁止 `..` 的既有配置校验。
- [x] 3.3 实现目标 note 路径选择，覆盖同 `source_id`、不同 `source_id` 兜底、兜底冲突错误。
- [x] 3.4 实现 note 临时文件写入和原子替换。
- [x] 3.5 实现同 `source_id` 覆盖时保留旧 `created_at` 并刷新 `updated_at`。
- [x] 3.6 将 Obsidian 写入异常映射为 `OBSIDIAN_WRITE_FAILED`。

## 4. Summary 校验与 SQLite 状态实现

- [x] 4.1 实现阶段八读取并校验 `summary/summary.json`，复用或提取阶段七 summary schema 校验逻辑。
- [x] 4.2 校验 `summary.source.url`、`source.asset_dir`、`source.canonical_text_path` 和 `source.domain_path` 与当前 pipeline 上下文一致。
- [x] 4.3 将阶段八输入校验失败映射为 `SUMMARY_INPUT_INVALID`，且不写 Obsidian note 或 SQLite processed。
- [x] 4.4 扩展 `IngestIndex` 或等价 SQLite 边界，支持写入/更新 `processed` 记录。
- [x] 4.5 扩展 `IngestIndex` 或等价 SQLite 边界，支持阶段八失败时写入 `failed` 记录。
- [x] 4.6 确认 SQLite 写入保留旧 `created_at`、刷新 `updated_at`，并保持 `PRAGMA user_version = 1`。
- [x] 4.7 将 note 已写入后的 SQLite processed 写入失败映射为 `INDEX_WRITE_FAILED`，并让失败响应包含 `note_path`。

## 5. CLI 集成

- [x] 5.1 新增 `processed_ready` response builder，返回 `content_type`、`source_url`、`asset_dir`、`canonical_text_path`、`domain_path`、`summary_path`、`note_path`、`domain` 和 `title`。
- [x] 5.2 保留 `summary_ready` response builder 作为内部阶段结果。
- [x] 5.3 在 Bilibili 成功文本化、领域分类和中文总结之后自动调用 Obsidian note pipeline。
- [x] 5.4 在网页文章成功文本化、领域分类和中文总结之后自动调用 Obsidian note pipeline。
- [x] 5.5 成功时返回 `processed_ready` 和退出码 `0`，不再在 CLI 端到端成功路径返回 `summary_ready`。
- [x] 5.6 确认 `processed_ready` 不输出总结正文、note 正文、规范文本正文或评测字段。
- [x] 5.7 确认 `OBSIDIAN_WRITE_FAILED` 和 `INDEX_WRITE_FAILED` 返回退出码 `2`，`INDEX_WRITE_FAILED` 包含 `note_path`。
- [x] 5.8 确认 `processed` 重复来源跳过优先于文本化、分类、总结和 Obsidian 写入。

## 6. 文档、skills 与规范维护

- [x] 6.1 新增 `skills/obsidian-write/SKILL.md`，记录使用条件、受控 tools、禁止直接写 Obsidian/SQLite、禁止重新调用 LLM 和禁止嵌入原文。
- [x] 6.2 更新 `skills/summary-generation/SKILL.md`，说明中文总结 skill 不负责 Obsidian 写入，后续写入交给 `obsidian-write`。
- [x] 6.3 更新 README，记录阶段八 `processed_ready`、Obsidian note 结构、文件命名、错误码、SQLite processed 语义和阶段八非目标。
- [x] 6.4 更新 Superpowers 设计文档，补充阶段八 Obsidian 写入与 processed 闭环设计。
- [x] 6.5 检查 OpenSpec artifacts 不包含占位符、矛盾或未决问题。

## 7. 验证

- [x] 7.1 运行 `UV_CACHE_DIR=.uv-cache uv --no-config run python -m unittest discover -s tests -v`。
- [x] 7.2 运行 `openspec validate add-obsidian-processed-pipeline`。
- [x] 7.3 运行 `openspec validate --all`。
