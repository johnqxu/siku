import unittest

from km.routing import ContentType, route_url


class UrlRoutingTests(unittest.TestCase):
    def test_routes_bilibili_video_pages(self):
        for url in (
            "https://www.bilibili.com/video/BV1xx411c7mD",
            "https://bilibili.com/video/BV1xx411c7mD",
            "https://m.bilibili.com/video/BV1xx411c7mD",
        ):
            with self.subTest(url=url):
                result = route_url(url)

                self.assertEqual(result.content_type, ContentType.BILIBILI_VIDEO)

    def test_routes_b23_short_link_as_bilibili_video_candidate(self):
        result = route_url("https://b23.tv/abc123")

        self.assertEqual(result.content_type, ContentType.BILIBILI_VIDEO)

    def test_routes_non_bilibili_urls_as_web_article_candidates(self):
        for url in ("https://example.com/article", "http://example.com/article"):
            with self.subTest(url=url):
                result = route_url(url)

                self.assertEqual(result.content_type, ContentType.WEB_ARTICLE)

    def test_routes_bilibili_non_video_paths_as_unsupported(self):
        result = route_url("https://www.bilibili.com/read/cv123")

        self.assertEqual(result.content_type, ContentType.UNSUPPORTED)

    def test_routes_empty_b23_path_as_unsupported(self):
        result = route_url("https://b23.tv/")

        self.assertEqual(result.content_type, ContentType.UNSUPPORTED)


if __name__ == "__main__":
    unittest.main()
