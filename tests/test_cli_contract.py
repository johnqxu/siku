import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from km.__main__ import main


class CliContractTests(unittest.TestCase):
    def run_cli(self, command, payload, env=None):
        return subprocess.run(
            [sys.executable, "-m", "km", command],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def run_public_cli(self, command, payload, env=None):
        executable_dir = "Scripts" if os.name == "nt" else "bin"
        script_name = "km.exe" if os.name == "nt" else "km"
        executable = os.path.join(sys.prefix, executable_dir, script_name)
        if not os.path.exists(executable):
            self.fail("km console script missing; run tests with `uv run` after `uv sync`.")
        return subprocess.run(
            [executable, command],
            input=payload,
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def parse_stdout_json(self, result):
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"stdout was not a JSON object: {result.stdout!r}; stderr={result.stderr!r}; {exc}")

    def test_ingest_command_is_removed_from_module_cli(self):
        result = self.run_cli("ingest", '{"url":"https://example.com","mode":"ingest"}')

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        self.assertFalse(response["recoverable"])
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_ingest_command_is_removed_from_public_console_script(self):
        result = self.run_public_cli("ingest", '{"url":"https://example.com","mode":"ingest"}')

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        self.assertFalse(response["recoverable"])
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertEqual(result.stderr, "")

    def test_main_rejects_ingest_without_loading_config_or_agent_runner(self):
        with (
            mock.patch("sys.argv", ["km", "ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com","mode":"ingest"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.load_config") as load_config,
            mock.patch("km.__main__.AgentIngestRunner") as runner_class,
        ):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        load_config.assert_not_called()
        runner_class.assert_not_called()

    def test_agent_ingest_command_remains_supported(self):
        fake_response = {
            "ok": True,
            "status": "processed_ready",
            "orchestrator": "deep_agents",
        }
        with (
            mock.patch("sys.argv", ["km", "agent-ingest"]),
            mock.patch("sys.stdin.read", return_value='{"url":"https://example.com","mode":"ingest"}'),
            mock.patch("sys.stdout") as stdout,
            mock.patch("km.__main__.load_config") as load_config,
            mock.patch("km.__main__.AgentIngestRunner") as runner_class,
        ):
            runner_class.return_value.run.return_value = fake_response
            exit_code = main()

        self.assertEqual(exit_code, 0)
        output = "".join(call.args[0] for call in stdout.write.call_args_list if call.args)
        self.assertEqual(json.loads(output), fake_response)
        load_config.assert_called_once()
        runner_class.return_value.run.assert_called_once_with(
            {"url": "https://example.com", "mode": "ingest"}
        )

    def test_malformed_json_still_returns_single_json_error_for_agent_ingest(self):
        result = self.run_cli("agent-ingest", "{")

        self.assertEqual(result.returncode, 1)
        response = self.parse_stdout_json(result)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "INPUT_INVALID")
        self.assertFalse(response["recoverable"])
        self.assertEqual(result.stdout.count("\n"), 1)

    def test_bottom_layer_modules_remain_importable_for_agent_tools(self):
        from km import bilibili, domain, index, obsidian, summary, web_article, whisper

        self.assertTrue(hasattr(bilibili, "collect_bilibili_transcript"))
        self.assertTrue(hasattr(web_article, "collect_web_article"))
        self.assertTrue(hasattr(domain, "classify_domain"))
        self.assertTrue(hasattr(summary, "generate_summary"))
        self.assertTrue(hasattr(obsidian, "write_obsidian_note"))
        self.assertTrue(hasattr(index, "IngestIndex"))
        self.assertTrue(hasattr(whisper, "OpenVinoWhisperTranscriber"))


if __name__ == "__main__":
    unittest.main()
