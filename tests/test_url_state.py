import hashlib
import unittest

from km.errors import KmError
from km.url_state import generate_source_id, normalize_url


class UrlStateTests(unittest.TestCase):
    def test_normalize_url_lowercases_scheme_and_host_removes_fragment_and_keeps_query(self):
        normalized = normalize_url("  HTTPS://Example.COM:8443/Some/Path?b=2&A=1#section  ")

        self.assertEqual(normalized.original_url, "HTTPS://Example.COM:8443/Some/Path?b=2&A=1#section")
        self.assertEqual(normalized.normalized_url, "https://example.com:8443/Some/Path?b=2&A=1")

    def test_normalize_url_rejects_non_http_scheme(self):
        with self.assertRaises(KmError) as raised:
            normalize_url("ftp://example.com/file")

        self.assertEqual(raised.exception.error_code, "INPUT_INVALID")

    def test_normalize_url_rejects_missing_host(self):
        with self.assertRaises(KmError) as raised:
            normalize_url("https:///missing-host")

        self.assertEqual(raised.exception.error_code, "INPUT_INVALID")

    def test_generate_source_id_uses_full_sha256_hex(self):
        normalized = normalize_url("https://example.com/articles/1?a=1#fragment")

        source_id = generate_source_id(normalized.normalized_url)

        self.assertEqual(source_id, hashlib.sha256(b"https://example.com/articles/1?a=1").hexdigest())
        self.assertEqual(len(source_id), 64)


if __name__ == "__main__":
    unittest.main()
