from pathlib import Path
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "test_bilibili_download.sh"


class BilibiliDownloadScriptTests(unittest.TestCase):
    def test_script_exposes_help_and_core_bilibili_diagnostics(self):
        self.assertTrue(SCRIPT.is_file(), f"missing script: {SCRIPT}")

        completed = subprocess.run(
            ["bash", str(SCRIPT), "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("用法", completed.stdout)
        self.assertIn("COOKIE", completed.stdout)

        script_text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Referer: https://www.bilibili.com", script_text)
        self.assertIn("Origin: https://www.bilibili.com", script_text)
        self.assertIn("Chrome/130.0.0.0", script_text)
        self.assertIn("--dump-single-json", script_text)
        self.assertIn("--extract-audio", script_text)


if __name__ == "__main__":
    unittest.main()
