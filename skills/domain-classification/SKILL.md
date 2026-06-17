# 领域分类 Skill

## 适用场景

当 Bilibili 或网页文章 pipeline 已经生成规范文本，并且需要识别知识主领域时，使用本 skill 指导领域分类流程。

## 固定领域表

阶段六只允许从以下固定领域表中选择一个单一主领域：

- AI
- 编程
- 产品
- 商业
- 学习
- 心理学
- 投资
- 写作
- 生活
- 菜谱
- 其他

如果内容跨领域、证据不足或无法明确判断，应选择 `其他`，并在原因中说明判断依据。

## 受控工具

所有副作用必须通过受控 Python tools 完成。领域分类必须调用项目提供的受控分类 tool，由该 tool 读取规范文本、调用配置引用的 LLM client、校验 JSON schema，并写入 `summary/domain.json`。

## 工作边界

- 本 skill 只描述流程和约束，不直接读取或写入素材仓库。
- 不得自行调用 LLM。
- 不得自行调用 shell。
- 不得自行写入素材仓库、SQLite 或 Obsidian。
- 不得生成 `summary/domain.md`。
- 不得生成中文总结或 Obsidian 笔记。
- 不得把多个领域、自由标签或辅助领域写入分类结果。

## 输出约束

领域分类结果必须写入 `summary/domain.json`，并包含：

- `taxonomy_version`
- `domain`
- `confidence`
- `reason`
- `model_ref`
- `model`

`reason` 必须使用中文。`domain_ready` 只表示领域分类完成，不表示完整知识笔记已经完成。

## 本阶段非目标

阶段六不接入 LangChain Deep Agents 运行时，不执行中文总结，不写 Obsidian，不写 SQLite `processed` 记录，也不更新 SQLite `domain` 字段。
