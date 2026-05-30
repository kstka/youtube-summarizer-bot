import os
import random
import re
from typing import Optional
from urllib.parse import urlparse
from urllib.request import build_opener, install_opener

import socks
from loguru import logger
from sockshandler import SocksiPyHandler
from youtube_transcript_api.proxies import GenericProxyConfig

from pytubefix.helpers import install_proxy

SUPPORTED_SCHEMES = frozenset({'http', 'https', 'socks5', 'socks5h'})


def parse_proxy_urls(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = re.split(r'[,\n]+', raw)
    return [part.strip() for part in parts if part.strip()]


def is_valid_proxy_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in SUPPORTED_SCHEMES and bool(parsed.hostname)


def load_proxies_from_env() -> list[str]:
    raw = os.environ.get('YOUTUBE_PROXIES', '')
    proxies = []
    for url in parse_proxy_urls(raw):
        if is_valid_proxy_url(url):
            proxies.append(url)
        else:
            logger.warning('Ignoring invalid YouTube proxy URL scheme={}', urlparse(url).scheme or '(empty)')
    if proxies:
        logger.info('YouTube proxy pool loaded count={}', len(proxies))
    return proxies


def pick_proxy() -> Optional[str]:
    from .config import YouTube

    if not YouTube.PROXIES:
        return None
    return random.choice(YouTube.PROXIES)

def proxy_log_label(url: str) -> str:
    parsed = urlparse(url)
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == 'https' else 80
    return f'{parsed.scheme}://{parsed.hostname}:{port}'


def proxy_config_for_transcript_api(url: str) -> GenericProxyConfig:
    return GenericProxyConfig(http_url=url, https_url=url)


def install_pytubefix_proxy(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme in ('socks5', 'socks5h'):
        port = parsed.port or 1080
        handler = SocksiPyHandler(
            socks.SOCKS5,
            parsed.hostname,
            port,
            username=parsed.username,
            password=parsed.password,
        )
        install_opener(build_opener(handler))
        return

    install_proxy({'http': url, 'https': url})
