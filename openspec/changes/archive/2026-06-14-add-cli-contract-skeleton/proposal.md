## 为什么

知识导入工具后续会接入网页、Bilibili、Whisper、LLM、SQLite 和 Obsidian 等多个复杂能力。先建立稳定的 CLI 契约骨架，可以让 Hermes 从第一阶段就依赖固定的 JSON stdin/stdout、退出码、配置加载和错误结构，而不用等待完整导入能力完成。

## 变更内容

- 新增 Python CLI 应用骨架和 `km ingest` 命令入口。
- 定义 Hermes 调用协议：stdin 接收单个 JSON 请求，stdout 返回唯一 JSON 响应，日志只写 stderr。
- 定义首版输入 schema：必填 `url`，可选 `mode`，默认 `ingest`；本阶段只允许 `mode = "ingest"`。
- 定义失败响应 envelope；本阶段对合法请求固定返回 `NOT_IMPLEMENTED`，表示协议可用但真实导入能力尚未接入。
- 增加本地配置发现、解析和校验骨架；本阶段最小配置只要求配置文件存在且是合法 TOML 对象。
- 增加统一错误模型、错误码到退出码的映射。
- 增加基础测试框架，覆盖 CLI 协议、配置校验、错误输出和日志边界。

## 能力

### 新增能力

- `cli-contract-skeleton`：面向 Hermes agent 的知识导入 CLI 契约骨架，包括命令入口、JSON stdin/stdout、最小配置加载、结构化错误、退出码和测试基线。

### 修改能力

无。

## 影响

- 新增 Python 项目结构、CLI 入口和基础测试配置。
- 新增面向后续阶段复用的 schema/model/error/config 模块。
- 暂不接入网页采集、Bilibili 采集、Whisper、LLM、SQLite 索引、素材仓库或 Obsidian 写入。
- 后续阶段需要在不破坏本阶段公开 CLI 契约的前提下扩展真实导入能力。
