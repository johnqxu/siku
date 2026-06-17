from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

from km.errors import KmError
from km.web_article import (
    FetchedWebArticle,
    GenericArticleParser,
    HttpWebArticleFetcher,
    WechatArticleParser,
    WebArticlePipelineError,
    collect_web_article,
    resolve_web_article_parser,
)


WECHAT_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta property="og:title" content="微信测试标题">
  </head>
  <body>
    <h1 id="activity-name">微信测试标题</h1>
    <span id="js_name">测试公众号</span>
    <em id="publish_time">2026-06-14</em>
    <div id="js_content">
      <p>第一段正文。</p>
      <p>第二段正文。</p>
    </div>
  </body>
</html>
"""


GENERIC_HTML = """
<!doctype html>
<html>
  <head>
    <title>通用网页标题</title>
    <meta name="author" content="测试作者">
  </head>
  <body>
    <article>
      <h1>通用网页标题</h1>
      <p>这是一篇通用网页的正文内容。</p>
      <p>它应该被抽取到规范 Markdown。</p>
    </article>
  </body>
</html>
"""


class FakeFetcher:
    def __init__(self, html=None, error=None, content_type="text/html; charset=utf-8"):
        self.html = html
        self.error = error
        self.content_type = content_type
        self.calls = []

    def fetch(self, source_url):
        self.calls.append(source_url)
        if self.error is not None:
            raise self.error
        return FetchedWebArticle(
            source_url=source_url,
            html=self.html,
            content_type=self.content_type,
            fetch_method="http",
        )


class WebArticlePipelineTests(unittest.TestCase):
    def make_asset_dir(self):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        asset_dir = Path(root.name)
        (asset_dir / "raw").mkdir()
        (asset_dir / "canonical").mkdir()
        (asset_dir / "summary").mkdir()
        return asset_dir

    def test_collects_wechat_article_to_canonical_content(self):
        asset_dir = self.make_asset_dir()
        source_url = "https://mp.weixin.qq.com/s/test"

        result = collect_web_article(
            source_url=source_url,
            asset_dir=asset_dir,
            fetcher=FakeFetcher(WECHAT_HTML),
        )

        page_path = asset_dir / "raw" / "page.html"
        metadata_path = asset_dir / "raw" / "metadata.json"
        content_path = asset_dir / "canonical" / "content.md"
        self.assertEqual(result.status, "content_ready")
        self.assertEqual(result.content_type, "web_article")
        self.assertEqual(result.parser_id, "wechat_article")
        self.assertEqual(result.fetch_method, "http")
        self.assertEqual(result.canonical_text_path, content_path)
        self.assertEqual(page_path.read_text(encoding="utf-8"), WECHAT_HTML)
        self.assertIn("微信测试标题", content_path.read_text(encoding="utf-8"))
        self.assertIn("第一段正文。", content_path.read_text(encoding="utf-8"))
        self.assertNotIn("<div id=\"js_content\">", content_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["title"], "微信测试标题")
        self.assertEqual(metadata["author"], "测试公众号")
        self.assertEqual(metadata["published_at"], "2026-06-14")
        self.assertEqual(metadata["parser_id"], "wechat_article")
        self.assertEqual(metadata["fetch_method"], "http")
        self.assertEqual(result.asset_manifest["html"], str(page_path))
        self.assertEqual(result.asset_manifest["metadata"], str(metadata_path))
        self.assertEqual(result.asset_manifest["canonical_text"], str(content_path))

    def test_collects_generic_article_with_trafilatura_wrapper(self):
        asset_dir = self.make_asset_dir()
        source_url = "https://example.com/article"
        parser = GenericArticleParser(
            extractor=lambda html, source_url: {
                "title": "通用网页标题",
                "text": "这是一篇通用网页的正文内容。\n它应该被抽取到规范 Markdown。",
            }
        )

        result = collect_web_article(
            source_url=source_url,
            asset_dir=asset_dir,
            fetcher=FakeFetcher(GENERIC_HTML),
            generic_parser=parser,
        )

        content = (asset_dir / "canonical" / "content.md").read_text(encoding="utf-8")
        metadata = json.loads((asset_dir / "raw" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(result.parser_id, "generic_article")
        self.assertIn("通用网页标题", content)
        self.assertIn("通用网页的正文内容", content)
        self.assertEqual(metadata["parser_id"], "generic_article")
        self.assertEqual(metadata["title"], "通用网页标题")

    def test_maps_fetch_failure_to_public_error(self):
        asset_dir = self.make_asset_dir()

        with self.assertRaises(KmError) as caught:
            collect_web_article(
                source_url="https://example.com/article",
                asset_dir=asset_dir,
                fetcher=FakeFetcher(error=WebArticlePipelineError("network boom")),
            )

        self.assertEqual(caught.exception.error_code, "WEB_FETCH_FAILED")

    def test_rejects_non_html_response_as_fetch_failure(self):
        asset_dir = self.make_asset_dir()

        with self.assertRaises(KmError) as caught:
            collect_web_article(
                source_url="https://example.com/file.json",
                asset_dir=asset_dir,
                fetcher=FakeFetcher("{}", content_type="application/json"),
            )

        self.assertEqual(caught.exception.error_code, "WEB_FETCH_FAILED")

    def test_maps_wechat_parse_failure_to_public_error_after_saving_html(self):
        asset_dir = self.make_asset_dir()

        with self.assertRaises(KmError) as caught:
            collect_web_article(
                source_url="https://mp.weixin.qq.com/s/test",
                asset_dir=asset_dir,
                fetcher=FakeFetcher("<html><body>no article</body></html>"),
            )

        self.assertEqual(caught.exception.error_code, "WEB_PARSE_FAILED")
        self.assertTrue((asset_dir / "raw" / "page.html").is_file())

    def test_maps_generic_parse_failure_to_public_error_after_saving_html(self):
        asset_dir = self.make_asset_dir()
        parser = GenericArticleParser(extractor=lambda html, source_url: None)

        with self.assertRaises(KmError) as caught:
            collect_web_article(
                source_url="https://example.com/article",
                asset_dir=asset_dir,
                fetcher=FakeFetcher(GENERIC_HTML),
                generic_parser=parser,
            )

        self.assertEqual(caught.exception.error_code, "WEB_PARSE_FAILED")
        self.assertTrue((asset_dir / "raw" / "page.html").is_file())

    def test_resolves_wechat_and_generic_parser_ids(self):
        self.assertEqual(resolve_web_article_parser("https://mp.weixin.qq.com/s/test"), "wechat_article")
        self.assertEqual(resolve_web_article_parser("https://example.com/article"), "generic_article")

    def test_generic_parser_uses_trafilatura_module(self):
        fake_trafilatura = mock.Mock()
        fake_trafilatura.extract.return_value = json.dumps(
            {
                "title": "通用网页标题",
                "text": "正文文本",
                "author": "测试作者",
                "date": "2026-06-14",
            },
            ensure_ascii=False,
        )
        parser = GenericArticleParser(trafilatura_module=fake_trafilatura)

        parsed = parser.parse(GENERIC_HTML, "https://example.com/article")

        self.assertEqual(parsed.title, "通用网页标题")
        self.assertEqual(parsed.body_markdown, "正文文本")
        self.assertEqual(parsed.metadata["author"], "测试作者")
        fake_trafilatura.extract.assert_called_once()
        _, kwargs = fake_trafilatura.extract.call_args
        self.assertEqual(kwargs["output_format"], "json")
        self.assertEqual(kwargs["url"], "https://example.com/article")

    def test_generic_parser_removes_duplicate_title_from_body(self):
        parser = GenericArticleParser(
            extractor=lambda html, source_url: {
                "title": "通用网页标题",
                "text": "通用网页标题\n\n正文第一段\n\n正文第二段",
            }
        )

        parsed = parser.parse(GENERIC_HTML, "https://example.com/article")

        self.assertEqual(parsed.body_markdown, "正文第一段\n\n正文第二段")

    def test_generic_parser_uses_html_meta_fallbacks(self):
        parser = GenericArticleParser(extractor=lambda html, source_url: {"title": "通用网页标题", "text": "正文"})
        html = """
        <!doctype html>
        <html>
          <head>
            <meta name="author" content="测试作者">
            <meta property="article:published_time" content="2026-06-14">
            <meta property="og:site_name" content="测试站点">
          </head>
          <body><article><p>正文</p></article></body>
        </html>
        """

        parsed = parser.parse(html, "https://example.com/article")

        self.assertEqual(parsed.metadata["author"], "测试作者")
        self.assertEqual(parsed.metadata["published_at"], "2026-06-14")
        self.assertEqual(parsed.metadata["site_name"], "测试站点")

    def test_http_fetcher_returns_html_response(self):
        response = _FakeHttpxResponse(
            text="<html><body>正文</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
            url="https://example.com/canonical",
        )
        httpx_module = _FakeHttpxModule(response=response)
        fetcher = HttpWebArticleFetcher(timeout=3.0, httpx_module=httpx_module)

        fetched = fetcher.fetch("https://example.com/article")

        self.assertEqual(fetched.source_url, "https://example.com/canonical")
        self.assertEqual(fetched.html, "<html><body>正文</body></html>")
        self.assertEqual(fetched.fetch_method, "http")
        self.assertEqual(httpx_module.calls[0]["timeout"], 3.0)
        self.assertTrue(httpx_module.calls[0]["follow_redirects"])
        self.assertIn("User-Agent", httpx_module.calls[0]["headers"])

    def test_http_fetcher_maps_status_failure(self):
        response = _FakeHttpxResponse(
            text="<html></html>",
            headers={"content-type": "text/html"},
            status_error=RuntimeError("bad status"),
        )
        fetcher = HttpWebArticleFetcher(httpx_module=_FakeHttpxModule(response=response))

        with self.assertRaises(WebArticlePipelineError):
            fetcher.fetch("https://example.com/article")

    def test_http_fetcher_rejects_non_html_response(self):
        response = _FakeHttpxResponse(text="{}", headers={"content-type": "application/json"})
        fetcher = HttpWebArticleFetcher(httpx_module=_FakeHttpxModule(response=response))

        with self.assertRaises(WebArticlePipelineError):
            fetcher.fetch("https://example.com/data.json")

    def test_wechat_parser_uses_beautifulsoup_when_available(self):
        fake_soup_class = mock.Mock()
        fake_soup = fake_soup_class.return_value
        fake_soup.find.side_effect = [
            _FakeNode("微信测试标题"),
            _FakeNode("第一段正文。\n第二段正文。"),
            _FakeNode("测试公众号"),
            None,
            _FakeNode("2026-06-14"),
        ]
        fake_soup.find.return_value = None
        fake_soup.select_one.return_value = None
        parser = WechatArticleParser(beautifulsoup_class=fake_soup_class)

        parsed = parser.parse(WECHAT_HTML, "https://mp.weixin.qq.com/s/test")

        self.assertEqual(parsed.title, "微信测试标题")
        self.assertIn("第一段正文。", parsed.body_markdown)
        self.assertEqual(parsed.metadata["author"], "测试公众号")
        fake_soup_class.assert_called_once_with(WECHAT_HTML, "html.parser")


class _FakeNode:
    def __init__(self, text):
        self._text = text

    def get_text(self, separator="\n", strip=False):
        return self._text.strip() if strip else self._text


class _FakeHttpxModule:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get(self, source_url, **kwargs):
        self.calls.append({"source_url": source_url, **kwargs})
        if self.error is not None:
            raise self.error
        return self.response


class _FakeHttpxResponse:
    def __init__(self, *, text, headers, url="https://example.com/article", status_error=None):
        self.text = text
        self.headers = headers
        self.url = url
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error is not None:
            raise self.status_error


if __name__ == "__main__":
    unittest.main()
