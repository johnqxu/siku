# 项目研发宪法设计

## 目标

建立一套默认适用于所有项目的研发流程约束，确保需求分析、提案创建、实施、验证和代码审查有稳定顺序，并能在当前仓库中保留可审计记录。

这套规则面向研发变更，不用于拖慢纯问答、状态查询、解释代码、单纯运行命令或非研发诊断。

## 范围

研发变更包括：

- 新功能。
- bugfix。
- 行为变更。
- 重构。
- 会影响项目契约、配置、文档流程或发布结果的工程改动。

轻量例外包括：

- 解释代码或文档。
- 查看状态、运行只读命令或转述命令输出。
- 纯讨论且不要求落地为变更。
- 临时诊断。若诊断结论转为修复实现，则从修复点开始进入严格研发流程。

## 采用方案

采用“全局规则 + 当前仓库文档镜像”。

全局规则负责让未来所有项目会话默认遵守研发宪法。当前仓库文档负责保存中文、可审计、可复制的规则版本，方便后续回顾、迁移和同步。

暂不把治理规则本身直接建成 OpenSpec capability。该做法作为增强选项保留：后续若需要让治理要求进入 OpenSpec 校验，可新增 `development-governance` 之类的能力规范。

## 全局执行层

全局执行层应表达以下强制规则：

1. 任何研发变更开始前，先使用 superpowers 能力做需求分析或探讨。
2. 创建提案必须使用 OpenSpec 能力，生成 proposal、design、tasks，以及需要的 specs。
3. 实施提案必须使用 `superpowers:test-driven-development`，遵守红绿重构；没有先失败的测试，不写生产代码。
4. 完成实施后，必须使用 `superpowers:requesting-code-review` 执行 code review。
5. 对 review 发现的 Critical 和 Important 问题，必须修复或给出技术反驳后再继续。
6. 完成前必须执行验证命令，并用实际输出作为完成声明依据。

实施时需要先确认 Codex 支持的全局指令入口。候选位置包括 `~/.codex` 下的 rules、prompts 或其他全局 instructions 文件；不能把自然语言宪法误写进只用于命令审批的规则文件。

## 项目审计层

当前仓库应新增一份中文宪法文档，例如：

```text
docs/development-constitution.md
```

该文档应包含：

- 适用范围。
- 轻量例外。
- 标准研发流程。
- superpowers 与 OpenSpec 的使用要求。
- TDD 和 code review 的强制门禁。
- 验证与完成声明规则。
- OpenSpec capability 化治理规则的增强路线。

`docs/project-overview.md` 或 README 应简短引用该文档，让维护者能从常用入口找到规则。

## 标准流程

```text
用户提出需求或问题
  -> 判断是否属于研发变更
  -> 若不是研发变更，按轻量请求处理
  -> 若是研发变更，使用 superpowers 分析和探讨
  -> 使用 OpenSpec 创建或更新提案
  -> 用户确认提案后进入实施
  -> 使用 superpowers TDD 实施
  -> 执行验证
  -> 使用 superpowers code review
  -> 修复或反驳 review 问题
  -> 再验证
  -> 按用户要求归档、提交或推送
```

## 增强选项

后续可以新增 OpenSpec capability，例如 `development-governance`，把研发宪法变成可验证规范：

- requirement：研发变更 MUST 先完成 OpenSpec proposal/design/tasks。
- requirement：实施 MUST 通过 TDD 记录红绿过程。
- requirement：完成 MUST 有 code review 结果和验证证据。
- scenario：轻量请求不强制创建 OpenSpec。

该增强不作为当前设计的第一步，避免治理规则本身先引入过重流程。

## 风险与控制

主要风险是规则过重导致简单协作变慢。控制方式是明确“研发变更严格，非研发请求例外”。

另一个风险是全局规则与项目文档漂移。控制方式是在项目文档中记录全局规则摘要，并在修改任一侧时同步另一侧。

第三个风险是 Codex 全局规则入口识别错误。实施时必须先验证目标文件用途，尤其不能把自然语言约束写入只支持 `prefix_rule(...)` 的命令审批文件。

## 验收标准

- 存在中文设计文档记录本设计。
- 后续实施时生成全局生效规则。
- 当前仓库存在可审计的研发宪法文档。
- 常用项目入口能引用该宪法文档。
- 文档明确记录 OpenSpec capability 化治理规则是增强选项。
- 文档明确轻量例外，不要求纯问答或状态查询创建 OpenSpec。
