## 1. 提案与设计

- [ ] 1.1 创建 OpenSpec 提案目录和元数据：`.openspec.yaml`、`proposal.md`、`design.md`、`tasks.md`。
- [ ] 1.2 创建 `specs/change-default-ingest-entry/spec.md`，定义 skill 默认入口变更的具体场景。

## 2. 更新 Hermes Skill 文档

- [ ] 2.1 重写 `skills/hermes-knowledge-ingest/SKILL.md`，将默认命令从 `km ingest` 切换为 `km agent-ingest`。
- [ ] 2.2 更新预检查要求，增加 `agent` extra 和 `agent_orchestration` 配置检查声明。
- [ ] 2.3 更新命令示例，将 `km agent-ingest` 放在默认推荐位置，`km ingest` 降级为调试/备用入口。
- [ ] 2.4 移除"未来阶段九迁移"等过时表述，统一为"当前默认使用 agent 编排入口"。

## 3. 更新项目文档

- [ ] 3.1 更新 `README.md`，将 `km agent-ingest` 放在快速开始和常用命令的更前位置。
- [ ] 3.2 更新 `docs/project-overview.md`，更新 Hermes 调用截面图和默认入口描述。

## 4. 更新测试

- [ ] 4.1 更新 `tests/test_project_skills.py`，确认 skill 文档默认命令包含 `km agent-ingest`，同时确认 `km ingest` 仍然作为调试入口被提及。

## 5. 验证

- [ ] 5.1 运行 `openspec validate switch-hermes-skill-to-agent-ingest --strict`。
- [ ] 5.2 运行 `uv run python -m unittest tests.test_project_skills -v`。
- [ ] 5.3 运行 `git diff --check -- skills/hermes-knowledge-ingest/SKILL.md README.md docs/project-overview.md tests/test_project_skills.py openspec/changes/switch-hermes-skill-to-agent-ingest`。
- [ ] 5.4 提交并推送变更。
