## Why

当前 `km ingest` 在生成 `summary/summary.json` 后返回 `summary_ready`，但还没有把知识写入 Obsidian，也没有把来源标记为 SQLite `processed`。这会导致端到端知识管理闭环缺失：Hermes 能得到总结完成信号，却不能依赖工具已经产出可阅读笔记，也不能通过本地索引跳过已完成来源。

阶段八需要把已确认的中文总结产物渲染为 Obsidian Markdown 笔记，写入配置的 inbox，并在 SQLite 中记录 `processed` 状态，让 CLI 成功状态从阶段性 `summary_ready` 推进为完整的 `processed_ready`。

## What Changes

- 新增 Obsidian 笔记写入 pipeline：读取并校验 `summary/summary.json`，渲染 Markdown，写入 `<vault_path>/<inbox_dir>/`。
- 新增 `processed_ready` 成功响应，端到端成功路径不再停在 `summary_ready`。
- 保留 `summary_ready` 作为内部阶段响应 builder，但 CLI 成功路径继续执行 Obsidian 写入和 SQLite processed 标记。
- 新增安全文件命名、同 `source_id` 幂等覆盖、不同来源同名冲突兜底规则。
- 新增受控 YAML frontmatter 子集和固定 Obsidian 正文结构。
- 新增 SQLite `processed` / 阶段八 `failed` 写入行为，不升级 schema，继续使用 `PRAGMA user_version = 1`。
- 新增公开错误码 `OBSIDIAN_WRITE_FAILED` 和 `INDEX_WRITE_FAILED`，均为可恢复错误并返回退出码 `2`；`INDEX_WRITE_FAILED` 公开返回已写入的 `note_path`。
- 新增项目内 `skills/obsidian-write/SKILL.md`，供未来 Hermes / Deep Agents 编排复用。
- 阶段八仍不接入 LangChain Deep Agents 运行时，不生成 Obsidian 内链、不自动分领域目录、不做 MOC/backlinks/daily note、不保护用户手工编辑。

## Capabilities

### New Capabilities

- `obsidian-note-pipeline`: 定义从 `summary/summary.json` 到 Obsidian Markdown 笔记、SQLite `processed` 标记和 `processed_ready` 响应的完整闭环。

### Modified Capabilities

- `cli-contract-skeleton`: 将端到端成功响应从 `summary_ready` 推进为 `processed_ready`，新增阶段八错误码、退出码和测试契约。
- `local-state-foundation`: 明确 `vault_path` / `inbox_dir` 写入校验、SQLite `processed` / `failed` 写入和重复来源跳过的阶段八语义。
- `summary-generation-pipeline`: 将 `summary_ready` 调整为内部阶段结果，并声明总结成功后继续进入 Obsidian processed pipeline。
- `domain-classification-pipeline`: 更新领域分类后的端到端成功路径，避免规范仍停留在 `summary_ready`。
- `bilibili-transcript-pipeline`: 更新 Bilibili 成功链路，文本化、分类、总结后继续写 Obsidian 并返回 `processed_ready`。
- `web-article-content-pipeline`: 更新网页文章成功链路，正文抽取、分类、总结后继续写 Obsidian 并返回 `processed_ready`。
- `url-routing-and-skill-skeleton`: 增加 `obsidian-write` 项目内 skill，并保持所有 skills 只能调用受控 Python tools。

## Impact

- 代码：新增 Obsidian note renderer / writer、SQLite processed 标记函数、`processed_ready` response builder，并接入 `km ingest` 成功路径。
- CLI 协议：成功状态新增并改为 `processed_ready`；失败响应新增 `OBSIDIAN_WRITE_FAILED`、`INDEX_WRITE_FAILED`。
- 本地文件系统：写入 Obsidian vault inbox 下的 Markdown 笔记，路径使用绝对路径。
- SQLite：复用现有 `sources` 表写入 `processed` 和阶段八 `failed`，不做 schema migration。
- 文档与 skills：更新 README、Superpowers 设计文档、OpenSpec specs，并新增 `skills/obsidian-write/SKILL.md`。
- 测试：新增渲染、文件命名、写入、SQLite、CLI 端到端契约和 skill 文档测试。
