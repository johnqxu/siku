from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any

from .errors import whisper_unavailable


@dataclass(frozen=True)
class TranscriptionResult:
    text: str


class OpenVinoWhisperTranscriber:
    _CHUNK_SAMPLES = 30 * 16000

    def __init__(
        self,
        model_dir: str,
        device: str = "GPU",
        model_size: str = "medium",
        model_class: Any | None = None,
        processor_class: Any | None = None,
        audio_loader: Any | None = None,
        path_exists: Any | None = None,
        make_dirs: Any | None = None,
    ) -> None:
        if device == "CPU":
            raise ValueError("阶段四要求使用 Intel GPU，不允许静默 CPU fallback。")
        self.model_dir = model_dir
        self.device = device
        self.model_size = model_size
        self._model_class = model_class
        self._processor_class = processor_class
        self._audio_loader = audio_loader
        self._path_exists = path_exists
        self._make_dirs = make_dirs
        self._model = None
        self._processor = None

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        try:
            model, processor = self._load_model()
            audio = self._load_audio(str(audio_path))
            text = self._transcribe_audio(audio, model, processor)
        except Exception as exc:
            raise whisper_unavailable(f"OpenVINO Whisper GPU 转写不可用: {exc}") from exc
        if not isinstance(text, str) or not text.strip():
            raise whisper_unavailable("OpenVINO Whisper GPU 未返回有效转写文本。")
        return TranscriptionResult(text=text)

    def _load_model(self):
        if self._model is not None and self._processor is not None:
            return self._model, self._processor

        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        model_class, processor_class = self._load_openvino_stack()
        model_id = f"openai/whisper-{self.model_size}"
        local_path = Path(self.model_dir).expanduser() / self.model_size

        if self._exists(local_path / "openvino_encoder_model.xml"):
            processor = self._load_processor(processor_class, model_id, local_path)
            model = model_class.from_pretrained(
                str(local_path),
                export=False,
                compile=True,
                device=self.device,
                local_files_only=True,
                ov_config={"PERFORMANCE_HINT": "LATENCY"},
            )
        else:
            processor = processor_class.from_pretrained(model_id, local_files_only=True)
            # Phase 1: export PyTorch -> OpenVINO IR without device compilation
            model = model_class.from_pretrained(
                model_id,
                export=True,
                compile=False,
                device=self.device,
                local_files_only=True,
                ov_config={"PERFORMANCE_HINT": "LATENCY"},
            )
            # Save IR immediately — persists even if GPU compilation fails
            self._mkdir(local_path)
            model.save_pretrained(str(local_path))
            processor.save_pretrained(str(local_path))

            # Phase 2: compile for target device
            try:
                model.compile()
            except Exception as exc:
                print(
                    f"km: Warning: Failed to compile Whisper model for {self.device}: {exc}",
                    file=sys.stderr,
                )
                print(
                    f"km: The OpenVINO IR has been saved to {local_path}. "
                    "Re-running will use the cached model.",
                    file=sys.stderr,
                )
                raise whisper_unavailable(
                    f"OpenVINO Whisper GPU compile failed for device '{self.device}': {exc}"
                ) from exc

        print(f"km: Whisper model loaded on {model._device}", file=sys.stderr)

        self._model = model
        self._processor = processor
        return model, processor

    def _load_processor(self, processor_class, model_id: str, local_path: Path):
        try:
            return processor_class.from_pretrained(str(local_path), local_files_only=True)
        except Exception:
            processor = processor_class.from_pretrained(model_id, local_files_only=True)
            try:
                self._mkdir(local_path)
                processor.save_pretrained(str(local_path))
            except Exception as exc:
                print(
                    f"km: Warning: Failed to cache Whisper processor to {local_path}: {exc}",
                    file=sys.stderr,
                )
            return processor

    def _load_openvino_stack(self):
        if self._model_class is not None and self._processor_class is not None:
            return self._model_class, self._processor_class
        try:
            from optimum.intel import OVModelForSpeechSeq2Seq  # type: ignore[import-not-found]
            from transformers import WhisperProcessor  # type: ignore[import-not-found]
        except ImportError as exc:
            raise whisper_unavailable("缺少 OpenVINO/optimum-intel Whisper GPU 运行时。") from exc
        return OVModelForSpeechSeq2Seq, WhisperProcessor

    def _load_audio(self, audio_path: str):
        if self._audio_loader is not None:
            return self._audio_loader(audio_path)
        try:
            import soundfile as sf  # type: ignore[import-not-found]
        except ImportError as exc:
            raise whisper_unavailable("缺少 soundfile 音频读取依赖。") from exc

        audio, sample_rate = sf.read(audio_path, dtype="float32")
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        if sample_rate != 16000:
            try:
                import librosa  # type: ignore[import-not-found]
            except ImportError as exc:
                raise whisper_unavailable("缺少 librosa 音频重采样依赖。") from exc
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
        return audio

    def _transcribe_audio(self, audio, model, processor) -> str:
        total_samples = len(audio)
        if total_samples <= self._CHUNK_SAMPLES:
            return self._transcribe_chunk(audio, model, processor)

        chunks: list[str] = []
        offset = 0
        while offset < total_samples:
            chunk = audio[offset : offset + self._CHUNK_SAMPLES]
            chunk_text = self._transcribe_chunk(chunk, model, processor)
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
            offset += self._CHUNK_SAMPLES
        return "\n".join(chunks)

    def _transcribe_chunk(self, audio_chunk, model, processor) -> str:
        input_features = processor.feature_extractor(
            audio_chunk,
            sampling_rate=16000,
            return_tensors="pt",
        ).input_features
        generated = model.generate(
            input_features,
            language="zh",
            task="transcribe",
            return_timestamps=False,
        )
        if hasattr(generated, "cpu") and callable(generated.cpu):
            generated = generated.cpu().numpy()
        return processor.tokenizer.decode(generated[0], skip_special_tokens=True)

    def _exists(self, path: Path) -> bool:
        if self._path_exists is not None:
            return bool(self._path_exists(str(path)))
        return path.exists()

    def _mkdir(self, path: Path) -> None:
        if self._make_dirs is not None:
            self._make_dirs(str(path))
        else:
            path.mkdir(parents=True, exist_ok=True)
