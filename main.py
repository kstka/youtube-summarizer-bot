import asyncio

from summarizer.logging_setup import setup_logging

setup_logging()

from summarizer.sentry_setup import init_sentry
from summarizer.app import main

if __name__ == '__main__':
    sentry_enabled = init_sentry()
    asyncio.run(main(sentry_enabled=sentry_enabled))
