import asyncio

import aiohttp

RETRIABLE_EXC = (aiohttp.ClientError, asyncio.TimeoutError)

LLM_CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=600, connect=30, sock_read=600)


async def with_retries(coro_factory, attempts=3, base_delay=2.0, multiplier=3.0):
    for i in range(attempts):
        try:
            return await coro_factory()
        except RETRIABLE_EXC:
            if i == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (multiplier ** i))
