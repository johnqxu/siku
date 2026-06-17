# 中文总结生成 Skill

本 skill 面向未来 Hermes / Deep Agents 编排，用于指导 agent 在文本化和领域分类完成后生成结构化中文总结。

## 使用边界

- 必须通过项目提供的受控 Python tools 执行中文总结，当前入口是 `generate_summary(...)`。
- 不得自行调用 LLM；模型调用、prompt 选择、schema 校验和错误映射都由受控 Python tools 处理。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 不得写 Obsidian，不得写 SQLite `processed` 记录。
- 不得启用 Deep Agents 运行时端到端编排；当前阶段仍由 Python 确定性 pipeline 调用。
- 不做评测评分、排序、manifest、UI 或人工选择记录。

## 输入前置条件

- 已存在规范文本：Bilibili 使用 `canonical/transcript.md`，网页文章使用 `canonical/content.md`。
- 已存在领域分类结果：`summary/domain.json`。
- 配置中已定义 `[llm.tasks] summary_generation`。
- 如果启用评测模式，配置中已定义 `[summary.evaluation] candidate_models` 和 `primary_model`。

## 处理策略

- 使用单次总结，不做 chunk、map-reduce 或多轮汇总。
- 默认不主动截断；`[summary].max_input_chars = 0` 表示完整输入。
- 显式配置 `max_input_chars > 0` 时，受控工具可以截断并在 `input.truncated` 中记录。
- 输出权威总结到 `summary/summary.json`。
- 评测模式下候选结果写入 `summary/evaluations/<model_ref>.json`，主模型结果写入 `summary/summary.json`。

## 输出要求

- 总结必须是中文结构化 JSON。
- `summary/summary.json` 必须包含标题、一句话总结、核心观点、关键概念、领域专属笔记、行动启发、后续问题、标签、来源追溯、输入策略、prompt 信息和模型追溯字段。
- Obsidian 正文不在本阶段生成。
- 后续 Obsidian 写入必须交给 `obsidian-write` skill 对应的受控 Python tools。
