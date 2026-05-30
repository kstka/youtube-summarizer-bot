import unittest
from unittest.mock import patch

from summarizer.youtube_proxy import (
    is_valid_proxy_url,
    load_proxies_from_env,
    parse_proxy_urls,
    pick_proxy,
    proxy_log_label,
)


class TestParseProxyUrls(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(parse_proxy_urls(''), [])
        self.assertEqual(parse_proxy_urls('   '), [])

    def test_comma_separated(self):
        raw = 'socks5://127.0.0.1:1080, http://proxy.example:8080'
        self.assertEqual(
            parse_proxy_urls(raw),
            ['socks5://127.0.0.1:1080', 'http://proxy.example:8080'],
        )

    def test_newline_separated(self):
        raw = 'socks5://127.0.0.1:1080\nhttp://proxy.example:8080'
        self.assertEqual(
            parse_proxy_urls(raw),
            ['socks5://127.0.0.1:1080', 'http://proxy.example:8080'],
        )


class TestIsValidProxyUrl(unittest.TestCase):
    def test_supported_schemes(self):
        self.assertTrue(is_valid_proxy_url('http://127.0.0.1:8080'))
        self.assertTrue(is_valid_proxy_url('https://127.0.0.1:8080'))
        self.assertTrue(is_valid_proxy_url('socks5://127.0.0.1:1080'))
        self.assertTrue(is_valid_proxy_url('socks5h://127.0.0.1:1080'))

    def test_rejects_invalid(self):
        self.assertFalse(is_valid_proxy_url('ftp://127.0.0.1:8080'))
        self.assertFalse(is_valid_proxy_url('http://'))
        self.assertFalse(is_valid_proxy_url('not-a-url'))


class TestLoadProxiesFromEnv(unittest.TestCase):
    def test_filters_invalid_entries(self):
        with patch.dict(
            'os.environ',
            {'YOUTUBE_PROXIES': 'socks5://127.0.0.1:1080,ftp://bad,http://proxy:8080'},
            clear=False,
        ):
            proxies = load_proxies_from_env()
        self.assertEqual(
            proxies,
            ['socks5://127.0.0.1:1080', 'http://proxy:8080'],
        )


class TestPickProxy(unittest.TestCase):
    def test_returns_none_when_empty(self):
        with patch('summarizer.config.YouTube') as youtube:
            youtube.PROXIES = ()
            self.assertIsNone(pick_proxy())

    def test_returns_member_of_pool(self):
        pool = ('http://a:8080', 'socks5://b:1080')
        with patch('summarizer.config.YouTube') as youtube:
            youtube.PROXIES = pool
            picked = pick_proxy()
        self.assertIn(picked, pool)


class TestProxyLogLabel(unittest.TestCase):
    def test_hides_credentials(self):
        label = proxy_log_label('http://user:secret@proxy.example:8080')
        self.assertNotIn('user', label)
        self.assertNotIn('secret', label)
        self.assertEqual(label, 'http://proxy.example:8080')

    def test_default_ports(self):
        self.assertEqual(proxy_log_label('http://proxy.example'), 'http://proxy.example:80')
        self.assertEqual(proxy_log_label('https://proxy.example'), 'https://proxy.example:443')


if __name__ == '__main__':
    unittest.main()
