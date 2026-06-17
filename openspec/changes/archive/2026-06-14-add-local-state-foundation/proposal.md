## Why

第一阶段已经建立 Hermes 调用 `km ingest` 的协议骨架，但合法请求仍停在 `NOT_IMPLEMENTED`，还没有可复用的本地状态能力。后续 Bilibili、网页、Whisper、LLM 和 Obsidian 写入都依赖稳定的配置、URL 规范化、素材仓库和去重索引，因此需要先把本地状态基础落稳。

## What Changes

- 将配置校验从“合法 TOML object”扩展为阶段二需要的明确 schema：`vault_path`、`inbox_dir`、`asset_store_path`。
- **BREAKING** 空 TOML 或缺少阶段二必填字段的配置不再视为有效运行配置。
- 增加 URL 规范化能力，生成稳定 `normalized_url`，用于去重和来源 ID 计算。
- 基于 `sha256(normalized_url)` 生成稳定 `source_id`，并用它作为素材目录名。
- 在可配置的 `asset_store_path` 下初始化素材仓库基础结构和 `index.sqlite`。
- 创建 SQLite `sources` 表和基础索引，支持按 `normalized_url` 查询已完成来源。
- 将 `km ingest` 的合法请求推进到本地状态层：未命中重复来源时仍返回 `NOT_IMPLEMENTED`，命中 `status = 'processed'` 记录时返回 `skipped_existing` 成功响应。
- 阶段二不实现网页采集、Bilibili 采集、Whisper、LLM、Deep Agents 编排或 Obsidian 笔记写入。

## Capabilities

### New Capabilities

- `local-state-foundation`: 定义配置 schema、URL 规范化、`source_id`、素材仓库初始化、SQLite schema 和重复来源查询。

### Modified Capabilities

- `cli-contract-skeleton`: 扩展配置校验要求，并允许合法请求在本地状态层命中重复来源时返回成功的 `skipped_existing` 响应。

## Impact

- 影响 `km` CLI 的配置加载、请求处理流程、响应模型和测试覆盖。
- 新增 Python 模块用于配置模型、URL 规范化、素材仓库路径管理和 SQLite 索引访问。
- 使用 Python 标准库 `sqlite3`、`hashlib`、`urllib.parse` 和 `pathlib`，不新增外部依赖。
- `km ingest` 在合法配置和合法 URL 下会产生本地副作用：创建素材仓库目录、初始化 `index.sqlite`，并可能创建 `<source_id>/raw`、`<source_id>/canonical`、`<source_id>/summary` 目录。
- 公开 JSON stdout 契约继续保持单对象输出；日志和诊断仍写入 stderr。
