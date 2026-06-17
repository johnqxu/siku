## 背景

知识导入工具最终会包含内容识别、网页采集、Bilibili 采集、Whisper 转写、LLM 总结、SQLite 索引、素材仓库和 Obsidian 写入。直接实现全部能力会让最关键的 Hermes 调用契约和错误边界被复杂业务逻辑掩盖。

本阶段只建立 CLI 契约骨架：命令入口、JSON stdin/stdout、配置加载、结构化错误、退出码和测试基线。后续阶段必须在这个契约上扩展，而不是重新定义 Hermes 调用方式。

## 目标 / 非目标

**目标：**

- 创建可安装或可运行的 Python CLI 项目骨架。
- 提供 `km ingest` 命令入口。
- 从 stdin 读取单个 JSON 请求，并向 stdout 写入唯一 JSON 响应。
- 将日志、异常细节和调试信息写入 stderr。
- 定义并校验最小输入 schema：`url` 必填且去除首尾空白后不能为空，`mode` 可选且默认 `ingest`；本阶段只允许 `mode = "ingest"`。
- 定义公开失败响应 envelope。
- 实现本地配置文件发现、解析和基础校验；本阶段最小配置只要求配置文件存在且是合法 TOML 对象。
- 实现统一错误模型和退出码映射。
- 建立可持续扩展的测试框架和协议测试。

**非目标：**

- 不实现网页抓取。
- 不实现 Bilibili 元数据、字幕或音频采集。
- 不实现 Whisper 转写。
- 不实现 LLM 分类或总结。
- 不实现 SQLite 去重索引。
- 不实现素材仓库写入。
- 不实现 Obsidian 笔记写入。
- 不引入 Deep Agents 编排。

## 决策

### 先固定 CLI 契约，再实现业务能力

Hermes 最依赖的是协议稳定性。先实现契约骨架可以让后续能力逐步接入，同时持续验证 stdout、stderr、退出码和错误 JSON 不被破坏。

替代方案是直接实现网页导入或完整端到端导入，但那会让协议、配置、错误和业务逻辑同时变化，测试和回归成本更高。

### JSON stdin/stdout 是唯一权威 agent 接口

`km ingest` 从 stdin 接收 JSON，stdout 只输出一个 JSON 对象。这个约束比 shell flags 更适合 agent 解析。后续可以添加人类友好的 wrapper，但不能替代这个接口。

### 配置与输入 payload 分离

Hermes 调用 payload 只表达“要处理什么”，不传 vault 路径、素材路径、模型名或密钥。配置由本地配置文件和环境变量提供，这样可以减少 agent 误传敏感信息的机会，也让调用更稳定。

### 本阶段使用占位处理结果

本阶段不做真实导入。对于通过输入校验和配置校验的合法请求，命令必须返回：

```json
{
  "ok": false,
  "error_code": "NOT_IMPLEMENTED",
  "message": "导入能力尚未实现。",
  "recoverable": true
}
```

该响应使用退出码 `2`。真实 `created`、`skipped_existing` 和业务错误将在后续阶段逐步接入。

### 本阶段最小配置格式

本阶段只验证配置文件存在且能解析为 TOML object。配置文件可以为空对象，也可以预留后续字段，例如：

```toml
[tool]
profile = "default"
```

业务配置字段，例如 `vault_path`、`asset_store_path`、LLM 设置和 Whisper 设置，不在本阶段校验范围内。

### 使用 uv 管理 Python 项目和虚拟环境

项目使用 `uv` 作为唯一推荐的 Python 项目管理入口。`pyproject.toml` 保存项目元数据、依赖声明、`km` console script 和 `uv_build` 构建配置；`uv.lock` 固定依赖解析结果并进入版本控制；`.python-version` 固定本地开发默认 Python 为 `3.11`。

本地项目虚拟环境由 `uv` 管理。开发者运行 `uv sync` 时，`uv` 会为项目创建或同步 `.venv/`；运行 `uv run ...` 时，`uv` 会在项目环境中执行命令，并确保环境与锁文件保持同步。测试命令使用 `uv run python -m unittest discover -s tests -v`，公开 CLI smoke test 必须覆盖已安装的 `km ingest` console script。`.venv/` 是本地生成物，必须保留在 `.gitignore` 中，不提交到仓库。

### 错误映射集中管理

所有内部异常都必须转换为公开错误对象：

```json
{
  "ok": false,
  "error_code": "INPUT_INVALID",
  "message": "人类可读的错误信息",
  "recoverable": false
}
```

退出码映射：

- `0`：未来成功或明确的非错误结果；本阶段不会因为合法请求返回 `0`。
- `1`：输入、配置或协议错误。
- `2`：可恢复的处理失败；本阶段合法请求固定返回 `NOT_IMPLEMENTED` 和退出码 `2`。

## 风险 / 取舍

- 骨架阶段看起来“不产生真实价值” -> 它为后续所有阶段提供稳定边界和测试基线，是避免 agent 工具失控的前置工作。
- 过早定义过多业务错误码可能造成返工 -> 本阶段只定义通用错误码和 envelope，业务错误码在对应阶段新增。
- 配置文件格式未来可能变化 -> 本阶段只要求文件存在且是合法 TOML object，具体业务字段在后续阶段扩展。
- stdout 纯 JSON 容易被调试输出污染 -> 测试必须显式覆盖 stdout/stderr 分离。

## 迁移计划

这是新项目骨架，没有现有运行时数据需要迁移。

实施顺序：

1. 创建 Python 项目结构和 CLI 入口。
2. 定义 models、schemas、errors 和 exit code 映射。
3. 实现 stdin JSON 解析和 stdout JSON 输出。
4. 实现配置加载和校验。
5. 添加日志到 stderr 的边界。
6. 添加协议测试和配置测试。

回滚方式是删除本阶段新增代码和 OpenSpec change。因为本阶段不写外部数据，不涉及数据迁移。

## 开放问题

- 默认配置文件位置使用 `~/.config/km/config.toml`，还是先要求通过环境变量指定？
