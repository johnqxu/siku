from pathlib import Path
import tempfile
import unittest
from unittest import mock

from km.bilibili import (
    BilibiliMetadata,
    BilibiliPipelineError,
    BilibiliSubtitle,
    YtDlpBilibiliDownloader,
    LocalAudio,
    TranscriptionResult,
    collect_bilibili_transcript,
)
from km.errors import KmError


class FakeDownloader:
    def __init__(self, *, subtitle=None, metadata_error=None, audio_error=None):
        self.subtitle = subtitle
        self.metadata_error = metadata_error
        self.audio_error = audio_error
        self.audio_downloads = 0

    def fetch_metadata(self, source_url):
        if self.metadata_error is not None:
            raise self.metadata_error
        return BilibiliMetadata(
            title="测试视频",
            uploader="测试 UP",
            source_url=source_url,
            canonical_url="https://www.bilibili.com/video/BV1xx411c7mD",
        )

    def fetch_subtitle(self, metadata):
        return self.subtitle

    def download_audio(self, metadata, raw_dir):
        self.audio_downloads += 1
        if self.audio_error is not None:
            raise self.audio_error
        path = raw_dir / "audio.wav"
        path.write_bytes(b"fake audio")
        return LocalAudio(path=path)


class FakeTranscriber:
    def __init__(self, *, unavailable=False, failure=False):
        self.unavailable = unavailable
        self.failure = failure
        self.calls = []

    def transcribe(self, audio_path):
        self.calls.append(audio_path)
        if self.unavailable:
            raise KmError("WHISPER_UNAVAILABLE", "OpenVINO GPU 不可用。", True, 2)
        if self.failure:
            raise KmError("BILIBILI_TRANSCRIPT_FAILED", "Whisper 转写失败。", True, 2)
        return TranscriptionResult(text="Whisper 转写文本")


class BilibiliPipelineTests(unittest.TestCase):
    def make_asset_dir(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        asset_dir = Path(root.name)
        (asset_dir / "raw").mkdir()
        (asset_dir / "canonical").mkdir()
        (asset_dir / "summary").mkdir()
        return asset_dir

    def test_uses_subtitle_to_create_canonical_transcript_without_downloading_audio(self):
        asset_dir = self.make_asset_dir()
        downloader = FakeDownloader(
            subtitle=BilibiliSubtitle(
                filename="subtitle.srt",
                text="1\n00:00:00,000 --> 00:00:02,000\n字幕文本\n",
            )
        )
        transcriber = FakeTranscriber()

        result = collect_bilibili_transcript(
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            asset_dir=asset_dir,
            downloader=downloader,
            transcriber=transcriber,
        )

        transcript_path = asset_dir / "canonical" / "transcript.md"
        metadata_path = asset_dir / "raw" / "metadata.json"
        subtitle_path = asset_dir / "raw" / "subtitle.srt"
        self.assertEqual(result.status, "transcript_ready")
        self.assertEqual(result.canonical_text_path, transcript_path)
        self.assertIn("字幕文本", transcript_path.read_text(encoding="utf-8"))
        self.assertTrue(metadata_path.is_file())
        self.assertTrue(subtitle_path.is_file())
        self.assertEqual(downloader.audio_downloads, 0)
        self.assertEqual(transcriber.calls, [])
        self.assertEqual(result.asset_manifest["metadata"], str(metadata_path))
        self.assertEqual(result.asset_manifest["subtitle"], str(subtitle_path))
        self.assertEqual(result.asset_manifest["canonical_text"], str(transcript_path))

    def test_downloads_audio_and_uses_whisper_when_subtitle_missing(self):
        asset_dir = self.make_asset_dir()
        downloader = FakeDownloader(subtitle=None)
        transcriber = FakeTranscriber()

        result = collect_bilibili_transcript(
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            asset_dir=asset_dir,
            downloader=downloader,
            transcriber=transcriber,
        )

        audio_path = asset_dir / "raw" / "audio.wav"
        transcript_path = asset_dir / "canonical" / "transcript.md"
        self.assertEqual(downloader.audio_downloads, 1)
        self.assertEqual(transcriber.calls, [audio_path])
        self.assertIn("Whisper 转写文本", transcript_path.read_text(encoding="utf-8"))
        self.assertEqual(result.asset_manifest["audio"], str(audio_path))
        self.assertEqual(result.asset_manifest["canonical_text"], str(transcript_path))

    def test_maps_metadata_failure_to_public_error(self):
        asset_dir = self.make_asset_dir()
        downloader = FakeDownloader(metadata_error=BilibiliPipelineError("metadata boom"))

        with self.assertRaises(KmError) as caught:
            collect_bilibili_transcript(
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
                asset_dir=asset_dir,
                downloader=downloader,
                transcriber=FakeTranscriber(),
            )

        self.assertEqual(caught.exception.error_code, "BILIBILI_METADATA_FAILED")

    def test_maps_audio_download_failure_to_transcript_error(self):
        asset_dir = self.make_asset_dir()
        downloader = FakeDownloader(subtitle=None, audio_error=BilibiliPipelineError("audio boom"))

        with self.assertRaises(KmError) as caught:
            collect_bilibili_transcript(
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
                asset_dir=asset_dir,
                downloader=downloader,
                transcriber=FakeTranscriber(),
            )

        self.assertEqual(caught.exception.error_code, "BILIBILI_TRANSCRIPT_FAILED")

    def test_preserves_whisper_unavailable_error(self):
        asset_dir = self.make_asset_dir()

        with self.assertRaises(KmError) as caught:
            collect_bilibili_transcript(
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
                asset_dir=asset_dir,
                downloader=FakeDownloader(subtitle=None),
                transcriber=FakeTranscriber(unavailable=True),
            )

        self.assertEqual(caught.exception.error_code, "WHISPER_UNAVAILABLE")

    def test_preserves_whisper_transcription_failure(self):
        asset_dir = self.make_asset_dir()

        with self.assertRaises(KmError) as caught:
            collect_bilibili_transcript(
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
                asset_dir=asset_dir,
                downloader=FakeDownloader(subtitle=None),
                transcriber=FakeTranscriber(failure=True),
            )

        self.assertEqual(caught.exception.error_code, "BILIBILI_TRANSCRIPT_FAILED")


class YtDlpBilibiliDownloaderTests(unittest.TestCase):
    def test_fetch_metadata_parses_yt_dlp_json(self):
        runner = mock.Mock()
        runner.return_value.stdout = (
            '{"title":"测试视频","uploader":"测试 UP",'
            '"webpage_url":"https://www.bilibili.com/video/BV1xx411c7mD"}'
        )
        downloader = YtDlpBilibiliDownloader(runner=runner)

        metadata = downloader.fetch_metadata("https://www.bilibili.com/video/BV1xx411c7mD")

        self.assertEqual(metadata.title, "测试视频")
        self.assertEqual(metadata.uploader, "测试 UP")
        self.assertEqual(metadata.canonical_url, "https://www.bilibili.com/video/BV1xx411c7mD")
        self.assertEqual(metadata.source_url, "https://www.bilibili.com/video/BV1xx411c7mD")
        command = runner.call_args.args[0]
        self.assertIn("--dump-single-json", command)
        self.assertIn("--add-header", command)
        self.assertIn("Referer: https://www.bilibili.com", command)
        self.assertIn("Origin: https://www.bilibili.com", command)
        self.assertIn("--user-agent", command)

    def test_fetch_subtitle_reads_inline_subtitle_text_from_metadata(self):
        metadata = BilibiliMetadata(
            title="测试视频",
            uploader="测试 UP",
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            raw_info={
                "subtitles": {
                    "zh-CN": [
                        {
                            "ext": "srt",
                            "data": "1\n00:00:00,000 --> 00:00:01,000\n字幕文本\n",
                        }
                    ]
                }
            },
        )
        downloader = YtDlpBilibiliDownloader(runner=mock.Mock())

        subtitle = downloader.fetch_subtitle(metadata)

        self.assertIsNotNone(subtitle)
        self.assertEqual(subtitle.filename, "subtitle.zh-CN.srt")
        self.assertIn("字幕文本", subtitle.text)

    def test_download_audio_returns_path_printed_by_yt_dlp(self):
        with tempfile.TemporaryDirectory() as root:
            raw_dir = Path(root)
            audio_path = raw_dir / "audio.wav"
            audio_path.write_bytes(b"fake")
            runner = mock.Mock()
            runner.return_value.stdout = f"{audio_path}\n"
            downloader = YtDlpBilibiliDownloader(runner=runner)
            metadata = BilibiliMetadata(
                title="测试视频",
                uploader="测试 UP",
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            )

            audio = downloader.download_audio(metadata, raw_dir)

        self.assertEqual(audio.path, audio_path)
        command = runner.call_args.args[0]
        self.assertIn("--extract-audio", command)
        self.assertIn("wav", command)
        self.assertIn("--print", command)
        self.assertIn("--add-header", command)
        self.assertIn("Referer: https://www.bilibili.com", command)
        self.assertIn("Origin: https://www.bilibili.com", command)
        self.assertIn("--user-agent", command)

if __name__ == "__main__":
    unittest.main()
