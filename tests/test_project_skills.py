from pathlib import Path
import unittest


class ProjectSkillsTests(unittest.TestCase):
    def test_project_skills_exist_and_require_controlled_tools(self):
        root = Path(__file__).resolve().parents[1]
        skill_paths = (
            root / "skills" / "url-routing" / "SKILL.md",
            root / "skills" / "bilibili-ingest" / "SKILL.md",
            root / "skills" / "web-article-ingest" / "SKILL.md",
            root / "skills" / "whisper-transcription" / "SKILL.md",
            root / "skills" / "domain-classification" / "SKILL.md",
            root / "skills" / "summary-generation" / "SKILL.md",
            root / "skills" / "obsidian-write" / "SKILL.md",
        )

        for path in skill_paths:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")

                self.assertIn("受控 Python tools", content)
                self.assertIn("不得自行写入素材仓库、SQLite 或 Obsidian", content)

    def test_whisper_skill_mentions_openvino_intel_gpu(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "whisper-transcription" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("OpenVINO + optimum-intel", content)
        self.assertIn("Intel Xe", content)
        self.assertIn("GPU", content)

    def test_web_article_skill_mentions_controlled_fetch_and_parsers(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "web-article-ingest" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("HTTP fetch", content)
        self.assertIn("微信公众号", content)
        self.assertIn("通用 fallback", content)
        self.assertIn("trafilatura", content)
        self.assertIn("不得自行访问网络或解析 HTML", content)

    def test_domain_classification_skill_mentions_fixed_taxonomy_and_tool_boundary(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "domain-classification" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("固定领域表", content)
        self.assertIn("单一主领域", content)
        self.assertIn("其他", content)
        self.assertIn("受控 Python tools", content)
        self.assertIn("不得自行调用 LLM", content)

    def test_summary_generation_skill_mentions_controlled_tool_and_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "summary-generation" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("受控 Python tools", content)
        self.assertIn("单次总结", content)
        self.assertIn("summary/summary.json", content)
        self.assertIn("不得自行调用 LLM", content)
        self.assertIn("不得写 Obsidian", content)
        self.assertIn("不得写 SQLite", content)
        self.assertIn("Deep Agents", content)

    def test_obsidian_write_skill_mentions_controlled_tools_and_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "obsidian-write" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("summary/summary.json", content)
        self.assertIn("受控 Python tools", content)
        self.assertIn("render_obsidian_note", content)
        self.assertIn("write_obsidian_note", content)
        self.assertIn("mark_source_processed", content)
        self.assertIn("不得自行写 Obsidian", content)
        self.assertIn("不得自行更新 SQLite", content)
        self.assertIn("不得重新调用 LLM", content)

    def test_hermes_knowledge_ingest_skill_documents_cli_boundary(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "hermes-knowledge-ingest" / "SKILL.md").read_text(encoding="utf-8")

        self.assertTrue(content.startswith("---\n"))
        frontmatter = content.split("---\n", 2)[1]
        self.assertIn("name: hermes-knowledge-ingest", frontmatter)
        self.assertIn("description:", frontmatter)
        self.assertIn("加入到知识库", frontmatter)
        self.assertIn("保存到知识库", frontmatter)
        self.assertIn("Obsidian", frontmatter)
        self.assertIn("URL", frontmatter)
        self.assertLessEqual(len(frontmatter), 1024)

        self.assertIn("Hermes", content)
        self.assertIn("完整知识导入流程", content)
        self.assertIn("/home/xu/workspace/siku", content)
        # 默认入口是 km agent-ingest
        self.assertIn("uv run --extra agent --env-file .env km agent-ingest", content)
        self.assertNotIn("uv run --env-file .env km ingest", content)
        self.assertNotIn("km ingest 保留", content)
        self.assertIn("stdin", content)
        self.assertIn("JSON object", content)
        self.assertIn("url", content)
        self.assertIn('mode: "ingest"', content)

    def test_hermes_knowledge_ingest_skill_documents_preflight_and_output(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "hermes-knowledge-ingest" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn(".env", content)
        self.assertIn("KM_CONFIG", content)
        self.assertIn("DEEPSEEK_API_KEY", content)
        self.assertIn("processed_ready", content)
        self.assertIn("skipped_existing", content)
        self.assertIn("ok", content)
        self.assertIn("error_code", content)
        self.assertIn("message", content)
        self.assertIn("recoverable", content)
        self.assertIn("stdout", content)
        self.assertIn("stderr", content)

    def test_hermes_knowledge_ingest_skill_documents_restrictions_and_agent_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "hermes-knowledge-ingest" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("不增加自己的重试循环", content)
        self.assertIn("不得直接调用内部流水线工具", content)
        self.assertIn("route_url", content)
        self.assertIn("collect_bilibili_text", content)
        self.assertIn("collect_web_article_text", content)
        self.assertIn("classify_domain", content)
        self.assertIn("generate_summary", content)
        self.assertIn("write_obsidian_note", content)
        self.assertIn("mark_source_processed", content)
        self.assertIn("不主动读取", content)
        self.assertIn("uv run --extra agent --env-file .env km agent-ingest", content)
        self.assertIn("uv run --extra agent --extra gpu --env-file .env km agent-ingest", content)
        self.assertIn("唯一公开导入入口", content)
        self.assertIn("不得自动回退", content)
        self.assertNotIn("选择 `km agent-ingest` 或 `km ingest`", content)

    def test_hermes_knowledge_ingest_skill_prevents_memory_false_success(self):
        root = Path(__file__).resolve().parents[1]
        content = (root / "skills" / "hermes-knowledge-ingest" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("加入到知识库", content)
        self.assertIn("https://b23.tv/wPRipfZ", content)
        self.assertIn("必须调用 `km agent-ingest`", content)
        self.assertIn("不得用 `web_extract`", content)
        self.assertIn("不得用 `memory`", content)
        self.assertIn("Hermes memory 不是 Obsidian 知识库", content)
        self.assertIn("没有 `km agent-ingest` stdout JSON", content)
        self.assertIn("不得回复“已加入知识库”", content)
        self.assertIn('`ok: true`', content)
        self.assertIn('`status: "processed_ready"`', content)
        self.assertIn('`status: "skipped_existing"`', content)


if __name__ == "__main__":
    unittest.main()
