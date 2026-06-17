## 1. 测试准备

- [x] 1.1 更新测试辅助函数，使测试配置默认包含 `vault_path`、`inbox_dir` 和 `asset_store_path`。
- [x] 1.2 添加配置 schema 测试：缺少字段、空白字段、非字符串字段、不安全 `inbox_dir` 和位于 vault 内的 `asset_store_path` 返回 `CONFIG_INVALID`。
- [x] 1.3 添加 URL 规范化测试：scheme/host 小写、去除 fragment、保留 query、拒绝非 `http/https` URL。
- [x] 1.4 添加 `source_id` 测试：相同 `normalized_url` 生成相同完整 SHA-256 hex。
- [x] 1.5 添加素材仓库初始化测试：创建根目录和 `<source_id>/raw`、`canonical`、`summary`。
- [x] 1.6 添加 SQLite 初始化测试：创建 `index.sqlite`、`sources` 表、基础索引和 `PRAGMA user_version = 1`，且重复初始化不清空数据。
- [x] 1.7 添加重复来源查询测试：`status = 'processed'` 命中并返回 `original_url`，非 `processed` 不命中。
- [x] 1.8 添加 CLI 行为测试：未命中重复来源返回 `NOT_IMPLEMENTED` 和退出码 `2`，命中重复来源返回 `skipped_existing` 和退出码 `0`。

## 2. 配置模型

- [x] 2.1 定义阶段二配置模型，包含 `vault_path`、`inbox_dir` 和 `asset_store_path`。
- [x] 2.2 更新 `load_config`，校验必填字段类型和非空字符串。
- [x] 2.3 对 `vault_path` 和 `asset_store_path` 执行 `~` 展开，并保留 `inbox_dir` 为 vault 内相对目录字符串。
- [x] 2.4 校验 `inbox_dir` 不是绝对路径且不包含 `..` 路径片段。
- [x] 2.5 校验 `asset_store_path` 不等于且不位于 `vault_path` 内部。
- [x] 2.6 确保配置错误统一转换为 `CONFIG_INVALID` 响应和退出码 `1`。

## 3. URL 与来源标识

- [x] 3.1 新增 URL 规范化模块，输出 `original_url` 和 `normalized_url`。
- [x] 3.2 实现保守规范化规则：去首尾空白、小写化 scheme/host、删除 fragment、保留 path/query/port。
- [x] 3.3 拒绝无法解析 host 或 scheme 不是 `http`/`https` 的 URL，并转换为 `INPUT_INVALID`。
- [x] 3.4 实现 `source_id = sha256(normalized_url).hexdigest()`。

## 4. 素材仓库

- [x] 4.1 新增素材仓库模块，负责解析 `asset_store_path`、`index.sqlite` 路径和来源目录路径。
- [x] 4.2 实现素材仓库根目录创建和可写性校验。
- [x] 4.3 实现来源目录初始化，创建 `raw`、`canonical` 和 `summary` 子目录。
- [x] 4.4 将路径不可创建、不是目录或不可写的情况转换为 `CONFIG_INVALID`。

## 5. SQLite 索引

- [x] 5.1 新增 SQLite 索引模块，使用标准库 `sqlite3` 打开 `<asset_store_path>/index.sqlite`。
- [x] 5.2 实现 `sources` 表创建，字段与阶段二 spec 保持一致。
- [x] 5.3 实现 `domain`、`created_at` 和 `status` 基础索引创建。
- [x] 5.4 设置并校验 `PRAGMA user_version = 1`，拒绝高于当前支持版本的数据库。
- [x] 5.5 确保 schema 初始化可重复执行且不破坏已有数据。
- [x] 5.6 实现按 `normalized_url` 查询 `status = 'processed'` 的重复来源，并返回 `original_url`。

## 6. CLI 集成

- [x] 6.1 更新 `km ingest` 流程：解析请求后保留 `IngestRequest`，加载阶段二配置。
- [x] 6.2 在返回业务结果前执行 URL 规范化和 `source_id` 生成。
- [x] 6.3 初始化素材仓库根目录、来源目录和 SQLite 索引。
- [x] 6.4 查询重复来源；命中时输出 `skipped_existing` 成功响应。
- [x] 6.5 未命中重复来源时继续输出 `NOT_IMPLEMENTED`，保持退出码 `2`。
- [x] 6.6 保持 stdout 只输出单个 JSON 对象，诊断信息不写入 stdout。

## 7. 文档与验证

- [x] 7.1 更新 README 阶段说明和示例配置，说明阶段二需要的配置字段。
- [x] 7.2 更新 Superpowers 设计文档或补充阶段二说明，使其与 OpenSpec 提案保持一致。
- [x] 7.3 运行 `uv run python -m unittest discover -s tests -v`。
- [x] 7.4 运行 `openspec validate add-local-state-foundation`。
- [x] 7.5 确认阶段二没有实现网页、Bilibili、Whisper、LLM、Deep Agents 或 Obsidian 写入。
