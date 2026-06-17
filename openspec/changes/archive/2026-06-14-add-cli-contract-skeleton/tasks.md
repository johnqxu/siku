## 1. Python 项目骨架

- [x] 1.1 创建 Python 包目录和 `km` CLI 入口模块。
- [x] 1.2 添加 `pyproject.toml`，声明包名、Python 版本、CLI entry point 和测试依赖。
- [x] 1.3 添加基础测试目录和测试运行配置。
- [x] 1.4 添加最小 README 或开发说明，记录如何在本地运行 `km ingest` 和测试命令。

## 2. 请求与响应模型

- [x] 2.1 定义 `IngestRequest` model，包含必填 `url` 和默认值为 `ingest` 的 `mode`。
- [x] 2.2 校验 `mode` 只允许 `ingest`，其他值返回 `INPUT_INVALID`。
- [x] 2.3 定义公开失败响应 envelope model，覆盖 `ok: false`、`error_code`、`message` 和 `recoverable`。
- [x] 2.4 定义 `NOT_IMPLEMENTED` 响应，用于合法请求到达本阶段未实现业务边界。
- [x] 2.5 定义结构化错误 model，包含 `error_code`、`message` 和 `recoverable`。
- [x] 2.6 定义退出码映射：输入/配置/协议错误 `1`，`NOT_IMPLEMENTED` 和可恢复处理失败 `2`，未来成功路径 `0`。

## 3. CLI 协议实现

- [x] 3.1 实现从 stdin 读取完整 JSON payload。
- [x] 3.2 实现 JSON 解析和输入 model 校验。
- [x] 3.3 实现 stdout 只输出一个 JSON 对象。
- [x] 3.4 实现日志和异常细节只写入 stderr。
- [x] 3.5 对合法但业务尚未实现的请求固定返回 `NOT_IMPLEMENTED` 错误和退出码 `2`。

## 4. 配置加载与校验

- [x] 4.1 定义本阶段最小配置规则：配置文件必须存在且内容必须是合法 TOML object。
- [x] 4.2 实现配置文件发现或显式配置路径读取。
- [x] 4.3 实现配置解析和基础校验。
- [x] 4.4 在配置缺失或无效时返回 `CONFIG_INVALID`。
- [x] 4.5 确保配置错误发生在业务处理前。

## 5. 错误处理边界

- [x] 5.1 实现中心化异常到公开错误响应的映射。
- [x] 5.2 实现 `INPUT_INVALID`。
- [x] 5.3 实现 `CONFIG_INVALID`。
- [x] 5.4 实现固定 `NOT_IMPLEMENTED` 阶段响应。
- [x] 5.5 确保未捕获异常不会污染 stdout。

## 6. 测试基线

- [x] 6.1 添加测试：有效 JSON 输入可以被解析。
- [x] 6.2 添加测试：省略 `mode` 时默认使用 `ingest`。
- [x] 6.3 添加测试：非法 `mode` 返回 `INPUT_INVALID` 和退出码 `1`。
- [x] 6.4 添加测试：malformed JSON 返回 `INPUT_INVALID` 和退出码 `1`。
- [x] 6.5 添加测试：缺少 `url` 返回 `INPUT_INVALID` 和退出码 `1`。
- [x] 6.6 添加测试：配置缺失或无效返回 `CONFIG_INVALID` 和退出码 `1`。
- [x] 6.7 添加测试：合法请求返回 `NOT_IMPLEMENTED` 和退出码 `2`。
- [x] 6.8 添加测试：stdout 始终是单个可解析 JSON 对象。
- [x] 6.9 添加测试：日志写入 stderr，不写入 stdout。

## 7. 阶段收尾

- [x] 7.1 运行格式化和测试命令。
- [x] 7.2 运行 `openspec validate add-cli-contract-skeleton`。
- [x] 7.3 确认本阶段没有实现网页、Bilibili、Whisper、LLM、SQLite、素材仓库、Obsidian 或 Deep Agents 业务能力。
