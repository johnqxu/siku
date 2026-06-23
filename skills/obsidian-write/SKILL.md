# Obsidian 写入 Skill

本 skill 面向未来 Hermes / Deep Agents 编排，用于指导 agent 在 `summary/summary.json` 已存在且校验通过后，将结构化中文总结写入 Obsidian，并标记 SQLite `processed` 状态。

## 使用条件

- 已完成文本化、领域分类和中文总结。
- 素材仓库中已经存在 `summary/summary.json`。
- `summary/summary.json` 与当前来源上下文一致。

## 必须使用受控 Python tools

所有副作用必须通过受控 Python tools 完成，例如：

- `render_obsidian_note(...)`
- `write_obsidian_note(...)`
- `mark_source_processed(...)`

agent 路径不得直接写 Obsidian、SQLite 或素材仓库，只能调用 `write_obsidian_note` 和 `mark_source_processed` 受控 tools。

## 禁止行为

- 不得自行写 Obsidian Markdown 文件。
- 不得自行写 Obsidian，也不得绕过受控 Python tools。
- 不得自行更新 SQLite。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 不得把原文、完整 transcript、完整网页正文或原始 HTML 塞进 Obsidian 正文。
- 不得重新调用 LLM 生成或改写笔记。

## 输出边界

- 成功后由受控 tool 写入 Obsidian note，并更新 SQLite `sources.status = "processed"`。
- 成功响应为 `processed_ready`。
- 写入 Obsidian 失败返回 `OBSIDIAN_WRITE_FAILED`。
- note 已写入但 SQLite 更新失败返回 `INDEX_WRITE_FAILED`，并暴露 `note_path`。
