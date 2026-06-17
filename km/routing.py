from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class ContentType(StrEnum):
    BILIBILI_VIDEO = "bilibili_video"
    WEB_ARTICLE = "web_article"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RouteResult:
    content_type: ContentType


def route_url(normalized_url: str) -> RouteResult:
    parsed = urlparse(normalized_url)
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    if host in {"www.bilibili.com", "bilibili.com", "m.bilibili.com"}:
        if len(path_parts) >= 2 and path_parts[0] == "video":
            return RouteResult(ContentType.BILIBILI_VIDEO)
        return RouteResult(ContentType.UNSUPPORTED)

    if host == "b23.tv":
        if len(path_parts) == 1:
            return RouteResult(ContentType.BILIBILI_VIDEO)
        return RouteResult(ContentType.UNSUPPORTED)

    return RouteResult(ContentType.WEB_ARTICLE)
