## Context

当前 `km ingest` 已完成从 URL 到规范文本、领域分类和中文总结的确定性 pipeline。阶段七成功时，系统会在素材仓库中写入 `summary/summary.json` 并返回 `summary_ready`。这个状态只说明总结产物已经生成，不代表 Obsidian 笔记已经可读，也不代表 SQLite `sources` 已记录为 `processed`。

阶段八要补齐知识管理工具的首个端到端闭环：将可信的 `summary/summary.json` 渲染成 Obsidian Markdown，写入 `vault_path/inbox_dir`，再把 `sources` 表标记为 `processed`。这一步副作用强、契约清晰，仍由 Python 确定性 pipeline 编排；LangChain Deep Agents 运行时留到后续阶段。

相关约束：

- 文档、规范和用户可见内容使用中文；代码标识、JSON 字段、错误码和路径字段保持原文。
- Obsidian 正文不得嵌入完整原文、完整 transcript/content 或完整 prompt。
- 素材仓库仍位于 Obsidian vault 外部，Obsidian 笔记只引用原始链接和素材绝对路径。
- SQLite 现有 `sources` schema 已包含阶段八所需字段，本阶段不升级 `PRAGMA user_version`。

## Goals / Non-Goals

**Goals:**

- 将 CLI 端到端成功状态从 `summary_ready` 推进为 `processed_ready`。
- 基于 `summary/summary.json` 生成固定结构的 Obsidian Markdown 笔记。
- 使用安全、幂等的文件命名和写入规则处理重试与同名冲突。
- 在笔记写入成功后写入或更新 SQLite `sources.status = "processed"`。
- 对 Obsidian 写入失败和 SQLite 写入失败提供结构化、可恢复错误。
- 新增 `skills/obsidian-write/SKILL.md`，作为未来 Hermes / Deep Agents 编排资产。

**Non-Goals:**

- 不重新调用 LLM 生成 Obsidian 笔记。
- 不接入 LangChain Deep Agents 运行时。
- 不生成 Obsidian wiki link、`obsidian://` 链接、vault 相对路径、MOC、backlinks 或 daily note。
- 不按领域自动创建目录或移动笔记。
- 不保护用户手工编辑；同 `source_id` 重试时整篇重渲染覆盖。
- 不升级 SQLite schema，不新增 `summary_path`、`domain_path` 或 `canonical_text_path` 字段。
- 不把评测模型结果、评分、排序或人工选择写入 Obsidian。

## Decisions

### 1. 使用确定性 Python renderer，不引入模板引擎

阶段八使用受控 Python renderer 从 `summary/summary.json` 直接生成 Markdown。渲染规则固定：frontmatter、H1、摘要、核心观点、关键概念、领域笔记、可操作启发、值得追问的问题、来源与素材。

选择这个方案的原因：

- summary schema 已经固定，模板引擎不会显著降低复杂度。
- 单元测试可以直接断言字段和 Markdown 片段。
- 不引入新依赖，保持 uv 依赖面稳定。

备选方案是使用 Jinja2 或外部 Markdown 模板。该方案更灵活，但首版会引入模板查找、变量缺失、转义和用户自定义模板兼容问题，超出阶段八目标。

### 2. frontmatter 使用受控 YAML 子集，不引入 PyYAML

frontmatter 只包含字符串和字符串数组。字符串使用 JSON 风格双引号转义，数组使用多行格式：

```yaml
tags:
  - "knowledge/AI"
```

固定字段包括 `title`、`source_id`、`source_url`、`content_type`、`domain`、`tags`、`created_at`、`updated_at`、`asset_dir`、`canonical_text`、`domain_path`、`summary_path`、`summary_model_ref` 和 `status`。

选择这个方案的原因：

- 字段集合简单，不需要完整 YAML serializer。
- JSON 字符串转义可以避免冒号、引号、反斜杠等字符破坏 frontmatter。
- 避免新增 PyYAML 依赖。

### 3. 文件命名使用可读标题，冲突时用 `source_id` 兜底

默认文件名：

```text
YYYY-MM-DD-safe-title.md
```

`safe-title` 规则：

- 去掉 `/ \ : * ? " < > |`
- 空白折叠成单个 `-`
- 最长 80 个字符
- 清洗后为空时使用 `untitled`

如果目标文件已存在：

- frontmatter `source_id` 等于当前 `source_id`：覆盖同一路径。
- frontmatter `source_id` 不同或不可识别：写入 `YYYY-MM-DD-safe-title-<source_id前8位>.md`。
- 兜底路径仍冲突且 `source_id` 不同：返回 `OBSIDIAN_WRITE_FAILED`。

这个方案兼顾 Obsidian 文件名可读性和重试幂等性。始终带 `source_id` 的方案更简单但文件名噪音较多；同名即报错则会让自动导入更脆弱。

### 4. 路径统一使用绝对路径

stdout JSON、SQLite `note_path` / `asset_dir`、frontmatter 和正文“来源与素材”统一使用绝对路径。阶段八不生成 vault 相对路径、Obsidian 内链或附件嵌入链接。

选择绝对路径是因为 CLI 面向 Hermes agent，绝对路径最少歧义。未来如果要提升 Obsidian 内部阅读体验，可单独设计链接美化阶段。

### 5. 文件系统和 SQLite 采用可重试的弱事务边界

阶段八顺序为：

1. 校验 `summary/summary.json` 和当前 pipeline 上下文一致。
2. 渲染 Markdown 到内存。
3. 计算目标 note 路径。
4. 通过临时文件写入，再原子替换目标 note。
5. note 写入成功后，写入或更新 SQLite `sources` 为 `processed`。

文件系统和 SQLite 无法组成真正的跨资源事务。设计上接受“note 已写入但 SQLite 失败”的状态，并通过 `INDEX_WRITE_FAILED` 返回 `note_path`。下一次重试时，同 `source_id` note 会被复用/覆盖，再次尝试写 SQLite。

### 6. SQLite 不升级 schema

阶段八复用现有 `sources` 字段：

```text
id, normalized_url, original_url, content_type, domain, title,
note_path, asset_dir, created_at, updated_at, status,
error_code, error_message
```

`id` 使用已有 `source_id`。`summary_path`、`domain_path` 和 `canonical_text_path` 不写入 SQLite，因为它们可由 `asset_dir` 推导，并已记录在 note frontmatter。

### 7. 只记录阶段八自身失败

阶段八新增 `OBSIDIAN_WRITE_FAILED` 和 `INDEX_WRITE_FAILED`。只有进入 Obsidian/processed 阶段后发生的失败才写 SQLite `status = "failed"`；前面文本化、领域分类和中文总结失败仍保持现有行为，不在本阶段补写 `failed`。

这样可以避免阶段八横向扩展到所有历史错误路径，保持变更范围集中。

### 8. `summary_ready` 保留为内部 builder，CLI 成功返回 `processed_ready`

`summary_ready_response(...)` 保留，方便内部测试和未来分阶段调用。但 `km ingest` 正常成功路径在总结后继续执行 Obsidian note pipeline，最终 stdout 返回 `processed_ready`。

`processed_ready` 不暴露评测字段；评测详情留在 `summary/summary.json` 和 `summary/evaluations/` 中。

### 9. vault 根目录必须存在，inbox 可以创建

`vault_path` 是用户知识库根目录，必须已存在、是目录且可写；系统不自动创建。`inbox_dir` 必须是 vault 内相对路径，不能是绝对路径或包含 `..`；如果不存在，系统可自动创建。`vault_path` 错误返回 `CONFIG_INVALID`，`inbox_dir` 创建或写入失败返回 `OBSIDIAN_WRITE_FAILED`。

## Risks / Trade-offs

- [Risk] 用户手工编辑的同 `source_id` note 在重试时被覆盖。  
  Mitigation: 阶段八明确采用整篇重渲染覆盖，只保留 `created_at`；人工编辑保护留到后续阶段。

- [Risk] note 已写入但 SQLite 更新失败，导致重复导入不会被 `processed` 跳过。  
  Mitigation: 返回 `INDEX_WRITE_FAILED` 并公开 `note_path`；重试时通过 `source_id` 幂等覆盖同一 note 并再次写 SQLite。

- [Risk] 不生成 Obsidian 内链会降低 vault 内阅读体验。  
  Mitigation: 阶段八优先完成可靠闭环；内链、vault 相对路径和 MOC 属于后续笔记体验优化。

- [Risk] 受控 YAML 子集可能不覆盖所有 YAML 特性。  
  Mitigation: frontmatter 字段保持简单，字符串使用 JSON 转义，数组仅支持字符串列表。

- [Risk] `summary/summary.json` 被外部篡改会生成错误笔记。  
  Mitigation: 写入前重新校验 schema、`schema_version` 和 `source` 路径与当前 pipeline 上下文一致，不一致返回 `SUMMARY_INPUT_INVALID`。

## Migration Plan

1. 新增 Obsidian note pipeline 代码和测试，不改 SQLite schema。
2. 扩展 CLI 成功路径：summary 成功后调用 note pipeline，最终返回 `processed_ready`。
3. 保留旧内部 response builders，避免一次性移除阶段性结果模型。
4. 更新 README、Superpowers 设计文档、OpenSpec specs 和项目内 skills。
5. 验证通过后归档 OpenSpec change，同步主 specs。

回滚策略：如果阶段八写入链路出现问题，可以在代码层临时回退 CLI 编排到 `summary_ready` 返回路径；素材仓库中的 summary 产物和 SQLite schema 均保持兼容。

## Open Questions

无。阶段八已确认不做 Deep Agents、Obsidian 内链、领域目录、用户编辑保护和 SQLite schema migration。
