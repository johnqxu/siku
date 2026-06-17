from __future__ import annotations

from dataclasses import dataclass
import hashlib
from urllib.parse import urlsplit, urlunsplit

from .errors import input_invalid


@dataclass(frozen=True)
class NormalizedUrl:
    original_url: str
    normalized_url: str


def normalize_url(url: str) -> NormalizedUrl:
    original_url = url.strip()
    parsed = urlsplit(original_url)

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise input_invalid("url 必须是有效的 http 或 https URL。")

    netloc = parsed.hostname.lower()
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    normalized_url = urlunsplit((scheme, netloc, parsed.path, parsed.query, ""))
    return NormalizedUrl(original_url=original_url, normalized_url=normalized_url)


def generate_source_id(normalized_url: str) -> str:
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
