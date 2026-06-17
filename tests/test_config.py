import os
from pathlib import Path
import tempfile
import unittest

from km.config import load_config
from km.errors import KmError


class ConfigTests(unittest.TestCase):
    def write_config(self, config_text):
        config = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        self.addCleanup(lambda path=config.name: os.path.exists(path) and os.unlink(path))
        with config:
            config.write(config_text)
        return config.name

    def valid_paths(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        root_path = Path(root.name)
        return root_path / "vault", root_path / "assets"

    def valid_config_text(self):
        vault_path, asset_store_path = self.valid_paths()
        return "\n".join(
            [
                f'vault_path = "{vault_path}"',
                'inbox_dir = "Inbox/Knowledge"',
                f'asset_store_path = "{asset_store_path}"',
                "",
            ]
        )

    def valid_config_text_with_llm(self):
        return (
            self.valid_config_text()
            + "\n".join(
                [
                    "[llm.models.deepseek_flash]",
                    'provider = "openai_compatible"',
                    'base_url = "https://api.deepseek.com/v1"',
                    'model = "deepseek-v4-flash"',
                    'api_key_env = "DEEPSEEK_API_KEY"',
                    "",
                    "[llm.tasks]",
                    'domain_classification = "deepseek_flash"',
                    "",
                ]
            )
        )

    def valid_config_text_with_summary_llm(self):
        return (
            self.valid_config_text()
            + "\n".join(
                [
                    "[llm.models.deepseek_v4_flash]",
                    'provider = "openai_compatible"',
                    'base_url = "https://api.deepseek.com/v1"',
                    'model = "deepseek-v4-flash"',
                    'api_key_env = "DEEPSEEK_API_KEY"',
                    'timeout_seconds = 60',
                    'max_output_tokens = 4096',
                    "",
                    "[llm.models.deepseek_v4_pro]",
                    'provider = "openai_compatible"',
                    'base_url = "https://api.deepseek.com/v1"',
                    'model = "deepseek-v4-pro"',
                    'api_key_env = "DEEPSEEK_API_KEY"',
                    "",
                    "[llm.tasks]",
                    'domain_classification = "deepseek_v4_flash"',
                    'summary_generation = "deepseek_v4_pro"',
                    "",
                    "[summary]",
                    "max_input_chars = 0",
                    "",
                    "[summary.evaluation]",
                    "enabled = true",
                    'candidate_models = ["deepseek_v4_flash", "deepseek_v4_pro"]',
                    'primary_model = "deepseek_v4_pro"',
                    "",
                ]
            )
        )

    def load_with_config(self, config_text):
        config_path = self.write_config(config_text)
        previous = os.environ.get("KM_CONFIG")
        os.environ["KM_CONFIG"] = config_path
        self.addCleanup(self.restore_env, previous)
        return load_config()

    def restore_env(self, previous):
        if previous is None:
            os.environ.pop("KM_CONFIG", None)
        else:
            os.environ["KM_CONFIG"] = previous

    def set_env(self, name, value):
        previous = os.environ.get(name)
        os.environ[name] = value
        self.addCleanup(self.restore_named_env, name, previous)

    def restore_named_env(self, name, previous):
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous

    def assert_config_invalid(self, config_text):
        with self.assertRaises(KmError) as raised:
            self.load_with_config(config_text)
        self.assertEqual(raised.exception.error_code, "CONFIG_INVALID")

    def test_load_config_returns_stage_two_config(self):
        config = self.load_with_config(self.valid_config_text())

        self.assertIsInstance(config.vault_path, Path)
        self.assertEqual(config.inbox_dir, "Inbox/Knowledge")
        self.assertIsInstance(config.asset_store_path, Path)
        self.assertEqual(config.whisper_model_dir, "models/whisper")
        self.assertEqual(config.whisper_device, "GPU")
        self.assertEqual(config.whisper_model_size, "medium")

    def test_load_config_accepts_domain_classification_llm_task_model(self):
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        config = self.load_with_config(self.valid_config_text_with_llm())

        self.assertEqual(config.llm_tasks.domain_classification, "deepseek_flash")
        model = config.llm_models["deepseek_flash"]
        self.assertEqual(model.provider, "openai_compatible")
        self.assertEqual(model.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(model.model, "deepseek-v4-flash")
        self.assertEqual(model.api_key_env, "DEEPSEEK_API_KEY")
        self.assertEqual(model.api_key, "test-key")

    def test_load_config_accepts_summary_generation_and_evaluation_config(self):
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        config = self.load_with_config(self.valid_config_text_with_summary_llm())

        self.assertEqual(config.llm_tasks.domain_classification, "deepseek_v4_flash")
        self.assertEqual(config.llm_tasks.summary_generation, "deepseek_v4_pro")
        self.assertEqual(config.summary.max_input_chars, 0)
        self.assertTrue(config.summary.evaluation.enabled)
        self.assertEqual(
            config.summary.evaluation.candidate_models,
            ("deepseek_v4_flash", "deepseek_v4_pro"),
        )
        self.assertEqual(config.summary.evaluation.primary_model, "deepseek_v4_pro")
        flash = config.llm_models["deepseek_v4_flash"]
        self.assertEqual(flash.timeout_seconds, 60)
        self.assertEqual(flash.max_output_tokens, 4096)
        pro = config.llm_models["deepseek_v4_pro"]
        self.assertEqual(pro.timeout_seconds, 120)
        self.assertEqual(pro.max_output_tokens, 8192)

    def test_summary_generation_model_reference_must_exist(self):
        config_text = self.valid_config_text_with_summary_llm().replace(
            'summary_generation = "deepseek_v4_pro"',
            'summary_generation = "missing_model"',
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_summary_evaluation_primary_model_must_be_candidate(self):
        config_text = self.valid_config_text_with_summary_llm().replace(
            'primary_model = "deepseek_v4_pro"',
            'primary_model = "missing_model"',
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_summary_evaluation_candidate_ref_must_be_file_safe(self):
        config_text = self.valid_config_text_with_summary_llm().replace(
            'candidate_models = ["deepseek_v4_flash", "deepseek_v4_pro"]',
            'candidate_models = ["deepseek/v4/flash", "deepseek_v4_pro"]',
        ).replace(
            'primary_model = "deepseek_v4_pro"',
            'primary_model = "deepseek/v4/flash"',
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_summary_max_input_chars_must_be_non_negative_integer(self):
        config_text = self.valid_config_text_with_summary_llm().replace(
            "max_input_chars = 0",
            "max_input_chars = -1",
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_model_timeout_and_output_limit_must_be_positive(self):
        self.set_env("DEEPSEEK_API_KEY", "test-key")
        for field, bad_value in (("timeout_seconds", "0"), ("max_output_tokens", "0")):
            with self.subTest(field=field):
                config_text = self.valid_config_text_with_summary_llm().replace(
                    f"{field} = {60 if field == 'timeout_seconds' else 4096}",
                    f"{field} = {bad_value}",
                )

                self.assert_config_invalid(config_text)

    def test_domain_classification_model_reference_must_exist(self):
        config_text = self.valid_config_text_with_llm().replace(
            'domain_classification = "deepseek_flash"',
            'domain_classification = "missing_model"',
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_domain_classification_model_requires_all_fields(self):
        config_text = self.valid_config_text_with_llm().replace(
            'base_url = "https://api.deepseek.com/v1"\n',
            "",
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_domain_classification_api_key_env_must_exist(self):
        previous = os.environ.get("DEEPSEEK_API_KEY")
        os.environ.pop("DEEPSEEK_API_KEY", None)
        self.addCleanup(self.restore_named_env, "DEEPSEEK_API_KEY", previous)

        self.assert_config_invalid(self.valid_config_text_with_llm())

    def test_domain_classification_provider_must_be_openai_compatible(self):
        config_text = self.valid_config_text_with_llm().replace(
            'provider = "openai_compatible"',
            'provider = "unsupported"',
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_llm_config_must_be_table(self):
        config_text = self.valid_config_text() + 'llm = "bad"\n'

        self.assert_config_invalid(config_text)

    def test_domain_classification_task_must_be_non_empty_string(self):
        config_text = self.valid_config_text_with_llm().replace(
            'domain_classification = "deepseek_flash"',
            'domain_classification = "   "',
        )
        self.set_env("DEEPSEEK_API_KEY", "test-key")

        self.assert_config_invalid(config_text)

    def test_load_config_accepts_openvino_whisper_settings(self):
        vault_path, asset_store_path = self.valid_paths()

        config = self.load_with_config(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    f'asset_store_path = "{asset_store_path}"',
                    "[whisper]",
                    'model_dir = "/models/whisper-large-v3"',
                    'model_size = "small"',
                    'device = "GPU.0"',
                    "",
                ]
            )
        )

        self.assertEqual(config.whisper_model_dir, "/models/whisper-large-v3")
        self.assertEqual(config.whisper_model_size, "small")
        self.assertEqual(config.whisper_device, "GPU.0")

    def test_whisper_cpu_device_returns_config_invalid(self):
        vault_path, asset_store_path = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    f'asset_store_path = "{asset_store_path}"',
                    "[whisper]",
                    'device = "CPU"',
                    "",
                ]
            )
        )

    def test_missing_required_field_returns_config_invalid(self):
        vault_path, _ = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    "",
                ]
            )
        )

    def test_blank_required_field_returns_config_invalid(self):
        vault_path, asset_store_path = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "   "',
                    f'asset_store_path = "{asset_store_path}"',
                    "",
                ]
            )
        )

    def test_non_string_required_field_returns_config_invalid(self):
        vault_path, asset_store_path = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    "inbox_dir = 123",
                    f'asset_store_path = "{asset_store_path}"',
                    "",
                ]
            )
        )

    def test_absolute_inbox_dir_returns_config_invalid(self):
        vault_path, asset_store_path = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "/tmp/outside"',
                    f'asset_store_path = "{asset_store_path}"',
                    "",
                ]
            )
        )

    def test_parent_segment_inbox_dir_returns_config_invalid(self):
        vault_path, asset_store_path = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "Inbox/../Outside"',
                    f'asset_store_path = "{asset_store_path}"',
                    "",
                ]
            )
        )

    def test_asset_store_inside_vault_returns_config_invalid(self):
        vault_path, _ = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    f'asset_store_path = "{vault_path / "assets"}"',
                    "",
                ]
            )
        )

    def test_asset_store_equal_to_vault_returns_config_invalid(self):
        vault_path, _ = self.valid_paths()

        self.assert_config_invalid(
            "\n".join(
                [
                    f'vault_path = "{vault_path}"',
                    'inbox_dir = "Inbox/Knowledge"',
                    f'asset_store_path = "{vault_path}"',
                    "",
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
