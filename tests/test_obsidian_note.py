import json
from pathlib import Path
import tempfile
import unittest

from km.errors import KmError


class ObsidianNoteTests(unittest.TestCase):
    def import_obsidian(self):
        try:
            import km.obsidian as obsidian
        except ImportError as exc:
            self.fail(f"km.obsidian module should exist: {exc}")
        return obsidian

    def make_context_and_summary(self, **summary_overrides):
        obsidian = self.import_obsidian()
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)
        asset_dir = root_path / "assets" / "source-id"
        canonical_text_path = asset_dir / "canonical" / "content.md"
        domain_path = asset_dir / "summary" / "domain.json"
        summary_path = asset_dir / "summary" / "summary.json"
        canonical_text_path.parent.mkdir(parents=True)
        domain_path.parent.mkdir(parents=True)
        canonical_text_path.write_text("完整原文不应该进入 Obsidian 正文。", encoding="utf-8")
        domain_path.write_text("{}", encoding="utf-8")
        summary_payload = {
            "schema_version": 1,
            "domain": "AI",
            "title": 'AI Agent: "工具" 系统复盘',
            "one_sentence_summary": "文章总结了 AI Agent 工具系统的核心设计。",
            "core_points": ["Agent 需要可靠工具边界。", "素材应保存在仓库中。"],
            "key_concepts": [{"name": "Agent", "explanation": "能够调用工具完成任务的系统。"}],
            "domain_notes": {
                "核心问题": "如何组织工具调用。",
                "模型或方法": "Agent 编排。",
                "工具或系统": "受控 Python tools。",
                "数据或评测": "原文未明确说明",
                "工作流影响": "降低人工整理成本。",
                "能力边界": "需要 schema 校验。",
                "可复现说明": "原文未明确说明",
            },
            "actionable_insights": ["先定义受控边界。"],
            "questions": ["如何评估不同模型总结质量？"],
            "tags": ["knowledge/AI", "topic/Agent", "tool/Python"],
            "source": {
                "url": "https://example.com/article",
                "content_type": "web_article",
                "asset_dir": str(asset_dir),
                "canonical_text_path": str(canonical_text_path),
                "domain_path": str(domain_path),
            },
            "input": {
                "canonical_text_path": str(canonical_text_path),
                "domain_path": str(domain_path),
                "strategy": "single_pass",
                "truncated": False,
                "max_input_chars": 0,
            },
            "prompt": {"prompt_id": "summary.ai.v1", "domain": "AI"},
            "model_ref": "deepseek_pro",
            "model": "deepseek-v4-pro",
        }
        summary_payload.update(summary_overrides)
        summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False), encoding="utf-8")
        context = obsidian.ObsidianNoteContext(
            source_id="abcdef1234567890",
            normalized_url="https://example.com/article",
            original_url="https://example.com/article",
            content_type="web_article",
            asset_dir=asset_dir,
            canonical_text_path=canonical_text_path,
            domain_path=domain_path,
            summary_path=summary_path,
        )
        return context, summary_payload, root_path

    def test_render_obsidian_note_writes_frontmatter_and_body(self):
        obsidian = self.import_obsidian()
        context, summary_payload, _ = self.make_context_and_summary()

        rendered = obsidian.render_obsidian_note(
            context=context,
            summary_payload=summary_payload,
            created_at="2026-06-15T22:10:00+08:00",
            updated_at="2026-06-15T22:20:00+08:00",
        )

        self.assertTrue(rendered.startswith("---\n"))
        self.assertIn('title: "AI Agent: \\"工具\\" 系统复盘"', rendered)
        self.assertIn('source_id: "abcdef1234567890"', rendered)
        self.assertIn('source_url: "https://example.com/article"', rendered)
        self.assertIn('summary_model_ref: "deepseek_pro"', rendered)
        self.assertIn('status: "processed"', rendered)
        self.assertIn('  - "knowledge/AI"', rendered)
        self.assertIn("# AI Agent: \"工具\" 系统复盘", rendered)
        self.assertIn("## 一句话摘要", rendered)
        self.assertIn("文章总结了 AI Agent 工具系统的核心设计。", rendered)
        self.assertIn("- Agent 需要可靠工具边界。", rendered)
        self.assertIn("- **Agent**：能够调用工具完成任务的系统。", rendered)
        self.assertIn("### 核心问题", rendered)
        self.assertIn("## 来源与素材", rendered)
        self.assertIn(f"- 总结 JSON：`{context.summary_path}`", rendered)
        self.assertNotIn("完整原文不应该进入 Obsidian 正文", rendered)
        self.assertNotIn("summary.ai.v1", rendered)

    def test_safe_title_and_default_filename(self):
        obsidian = self.import_obsidian()

        self.assertEqual(obsidian.safe_title('  bad / name: with   spaces?  '), "bad-name-with-spaces")
        self.assertEqual(obsidian.safe_title('/\\:*?"<>|'), "untitled")
        self.assertLessEqual(len(obsidian.safe_title("很长" * 100)), 80)
        self.assertEqual(
            obsidian.note_filename(title="Python 调试实践", date_prefix="2026-06-15"),
            "2026-06-15-Python-调试实践.md",
        )

    def test_write_obsidian_note_uses_source_id_for_conflicts_and_preserves_created_at(self):
        obsidian = self.import_obsidian()
        context, summary_payload, root_path = self.make_context_and_summary(title="重复标题")
        vault_path = root_path / "vault"
        vault_path.mkdir()
        inbox_dir = "Inbox/Knowledge"
        inbox_path = vault_path / inbox_dir
        inbox_path.mkdir(parents=True)
        default_note = inbox_path / "2026-06-15-重复标题.md"
        default_note.write_text(
            "\n".join(
                [
                    "---",
                    'source_id: "other-source"',
                    'created_at: "2026-06-14T00:00:00+08:00"',
                    "---",
                    "# 旧笔记",
                ]
            ),
            encoding="utf-8",
        )

        result = obsidian.write_obsidian_note(
            context=context,
            summary_payload=summary_payload,
            vault_path=vault_path,
            inbox_dir=inbox_dir,
            now="2026-06-15T22:10:00+08:00",
            date_prefix="2026-06-15",
        )

        expected = inbox_path / "2026-06-15-重复标题-abcdef12.md"
        self.assertEqual(result.note_path, expected)
        self.assertTrue(expected.is_file())
        self.assertIn('source_id: "abcdef1234567890"', expected.read_text(encoding="utf-8"))

        updated_payload = dict(summary_payload, one_sentence_summary="重试后的摘要。")
        retry = obsidian.write_obsidian_note(
            context=context,
            summary_payload=updated_payload,
            vault_path=vault_path,
            inbox_dir=inbox_dir,
            now="2026-06-15T22:30:00+08:00",
            date_prefix="2026-06-15",
        )

        self.assertEqual(retry.note_path, expected)
        retry_content = expected.read_text(encoding="utf-8")
        self.assertIn("重试后的摘要。", retry_content)
        self.assertIn('created_at: "2026-06-15T22:10:00+08:00"', retry_content)
        self.assertIn('updated_at: "2026-06-15T22:30:00+08:00"', retry_content)

    def test_write_obsidian_note_requires_existing_vault_and_valid_summary_context(self):
        obsidian = self.import_obsidian()
        context, summary_payload, root_path = self.make_context_and_summary()

        with self.assertRaises(KmError) as missing_vault:
            obsidian.write_obsidian_note(
                context=context,
                summary_payload=summary_payload,
                vault_path=root_path / "missing-vault",
                inbox_dir="Inbox/Knowledge",
                now="2026-06-15T22:10:00+08:00",
                date_prefix="2026-06-15",
            )
        self.assertEqual(missing_vault.exception.error_code, "CONFIG_INVALID")

        bad_summary = dict(summary_payload)
        bad_summary["source"] = dict(summary_payload["source"], canonical_text_path="/tmp/wrong.md")
        with self.assertRaises(KmError) as invalid_summary:
            obsidian.validate_summary_for_obsidian(context=context, summary_payload=bad_summary)
        self.assertEqual(invalid_summary.exception.error_code, "SUMMARY_INPUT_INVALID")

    def test_validate_vault_does_not_overwrite_or_delete_existing_probe_named_file(self):
        obsidian = self.import_obsidian()
        _, _, root_path = self.make_context_and_summary()
        vault_path = root_path / "vault"
        vault_path.mkdir()
        existing_probe = vault_path / ".km-vault-write-test"
        existing_probe.write_text("用户已有文件", encoding="utf-8")

        obsidian.validate_vault(vault_path)

        self.assertEqual(existing_probe.read_text(encoding="utf-8"), "用户已有文件")


if __name__ == "__main__":
    unittest.main()
