## Context

当前主 spec 已经定义 `km ingest` 的 Hermes 调用契约：JSON stdin/stdout、配置加载、失败 envelope、退出码和测试基线。现有实现只要求配置文件存在且是合法 TOML object，合法请求会固定返回 `NOT_IMPLEMENTED`。

阶段二需要把后续导入流程都会依赖的本地状态层前置完成。Bilibili、网页、Whisper、LLM 和 Obsidian 写入都需要稳定的来源标识、素材目录、SQLite 去重记录和配置路径。如果直接进入 Bilibili 采集，会把下载、字幕、音频、失败恢复和本地状态混在一起，导致边界过大。

## Goals / Non-Goals

**Goals:**

- 将配置校验升级为阶段二 schema：`vault_path`、`inbox_dir`、`asset_store_path` 都必须存在且是非空字符串。
- 在合法请求中完成 URL 规范化，生成稳定 `normalized_url`。
- 使用 `sha256(normalized_url)` 生成稳定 `source_id`，并用它作为素材目录名。
- 在 `asset_store_path` 下初始化 `index.sqlite` 和 `<source_id>/raw`、`<source_id>/canonical`、`<source_id>/summary`。
- 创建 SQLite `sources` 表及基础索引。
- 支持查询已处理来源；命中 `status = 'processed'` 时返回 `skipped_existing` 成功响应。
- 未命中重复来源时继续返回 `NOT_IMPLEMENTED` 和退出码 `2`，为后续采集阶段保留边界。

**Non-Goals:**

- 不采集网页内容。
- 不采集 Bilibili 元数据、字幕、视频或音频。
- 不调用 Whisper、本地模型或远程 LLM。
- 不引入 LangChain Deep Agents 编排。
- 不写 Obsidian 笔记。
- 不写 `source.json`、`summary.json` 或规范正文文件。
- 不实现失败尝试记录和重试策略；只创建支持这些字段的 schema。

## Decisions

### 阶段二 CLI 真实初始化本地状态

合法请求通过配置和 URL 校验后，CLI 会创建素材仓库目录、初始化 `index.sqlite`、创建来源目录并查询重复记录。这样阶段二不仅是内部模块，还能验证 Hermes 未来调用时最关键的本地状态链路。

替代方案是只实现内部模块而不接入 CLI。该方案更小，但无法暴露配置路径、文件权限和 SQLite 初始化问题，因此推迟了最容易影响后续阶段的风险。

### 配置字段使用字符串路径并在运行时展开

阶段二配置要求：

```toml
vault_path = "/Users/xu/Obsidian"
inbox_dir = "Inbox/Knowledge"
asset_store_path = "/Users/xu/KnowledgeAssets"
```

`vault_path` 和 `asset_store_path` 按文件系统路径处理并展开 `~`。`inbox_dir` 是 vault 内相对目录，阶段二要求它是非空字符串、不是绝对路径，且路径片段不包含 `..`。阶段二不强制创建 Obsidian 目录；真正写笔记的目录创建留到 Obsidian 阶段。

`asset_store_path` 必须位于 Obsidian vault 外部。系统应比较 `asset_store_path.resolve()` 和 `vault_path.resolve()`，拒绝素材仓库等于 vault 或位于 vault 内部的配置，避免把大体积原始素材写进 Obsidian vault。

### URL 规范化保持保守

规范化规则采用低风险集合：

- 去除首尾空白。
- 要求 scheme 是 `http` 或 `https`。
- scheme 和 host 小写。
- 删除 fragment。
- 保留 path、query、端口和大小写敏感 path。

阶段二不做站点专属规则，例如不删除 Bilibili query、不解析 BV 号、不合并移动站和主站 URL。这些规则容易影响内容定位，适合在 URL 路由或具体采集阶段补充。

### 使用完整 SHA-256 作为 source_id

`source_id = sha256(normalized_url).hexdigest()`，素材目录为 `<asset_store_path>/<source_id>`。阶段二使用完整 64 位 hex，而不是截断 ID，避免在早期引入碰撞和迁移问题。后续如果需要更短目录名，可以增加 display id，但不改变权威 ID。

### SQLite 是权威索引

SQLite 文件固定为 `<asset_store_path>/index.sqlite`。阶段二创建 `sources` 表：

```sql
CREATE TABLE sources (
  id TEXT PRIMARY KEY,
  normalized_url TEXT NOT NULL UNIQUE,
  original_url TEXT NOT NULL,
  content_type TEXT NOT NULL,
  domain TEXT,
  title TEXT,
  note_path TEXT,
  asset_dir TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  error_code TEXT,
  error_message TEXT
);
```

并创建 `domain`、`created_at`、`status` 的索引。阶段二设置 `PRAGMA user_version = 1` 作为初始 schema 版本；初始化时如果发现数据库版本高于当前支持版本，应返回配置错误，避免用旧代码处理未来 schema。阶段二只查询 `status = 'processed'` 的记录，返回 `note_path`、`asset_dir` 和该记录的 `original_url`；写入 processed/failed 记录留到后续真正导入阶段。

### 成功 envelope 先只支持 skipped_existing

阶段二新增唯一成功场景：重复来源跳过。

```json
{
  "ok": true,
  "status": "skipped_existing",
  "note_path": "...",
  "asset_dir": "...",
  "source_url": "..."
}
```

`source_url` 使用 SQLite 已处理记录中的 `original_url`，表示当初创建该知识记录时保存的原始来源链接；内部去重身份仍由 `normalized_url` 决定。

`created` 成功响应不在阶段二引入，因为阶段二不会创建 Obsidian 笔记或完整素材。

## Risks / Trade-offs

- 配置 schema 从空 TOML 升级为必填字段会破坏第一阶段测试假设 -> 同步更新 CLI 契约 spec 和测试，让 breaking 行为显式化。
- 阶段二会在未实现采集时创建空来源目录 -> 这是有意取舍，用于提前验证路径和权限；后续导入阶段可以复用目录。
- URL 规范化过度会造成错误去重 -> 阶段二采用保守规则，站点专属归一化留给后续。
- SQLite schema 过早固化可能需要迁移 -> 初始 schema 保留通用字段；本阶段不引入复杂迁移框架，只要求 `CREATE TABLE IF NOT EXISTS` 和索引初始化可重复执行。
- Obsidian 路径配置可能导致素材写入 vault 内或 Inbox 逃逸 vault -> 阶段二校验 `asset_store_path` 不在 vault 内，并校验 `inbox_dir` 是不含 `..` 的相对路径。
- `content_type TEXT NOT NULL` 与阶段二尚未识别内容类型存在张力 -> 阶段二不写入新来源记录，因此不会产生未知 `content_type`；已有测试 fixture 如需插入 processed 记录，应提供明确 `content_type`。

## Migration Plan

1. 更新配置模型和校验逻辑，使缺失字段、非字符串字段、空字符串、不安全 `inbox_dir` 或位于 vault 内的 `asset_store_path` 返回 `CONFIG_INVALID`。
2. 增加 URL 规范化、`source_id`、素材仓库和 SQLite 模块。
3. 将 `km ingest` 合法请求流程扩展为：解析请求 -> 加载配置 -> 规范化 URL -> 初始化素材仓库和 SQLite -> 查询重复记录 -> 命中则返回 `skipped_existing`，未命中则返回 `NOT_IMPLEMENTED`。
4. 更新和新增测试，覆盖配置 schema、URL 规范化、目录初始化、SQLite schema、重复命中和未命中行为。
5. 若需要回滚，删除阶段二新增模块并恢复第一阶段配置校验与固定 `NOT_IMPLEMENTED` 行为；阶段二创建的本地 `index.sqlite` 和空来源目录不影响第一阶段 CLI 契约。

## Open Questions

- 阶段二暂不定义站点专属 URL 规范化规则；Bilibili BV 号级别归一化应在阶段三 URL 路由或阶段四 Bilibili 采集时再确认。
- 阶段二是否需要把本地状态初始化信息写入 stderr 诊断日志：默认不写，避免 Hermes 调用噪音；测试只要求 stdout 是单个 JSON 对象。
