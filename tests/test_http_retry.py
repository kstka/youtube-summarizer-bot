import unittest

import aiohttp

from summarizer.http_retry import with_retries


class TestWithRetries(unittest.IsolatedAsyncioTestCase):
    async def test_succeeds_after_transient_errors(self):
        attempts = 0

        async def coro_factory():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise aiohttp.ClientPayloadError('incomplete body')
            return 'ok'

        result = await with_retries(coro_factory, attempts=3, base_delay=0.01, multiplier=1.0)
        self.assertEqual(result, 'ok')
        self.assertEqual(attempts, 3)

    async def test_raises_after_exhausted_attempts(self):
        async def coro_factory():
            raise aiohttp.ClientPayloadError('incomplete body')

        with self.assertRaises(aiohttp.ClientPayloadError):
            await with_retries(coro_factory, attempts=2, base_delay=0.01, multiplier=1.0)


if __name__ == '__main__':
    unittest.main()
