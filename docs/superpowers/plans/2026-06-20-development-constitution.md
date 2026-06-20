# Development Constitution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the confirmed project development constitution as both global Codex guidance and a versioned repository document.

**Architecture:** Use `~/.codex/AGENTS.md` as the global Codex instruction file, because Codex reads global context there. Mirror the same rules in `docs/development-constitution.md`, then expose that document from repository entry points without changing application behavior.

**Tech Stack:** Markdown, Codex `AGENTS.md`, OpenSpec CLI, shell-based document verification.

## Global Constraints

- This is a bootstrap governance change: once it lands, future研发变更 must follow the installed constitution, including OpenSpec proposals and superpowers TDD/review gates.
- Do not write natural-language instructions into `/home/xu/.codex/rules/default.rules`; that file stores command approval rules such as `prefix_rule(...)`.
- Preserve existing uncommitted application changes in this repository. Do not revert or stage unrelated files.
- Documentation language is Chinese by default. Keep tool names, command names, file paths, skill names, and OpenSpec keywords in their original form.
- The OpenSpec `development-governance` capability remains an enhancement option, not part of this first implementation.

---

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `/home/xu/.codex/AGENTS.md` | Create or modify | Global Codex instruction file that makes the constitution apply across all projects. Requires filesystem escalation because it is outside the workspace. |
| `docs/development-constitution.md` | Create | Versioned Chinese mirror of the constitution for audit, migration, and project discovery. |
| `AGENTS.md` | Create | Project-level agent instruction file that points agents to the repository mirror and confirms this repo follows the global constitution. |
| `docs/project-overview.md` | Modify | Add the constitution to the long-term project document map. Preserve existing unrelated edits. |

## Task 1: Add Repository Constitution Document

**Files:**
- Create: `docs/development-constitution.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-06-20-development-constitution-design.md`
- Produces: `docs/development-constitution.md` with stable headings used by later verification commands.

- [ ] **Step 1: Verify the document does not already exist**

Run:

```bash
test ! -e docs/development-constitution.md
```

Expected: exit code `0`. If it already exists, read it and merge the constitution instead of overwriting it.

- [ ] **Step 2: Write the failing document verification**

Run:

```bash
rg -n "项目研发宪法|研发变更严格，非研发请求例外|superpowers:test-driven-development|superpowers:requesting-code-review|OpenSpec capability 化治理规则" docs/development-constitution.md
```

Expected: FAIL because `docs/development-constitution.md` does not exist yet.

- [ ] **Step 3: Create the constitution document**

Create `docs/development-constitution.md` with this content:

```markdown
# 项目研发宪法

## 目标

本宪法定义所有项目默认遵守的研发流程：需求先分析，提案走 OpenSpec，实施走 superpowers TDD，完成后必须 code review，并以验证证据支撑完成声明。

本宪法面向研发变更，不用于拖慢纯问答、状态查询、解释代码、单纯运行命令或非研发诊断。

## 适用范围

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

核心边界：研发变更严格，非研发请求例外。

## 强制流程

```text
用户提出需求或问题
  -> 判断是否属于研发变更
  -> 若不是研发变更，按轻量请求处理
  -> 若是研发变更，使用 superpowers 分析和探讨
  -> 使用 OpenSpec 创建或更新提案
  -> 用户确认提案后进入实施
  -> 使用 superpowers:test-driven-development 实施
  -> 执行验证
  -> 使用 superpowers:requesting-code-review 执行 code review
  -> 修复或反驳 review 问题
  -> 再验证
  -> 按用户要求归档、提交或推送
```

## superpowers 使用要求

- 需求分析、方案探讨、功能设计或行为变更前，必须优先使用适用的 superpowers 能力。
- 创造性工作默认从 `superpowers:brainstorming` 或同类探索能力开始。
- bug 诊断应使用 `superpowers:systematic-debugging`。
- 实施新功能、bugfix、重构或行为变更时，必须使用 `superpowers:test-driven-development`。
- 完成主要实现后，必须使用 `superpowers:requesting-code-review` 做 code review。
- 完成声明前，必须使用验证流程确认测试、校验或手动验收输出。

## OpenSpec 使用要求

- 创建研发提案必须使用 OpenSpec 能力。
- OpenSpec artifacts 应包含 proposal、design、tasks，以及变更需要的 specs。
- 实施前必须读取 OpenSpec 上下文 artifacts。
- 实施过程中发现设计问题时，应回到 OpenSpec artifacts 更新事实来源，而不是只改代码。
- 完成实现后，按用户要求归档 OpenSpec 提案。

## TDD 门禁

- 没有先失败的测试，不写生产代码。
- 每个行为变更都应经历 RED、GREEN、REFACTOR。
- 对配置或文档类 bootstrap 变更，如果没有传统单元测试，应使用 shell 检查、文档断言或 OpenSpec validate 作为可复现验证。
- 不能用“看起来没问题”替代测试或验证输出。

## Code Review 门禁

- 完成实施后必须执行 `superpowers:requesting-code-review`。
- Critical 问题必须修复。
- Important 问题必须修复，或给出有证据的技术反驳。
- review 后修改必须重新验证。

## 验证与完成声明

- 声称完成、通过或可合并前，必须运行能证明该声明的命令。
- 最终回复必须列出关键验证命令和结果。
- 如果某项验证未运行，必须明确说明原因和剩余风险。

## 全局与项目镜像

- 全局执行规则保存在 Codex 全局指令文件：`~/.codex/AGENTS.md`。
- 当前仓库的可审计镜像保存在：`docs/development-constitution.md`。
- `~/.codex/rules/default.rules` 只用于命令审批规则，不存放自然语言研发宪法。

## 增强选项

后续可以新增 OpenSpec capability，例如 `development-governance`，把本宪法转成可验证规范：

- requirement：研发变更 MUST 先完成 OpenSpec proposal/design/tasks。
- requirement：实施 MUST 通过 TDD 记录红绿过程。
- requirement：完成 MUST 有 code review 结果和验证证据。
- scenario：轻量请求不强制创建 OpenSpec。

该增强不是当前第一步，避免治理规则本身先引入过重流程。
```

- [ ] **Step 4: Verify the document passes**

Run:

```bash
rg -n "项目研发宪法|研发变更严格，非研发请求例外|superpowers:test-driven-development|superpowers:requesting-code-review|OpenSpec capability 化治理规则" docs/development-constitution.md
```

Expected: PASS with matches for all required phrases.

## Task 2: Add Global Codex Instructions

**Files:**
- Create or modify: `/home/xu/.codex/AGENTS.md`

**Interfaces:**
- Consumes: `docs/development-constitution.md`
- Produces: global instructions that Codex loads for all projects.

- [ ] **Step 1: Confirm the target instruction file**

Run:

```bash
sed -n '1,80p' /home/xu/.codex/plugins/cache/personal/superpowers/6.0.2/skills/using-superpowers/references/codex-tools.md
```

Expected: output states that Codex reads `~/.codex/AGENTS.md` for global context and project-root `AGENTS.md` for project context.

- [ ] **Step 2: Verify the global constitution is not already installed**

Run:

```bash
test ! -f /home/xu/.codex/AGENTS.md || ! rg -q "项目研发宪法" /home/xu/.codex/AGENTS.md
```

Expected: exit code `0` before first install. If it fails, read the file and update the existing section instead of duplicating it.

- [ ] **Step 3: Write the failing global verification**

Run:

```bash
rg -n "项目研发宪法|研发变更严格，非研发请求例外|OpenSpec|superpowers:test-driven-development|superpowers:requesting-code-review" /home/xu/.codex/AGENTS.md
```

Expected: FAIL before the global instruction section exists.

- [ ] **Step 4: Request escalation and create or update `/home/xu/.codex/AGENTS.md`**

Because `/home/xu/.codex/AGENTS.md` is outside the workspace, request filesystem escalation before editing it.

If the file does not exist, create it with:

```markdown
# Codex 全局指令

## 项目研发宪法

对所有项目默认采用以下研发流程。用户在当前对话中的显式指令仍然优先。

### 适用范围

研发变更包括新功能、bugfix、行为变更、重构，以及会影响项目契约、配置、文档流程或发布结果的工程改动。

轻量例外包括纯问答、状态查询、解释代码、单纯运行命令、转述命令输出，以及尚未进入修复实现的临时诊断。

核心边界：研发变更严格，非研发请求例外。

### 强制流程

1. 需求分析、方案探讨、功能设计或行为变更前，先使用适用的 superpowers 能力。
2. 创建研发提案必须使用 OpenSpec 能力，并生成 proposal、design、tasks，以及变更需要的 specs。
3. 实施提案必须使用 `superpowers:test-driven-development`，遵守 RED、GREEN、REFACTOR；没有先失败的测试，不写生产代码。
4. 完成实施后，必须使用 `superpowers:requesting-code-review` 执行 code review。
5. Critical 和 Important review 问题必须修复，或给出有证据的技术反驳。
6. 完成声明前必须运行验证命令，并在最终回复中说明实际验证结果。

### OpenSpec 增强路线

后续可以把本宪法建成 OpenSpec capability，例如 `development-governance`。这是增强选项，不是当前 bootstrap 的第一步。
```

If the file already exists, append or replace only the `## 项目研发宪法` section and preserve unrelated content.

- [ ] **Step 5: Verify global instructions pass**

Run:

```bash
rg -n "项目研发宪法|研发变更严格，非研发请求例外|OpenSpec|superpowers:test-driven-development|superpowers:requesting-code-review" /home/xu/.codex/AGENTS.md
```

Expected: PASS with matches for all required phrases.

## Task 3: Add Project Agent Entry Point

**Files:**
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: `docs/development-constitution.md`
- Produces: project-root agent instructions that point to the audited constitution document.

- [ ] **Step 1: Verify project AGENTS does not already exist**

Run:

```bash
test ! -e AGENTS.md
```

Expected: exit code `0`. If it already exists, read it and merge the following section instead of overwriting it.

- [ ] **Step 2: Write the failing project instruction verification**

Run:

```bash
rg -n "docs/development-constitution.md|项目研发宪法|OpenSpec|superpowers:test-driven-development" AGENTS.md
```

Expected: FAIL because `AGENTS.md` does not exist yet.

- [ ] **Step 3: Create project `AGENTS.md`**

Create `AGENTS.md` with this content:

```markdown
# siku Agent Instructions

## 项目研发宪法

本仓库遵守 [docs/development-constitution.md](docs/development-constitution.md)。

研发变更必须先使用 superpowers 做需求分析或探讨，创建提案必须使用 OpenSpec，实施必须使用 `superpowers:test-driven-development`，完成实施后必须使用 `superpowers:requesting-code-review`。

轻量例外包括纯问答、状态查询、解释代码、单纯运行命令、转述命令输出，以及尚未进入修复实现的临时诊断。
```

- [ ] **Step 4: Verify project instructions pass**

Run:

```bash
rg -n "docs/development-constitution.md|项目研发宪法|OpenSpec|superpowers:test-driven-development" AGENTS.md
```

Expected: PASS with matches for all required phrases.

## Task 4: Link the Constitution from Project Overview

**Files:**
- Modify: `docs/project-overview.md`

**Interfaces:**
- Consumes: `docs/development-constitution.md`
- Produces: a discoverable pointer from the long-term project overview.

- [ ] **Step 1: Inspect the current document map**

Run:

```bash
sed -n '1,40p' docs/project-overview.md
```

Expected: output includes the `## 文档定位` section and existing document bullets.

- [ ] **Step 2: Write the failing overview verification**

Run:

```bash
rg -n "docs/development-constitution.md" docs/project-overview.md
```

Expected: FAIL before the link is added.

- [ ] **Step 3: Add one bullet to the document map**

In `docs/project-overview.md`, add this bullet under `## 文档定位`:

```markdown
- `docs/development-constitution.md`：记录所有项目默认遵守的研发宪法，包括 superpowers、OpenSpec、TDD、code review 和验证门禁。
```

Preserve existing unrelated edits in the file.

- [ ] **Step 4: Verify overview link passes**

Run:

```bash
rg -n "docs/development-constitution.md" docs/project-overview.md
```

Expected: PASS with the new bullet.

## Task 5: Final Verification and Review Gate

**Files:**
- Read: `AGENTS.md`
- Read: `docs/development-constitution.md`
- Read: `docs/project-overview.md`
- Read: `/home/xu/.codex/AGENTS.md`

**Interfaces:**
- Consumes: all outputs from Tasks 1-4.
- Produces: verification evidence and mandatory code review before completion.

- [ ] **Step 1: Run repository mirror checks**

Run:

```bash
rg -n "项目研发宪法|研发变更严格，非研发请求例外|superpowers:test-driven-development|superpowers:requesting-code-review|OpenSpec capability 化治理规则" docs/development-constitution.md
```

Expected: PASS with matches for all required phrases.

- [ ] **Step 2: Run agent instruction checks**

Run:

```bash
rg -n "项目研发宪法|研发变更严格，非研发请求例外|OpenSpec|superpowers:test-driven-development|superpowers:requesting-code-review" AGENTS.md /home/xu/.codex/AGENTS.md
```

Expected: PASS with matches in both files.

- [ ] **Step 3: Verify the project overview link**

Run:

```bash
rg -n "docs/development-constitution.md" docs/project-overview.md
```

Expected: PASS.

- [ ] **Step 4: Verify OpenSpec state remains valid**

Run:

```bash
openspec validate --all
```

Expected: PASS. This constitution bootstrap does not add the `development-governance` capability, so existing specs should remain valid.

- [ ] **Step 5: Check whitespace**

Run:

```bash
git diff --check -- AGENTS.md docs/development-constitution.md docs/project-overview.md
```

Expected: no output and exit code `0`.

- [ ] **Step 6: Request code review**

Invoke `superpowers:requesting-code-review` with this context:

```text
DESCRIPTION: Installed the development constitution as global Codex instructions and a versioned project mirror.
PLAN_OR_REQUIREMENTS: docs/superpowers/specs/2026-06-20-development-constitution-design.md and docs/superpowers/plans/2026-06-20-development-constitution.md.
BASE_SHA: the commit before implementation starts.
HEAD_SHA: current HEAD or the reviewable working tree diff, depending on whether implementation commits are made.
```

Expected: reviewer reports no Critical or Important issues, or any such issues are fixed or technically rebutted.

- [ ] **Step 7: Re-run verification after review fixes**

Run the commands from Steps 1-5 again.

Expected: all pass after any review-driven edits.
