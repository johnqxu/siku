## 1. TDD 测试基线

- [x] 1.1 扩展 `tests/test_project_skills.py`，新增 `hermes-knowledge-ingest` skill 存在性测试。
- [x] 1.2 新增 Hermes skill 当前命令测试，确认文档包含 `/home/xu/workspace/siku` 和 `uv run --env-file .env km ingest`。
- [x] 1.3 新增 Hermes skill stdin 契约测试，确认文档要求单个 JSON object，并包含 `url` 与 `mode: "ingest"`。
- [x] 1.4 新增 Hermes skill 轻量预检查测试，确认文档包含 `.env`、`KM_CONFIG` 和 `DEEPSEEK_API_KEY`。
- [x] 1.5 新增 Hermes skill 输出处理测试，确认文档解释 `processed_ready`、`skipped_existing`、`ok`、`error_code`、`message` 和 `recoverable`。
- [x] 1.6 新增 Hermes skill 边界测试，确认文档禁止直接调用内部流水线 tools、不额外重试、默认不读取生成文件内容。
- [x] 1.7 新增 Hermes skill 迁移测试，确认文档记录未来 `uv run --extra agent --env-file .env km agent-ingest`，且禁止自动回退到 `km ingest`。

## 2. Skill 文档实现

- [x] 2.1 新增 `skills/hermes-knowledge-ingest/SKILL.md`，说明该 skill 是 Hermes 调用完整知识导入流程的高层入口。
- [x] 2.2 在 skill 中记录当前运行目录和命令：`cd /home/xu/workspace/siku` 后执行 `uv run --env-file .env km ingest`。
- [x] 2.3 在 skill 中记录 stdin JSON 契约：单个 object，包含 `url` 和 `mode: "ingest"`。
- [x] 2.4 在 skill 中记录轻量预检查边界，说明完整配置、URL、Obsidian、素材仓库、Whisper、下载器和 SQLite 校验仍由 CLI 负责。
- [x] 2.5 在 skill 中记录 stdout JSON 解释规则，覆盖成功、重复来源和失败 envelope。
- [x] 2.6 在 skill 中记录重试规则：skill 不自行重试，Hermes 只能根据 `recoverable: true` 在 workflow 层稍后重试。
- [x] 2.7 在 skill 中记录禁止行为：不得直接调用内部 tools、不得写素材仓库/SQLite/Obsidian、默认不得读取生成文件内容。
- [x] 2.8 在 skill 中记录未来显式切换到 `km agent-ingest` 的命令，并说明不允许自动 fallback。

## 3. 验证

- [x] 3.1 运行 `UV_CACHE_DIR=.uv-cache uv --no-config run python -m unittest tests.test_project_skills -v`。
- [x] 3.2 运行 `openspec validate add-hermes-knowledge-ingest-skill --strict`。
- [x] 3.3 运行 `openspec validate --all --strict`。
- [x] 3.4 运行 `git diff --check -- skills/hermes-knowledge-ingest/SKILL.md tests/test_project_skills.py openspec/changes/add-hermes-knowledge-ingest-skill`。
