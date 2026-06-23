import unittest
from unittest import mock

from km.whisper import OpenVinoWhisperTranscriber
from km.errors import KmError


class OpenVinoWhisperTranscriberTests(unittest.TestCase):
    def test_defaults_to_gpu_device(self):
        transcriber = OpenVinoWhisperTranscriber(model_dir="/models/whisper")

        self.assertEqual(transcriber.device, "GPU")

    def test_rejects_cpu_device_to_avoid_silent_fallback(self):
        with self.assertRaises(ValueError):
            OpenVinoWhisperTranscriber(model_dir="/models/whisper", device="CPU")

    def test_loads_cached_openvino_ir_from_configured_model_dir(self):
        fake_model = mock.Mock()
        fake_model.generate.return_value = [[1, 2, 3]]
        fake_model_class = mock.Mock()
        fake_model_class.from_pretrained.return_value = fake_model
        fake_processor = self.fake_processor()
        fake_processor_class = mock.Mock()
        fake_processor_class.from_pretrained.return_value = fake_processor
        fake_audio_loader = mock.Mock(return_value=[0.0] * 16000)

        transcriber = OpenVinoWhisperTranscriber(
            model_dir="/models/whisper",
            model_size="medium",
            model_class=fake_model_class,
            processor_class=fake_processor_class,
            audio_loader=fake_audio_loader,
            path_exists=lambda path: path.endswith("/models/whisper/medium/openvino_encoder_model.xml"),
            make_dirs=mock.Mock(),
        )

        result = transcriber.transcribe("/tmp/audio.wav")

        fake_model_class.from_pretrained.assert_called_once_with(
            "/models/whisper/medium",
            export=False,
            compile=True,
            device="GPU",
            local_files_only=True,
            ov_config={"PERFORMANCE_HINT": "LATENCY"},
        )
        fake_processor_class.from_pretrained.assert_called_once_with(
            "/models/whisper/medium",
            local_files_only=True,
        )
        fake_model.save_pretrained.assert_not_called()
        generate_kwargs = fake_model.generate.call_args.kwargs
        self.assertNotIn("max_new_tokens", generate_kwargs)
        self.assertEqual(result.text, "转写文本")

    def test_cached_openvino_ir_bootstraps_missing_processor_from_hf_cache(self):
        fake_model = mock.Mock()
        fake_model.generate.return_value = [[1, 2, 3]]
        fake_model_class = mock.Mock()
        fake_model_class.from_pretrained.return_value = fake_model
        fake_processor = self.fake_processor()
        fake_processor_class = mock.Mock()
        fake_processor_class.from_pretrained.side_effect = [OSError("missing local processor"), fake_processor]
        fake_audio_loader = mock.Mock(return_value=[0.0] * 16000)

        transcriber = OpenVinoWhisperTranscriber(
            model_dir="/models/whisper",
            model_size="medium",
            model_class=fake_model_class,
            processor_class=fake_processor_class,
            audio_loader=fake_audio_loader,
            path_exists=lambda path: path.endswith("/models/whisper/medium/openvino_encoder_model.xml"),
            make_dirs=mock.Mock(),
        )

        result = transcriber.transcribe("/tmp/audio.wav")

        self.assertEqual(result.text, "转写文本")
        self.assertEqual(
            fake_processor_class.from_pretrained.call_args_list,
            [
                mock.call("/models/whisper/medium", local_files_only=True),
                mock.call("openai/whisper-medium", local_files_only=True),
            ],
        )
        fake_processor.save_pretrained.assert_called_once_with("/models/whisper/medium")

    def test_cached_openvino_ir_continues_when_processor_cache_copy_is_read_only(self):
        fake_model = mock.Mock()
        fake_model.generate.return_value = [[1, 2, 3]]
        fake_model_class = mock.Mock()
        fake_model_class.from_pretrained.return_value = fake_model
        fake_processor = self.fake_processor()
        fake_processor.save_pretrained.side_effect = OSError("read-only model dir")
        fake_processor_class = mock.Mock()
        fake_processor_class.from_pretrained.side_effect = [OSError("missing local processor"), fake_processor]
        fake_audio_loader = mock.Mock(return_value=[0.0] * 16000)

        transcriber = OpenVinoWhisperTranscriber(
            model_dir="/models/whisper",
            model_size="medium",
            model_class=fake_model_class,
            processor_class=fake_processor_class,
            audio_loader=fake_audio_loader,
            path_exists=lambda path: path.endswith("/models/whisper/medium/openvino_encoder_model.xml"),
            make_dirs=mock.Mock(),
        )

        result = transcriber.transcribe("/tmp/audio.wav")

        self.assertEqual(result.text, "转写文本")
        fake_processor.save_pretrained.assert_called_once_with("/models/whisper/medium")

    def test_exports_missing_model_to_configured_model_dir(self):
        fake_model = mock.Mock()
        fake_model.generate.return_value = [[1, 2, 3]]
        fake_model_class = mock.Mock()
        fake_model_class.from_pretrained.return_value = fake_model
        fake_processor = self.fake_processor()
        fake_processor_class = mock.Mock()
        fake_processor_class.from_pretrained.return_value = fake_processor

        transcriber = OpenVinoWhisperTranscriber(
            model_dir="/project/models/whisper",
            model_size="small",
            model_class=fake_model_class,
            processor_class=fake_processor_class,
            audio_loader=mock.Mock(return_value=[0.0] * 16000),
            path_exists=lambda path: False,
            make_dirs=mock.Mock(),
        )

        transcriber.transcribe("/tmp/audio.wav")

        fake_model_class.from_pretrained.assert_called_once_with(
            "openai/whisper-small",
            export=True,
            compile=False,
            device="GPU",
            local_files_only=True,
            ov_config={"PERFORMANCE_HINT": "LATENCY"},
        )
        fake_model.save_pretrained.assert_called_once_with("/project/models/whisper/small")
        fake_processor.save_pretrained.assert_called_once_with("/project/models/whisper/small")
        fake_model.compile.assert_called_once()

    def test_missing_openvino_stack_maps_to_whisper_unavailable(self):
        transcriber = OpenVinoWhisperTranscriber(model_dir="/models/whisper")

        with self.assertRaises(KmError) as caught:
            transcriber.transcribe("/tmp/audio.wav")

        self.assertEqual(caught.exception.error_code, "WHISPER_UNAVAILABLE")

    def fake_processor(self):
        processor = mock.Mock()
        processor.feature_extractor.return_value.input_features = "features"
        processor.tokenizer.decode.return_value = "转写文本"
        return processor


if __name__ == "__main__":
    unittest.main()
