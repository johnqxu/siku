from __future__ import annotations

from dataclasses import dataclass, field
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Callable, Protocol
from urllib.parse import urlparse

from .errors import KmError, web_fetch_failed, web_parse_failed


class WebArticlePipelineError(Exception):
    pass


@dataclass(frozen=True)
class FetchedWebArticle:
    source_url: str
    html: str | None
    content_type: str
    fetch_method: str = "http"


@dataclass(frozen=True)
class ParsedWebArticle:
    title: str
    body_markdown: str
    parser_id: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class WebArticleContentResult:
    status: str
    content_type: str
    source_url: str
    asset_dir: Path
    canonical_text_path: Path
    asset_manifest: dict[str, str]
    parser_id: str
    fetch_method: str


class WebArticleFetcher(Protocol):
    def fetch(self, source_url: str) -> FetchedWebArticle:
        ...


class HttpWebArticleFetcher:
    def __init__(self, *, timeout: float = 15.0, httpx_module=None) -> None:
        self._timeout = timeout
        self._httpx = httpx_module

    def fetch(self, source_url: str) -> FetchedWebArticle:
        httpx_module = self._httpx
        if httpx_module is None:
            try:
                import httpx as httpx_module
            except ModuleNotFoundError as exc:
                raise WebArticlePipelineError("缺少 httpx 依赖。") from exc
        try:
            response = httpx_module.get(
                source_url,
                timeout=self._timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; siku-km/0.1; "
                        "+https://example.invalid/siku)"
                    )
                },
            )
            response.raise_for_status()
        except Exception as exc:
            raise WebArticlePipelineError("网页 HTTP 抓取失败。") from exc

        content_type = response.headers.get("content-type", "")
        text = response.text
        if not _is_html_response(content_type, text):
            raise WebArticlePipelineError("网页响应不是 HTML。")
        return FetchedWebArticle(
            source_url=str(getattr(response, "url", source_url)),
            html=text,
            content_type=content_type,
            fetch_method="http",
        )


class WechatArticleParser:
    parser_id = "wechat_article"

    def __init__(self, *, beautifulsoup_class=None) -> None:
        self._beautifulsoup_class = beautifulsoup_class

    def parse(self, page_html: str, source_url: str) -> ParsedWebArticle:
        parsed = self._parse_with_beautifulsoup(page_html, source_url)
        if parsed is not None:
            return parsed
        return self._parse_with_stdlib(page_html, source_url)

    def _parse_with_beautifulsoup(self, page_html: str, source_url: str) -> ParsedWebArticle | None:
        beautifulsoup_class = self._beautifulsoup_class
        if beautifulsoup_class is None:
            try:
                from bs4 import BeautifulSoup as beautifulsoup_class
            except ModuleNotFoundError:
                return None
        soup = beautifulsoup_class(page_html, "html.parser")
        title_node = soup.find(id="activity-name") or soup.select_one("meta[property='og:title']")
        content_node = soup.find(id="js_content")
        author_node = soup.find(id="js_name") or soup.find(id="js_author")
        published_node = soup.find(id="publish_time")

        title = _node_text(title_node)
        if not title and hasattr(title_node, "get"):
            title = _first_nonblank(title_node.get("content"))
        body = _node_text(content_node)
        if not title or not body:
            return None
        body_markdown = _text_to_markdown(body)
        if not body_markdown:
            return None
        metadata = {
            "title": title,
            "source_url": source_url,
            "parser_id": self.parser_id,
        }
        author = _node_text(author_node)
        published_at = _node_text(published_node)
        if author:
            metadata["author"] = author
        if published_at:
            metadata["published_at"] = published_at
        return ParsedWebArticle(
            title=title,
            body_markdown=body_markdown,
            parser_id=self.parser_id,
            metadata=metadata,
        )

    def _parse_with_stdlib(self, page_html: str, source_url: str) -> ParsedWebArticle:
        extractor = _WechatHtmlExtractor()
        extractor.feed(page_html)
        title = _first_nonblank(
            extractor.by_id.get("activity-name"),
            extractor.meta.get("og:title"),
            extractor.title,
        )
        body = extractor.by_id.get("js_content", "")
        if not title or not body:
            raise WebArticlePipelineError("微信公众号正文解析失败。")
        body_markdown = _text_to_markdown(body)
        if not body_markdown:
            raise WebArticlePipelineError("微信公众号正文为空。")
        metadata = {
            "title": title,
            "source_url": source_url,
            "parser_id": self.parser_id,
        }
        author = _first_nonblank(extractor.by_id.get("js_name"), extractor.by_id.get("js_author"))
        published_at = _first_nonblank(extractor.by_id.get("publish_time"))
        if author:
            metadata["author"] = author
        if published_at:
            metadata["published_at"] = published_at
        return ParsedWebArticle(
            title=title,
            body_markdown=body_markdown,
            parser_id=self.parser_id,
            metadata=metadata,
        )


class GenericArticleParser:
    parser_id = "generic_article"

    def __init__(
        self,
        *,
        trafilatura_module=None,
        extractor: Callable[[str, str], object] | None = None,
    ) -> None:
        self._trafilatura = trafilatura_module
        self._extractor = extractor

    def parse(self, page_html: str, source_url: str) -> ParsedWebArticle:
        if self._extractor is not None:
            extracted = self._extractor(page_html, source_url)
        else:
            extracted = self._extract_with_trafilatura(page_html, source_url)
        if extracted is None:
            raise WebArticlePipelineError("通用网页正文解析失败。")
        payload = _coerce_extracted_payload(extracted)
        title = _first_nonblank(payload.get("title"), _html_title(page_html))
        body = _first_nonblank(payload.get("text"), payload.get("raw_text"), payload.get("body"))
        if not title or not body:
            raise WebArticlePipelineError("通用网页标题或正文为空。")
        body_markdown = _remove_leading_title(_text_to_markdown(body), title)
        if not body_markdown:
            raise WebArticlePipelineError("通用网页正文为空。")
        html_metadata = _html_metadata(page_html)
        metadata = {
            "title": title,
            "source_url": source_url,
            "parser_id": self.parser_id,
        }
        for source_key, target_key in (
            ("author", "author"),
            ("date", "published_at"),
            ("sitename", "site_name"),
            ("hostname", "host_name"),
        ):
            value = _first_nonblank(payload.get(source_key))
            if value:
                metadata[target_key] = value
        for key in ("author", "published_at", "site_name"):
            value = html_metadata.get(key)
            if value and key not in metadata:
                metadata[key] = value
        return ParsedWebArticle(
            title=title,
            body_markdown=body_markdown,
            parser_id=self.parser_id,
            metadata=metadata,
        )

    def _extract_with_trafilatura(self, page_html: str, source_url: str) -> object:
        trafilatura_module = self._trafilatura
        if trafilatura_module is None:
            try:
                import trafilatura as trafilatura_module
            except ModuleNotFoundError as exc:
                raise WebArticlePipelineError("缺少 trafilatura 依赖。") from exc
        return trafilatura_module.extract(
            page_html,
            output_format="json",
            include_comments=False,
            include_tables=True,
            url=source_url,
        )


def resolve_web_article_parser(source_url: str) -> str:
    host = (urlparse(source_url).hostname or "").lower()
    if host == "mp.weixin.qq.com":
        return "wechat_article"
    return "generic_article"


def collect_web_article(
    *,
    source_url: str,
    asset_dir: Path,
    fetcher: WebArticleFetcher,
    wechat_parser: WechatArticleParser | None = None,
    generic_parser: GenericArticleParser | None = None,
) -> WebArticleContentResult:
    raw_dir = asset_dir / "raw"
    canonical_dir = asset_dir / "canonical"
    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir.mkdir(parents=True, exist_ok=True)

    try:
        fetched = fetcher.fetch(source_url)
        if not _is_html_response(fetched.content_type, fetched.html or ""):
            raise WebArticlePipelineError("网页响应不是 HTML。")
    except Exception as exc:
        raise web_fetch_failed("网页抓取失败。") from exc

    page_path = raw_dir / "page.html"
    page_path.write_text(fetched.html or "", encoding="utf-8")
    manifest = {"html": str(page_path)}

    parser_id = resolve_web_article_parser(source_url)
    if parser_id == "wechat_article":
        parser = wechat_parser or WechatArticleParser()
    else:
        parser = generic_parser or GenericArticleParser()
    try:
        parsed = parser.parse(fetched.html or "", source_url)
    except KmError:
        raise
    except Exception as exc:
        raise web_parse_failed("网页正文解析失败。") from exc

    metadata = dict(parsed.metadata)
    metadata.setdefault("title", parsed.title)
    metadata.setdefault("source_url", source_url)
    metadata["parser_id"] = parsed.parser_id
    metadata["fetch_method"] = fetched.fetch_method
    metadata["content_type"] = "web_article"

    metadata_path = raw_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["metadata"] = str(metadata_path)

    content_path = canonical_dir / "content.md"
    content_path.write_text(
        _to_canonical_markdown(
            title=parsed.title,
            source_url=source_url,
            body_markdown=parsed.body_markdown,
        ),
        encoding="utf-8",
    )
    manifest["canonical_text"] = str(content_path)

    return WebArticleContentResult(
        status="content_ready",
        content_type="web_article",
        source_url=source_url,
        asset_dir=asset_dir,
        canonical_text_path=content_path,
        asset_manifest=manifest,
        parser_id=parsed.parser_id,
        fetch_method=fetched.fetch_method,
    )


def _is_html_response(content_type: str, text: str) -> bool:
    lowered = content_type.lower()
    if "html" in lowered:
        return True
    stripped = text.lstrip().lower()
    return stripped.startswith("<!doctype html") or stripped.startswith("<html")


def _coerce_extracted_payload(extracted: object) -> dict[str, str]:
    if isinstance(extracted, dict):
        return {str(key): str(value) for key, value in extracted.items() if value is not None}
    if isinstance(extracted, str):
        stripped = extracted.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return {"text": stripped}
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items() if value is not None}
    return {}


def _html_title(page_html: str) -> str:
    extractor = _GenericHtmlExtractor()
    extractor.feed(page_html)
    return extractor.title


def _html_metadata(page_html: str) -> dict[str, str]:
    extractor = _MetadataHtmlExtractor()
    extractor.feed(page_html)
    metadata: dict[str, str] = {}
    author = _first_nonblank(extractor.values.get("author"), extractor.values.get("article:author"))
    published_at = _first_nonblank(
        extractor.values.get("article:published_time"),
        extractor.values.get("date"),
        extractor.values.get("publishdate"),
        extractor.values.get("pubdate"),
    )
    site_name = _first_nonblank(extractor.values.get("og:site_name"), extractor.values.get("application-name"))
    if author:
        metadata["author"] = author
    if published_at:
        metadata["published_at"] = published_at
    if site_name:
        metadata["site_name"] = site_name
    return metadata


def _first_nonblank(*values: str | None) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return html.unescape(value.strip())
    return ""


def _node_text(node: object) -> str:
    if node is None:
        return ""
    get_text = getattr(node, "get_text", None)
    if callable(get_text):
        return _first_nonblank(get_text(separator="\n", strip=True))
    return _first_nonblank(str(node))


def _text_to_markdown(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = re.sub(r"\s+", " ", html.unescape(line)).strip()
        if stripped:
            lines.append(stripped)
    return "\n\n".join(lines)


def _remove_leading_title(body_markdown: str, title: str) -> str:
    parts = body_markdown.split("\n\n")
    if parts and _normalize_heading(parts[0]) == _normalize_heading(title):
        return "\n\n".join(parts[1:]).strip()
    return body_markdown


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", "", html.unescape(text)).strip()


def _to_canonical_markdown(*, title: str, source_url: str, body_markdown: str) -> str:
    return f"# {title.strip()}\n\n来源：{source_url}\n\n{body_markdown.strip()}\n"


class _WechatHtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.by_id: dict[str, str] = {}
        self.meta: dict[str, str] = {}
        self.title = ""
        self._capture_stack: list[str] = []
        self._title_active = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            content = attributes.get("content")
            if key and content:
                self.meta[key] = content
        element_id = attributes.get("id")
        if element_id in {"activity-name", "js_name", "js_author", "publish_time", "js_content"}:
            self._capture_stack.append(element_id)
            self.by_id.setdefault(element_id, "")
        if tag == "title":
            self._title_active = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title_active = False
        if self._capture_stack and tag in {"h1", "span", "em", "div"}:
            self._capture_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._title_active:
            self.title += data
        if self._capture_stack:
            key = self._capture_stack[-1]
            self.by_id[key] = f"{self.by_id.get(key, '')}\n{data}"


class _GenericHtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.article = ""
        self.body = ""
        self._title_active = False
        self._article_depth = 0
        self._body_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._title_active = True
        if tag == "article":
            self._article_depth += 1
        if tag == "body":
            self._body_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title_active = False
        if tag == "article" and self._article_depth:
            self._article_depth -= 1
        if tag == "body" and self._body_depth:
            self._body_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_active:
            self.title += data
        if self._article_depth:
            self.article += f"\n{data}"
        elif self._body_depth:
            self.body += f"\n{data}"


class _MetadataHtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attributes = dict(attrs)
        key = attributes.get("property") or attributes.get("name")
        content = attributes.get("content")
        if key and content:
            self.values[key.lower()] = content
