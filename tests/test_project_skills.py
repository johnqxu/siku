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


if __name__ == "__main__":
    unittest.main()
