#!/usr/bin/env python3
"""Check each URL in YOUTUBE_PROXIES (.env) for YouTube connectivity."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

from summarizer.youtube_proxy import (
    install_pytubefix_proxy,
    load_proxies_from_env,
    proxy_config_for_transcript_api,
    proxy_log_label,
)

DEFAULT_VIDEO_ID = 'jNQXAC9IVRw'
DEFAULT_VIDEO_URL = f'https://www.youtube.com/watch?v={DEFAULT_VIDEO_ID}'


@dataclass
class ProxyCheckResult:
    label: str
    subtitles_ok: bool
    subtitles_error: Optional[str]
    pytubefix_ok: bool
    pytubefix_error: Optional[str]

    @property
    def ok(self) -> bool:
        return self.subtitles_ok and self.pytubefix_ok


def check_subtitles(proxy_url: str, video_id: str) -> tuple[bool, Optional[str]]:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        InvalidVideoId,
        NoTranscriptFound,
        VideoUnavailable,
    )

    api = YouTubeTranscriptApi(
        proxy_config=proxy_config_for_transcript_api(proxy_url),
    )
    try:
        api.fetch(video_id, languages=['en', 'ru'])
        return True, None
    except (NoTranscriptFound, VideoUnavailable, InvalidVideoId) as exc:
        return False, f'{type(exc).__name__}: {exc}'
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


def check_pytubefix(proxy_url: str, video_url: str) -> tuple[bool, Optional[str]]:
    import pytubefix as pytube

    install_pytubefix_proxy(proxy_url)
    try:
        yt = pytube.YouTube(video_url)
        if not yt.title:
            return False, 'empty video title'
        return True, None
    except Exception as exc:
        return False, f'{type(exc).__name__}: {exc}'


def check_proxy(
    proxy_url: str,
    *,
    video_id: str,
    video_url: str,
    skip_subtitles: bool,
    skip_pytubefix: bool,
) -> ProxyCheckResult:
    label = proxy_log_label(proxy_url)
    if skip_subtitles:
        subtitles_ok, subtitles_error = True, None
    else:
        subtitles_ok, subtitles_error = check_subtitles(proxy_url, video_id)
    if skip_pytubefix:
        pytubefix_ok, pytubefix_error = True, None
    else:
        pytubefix_ok, pytubefix_error = check_pytubefix(proxy_url, video_url)
    return ProxyCheckResult(
        label=label,
        subtitles_ok=subtitles_ok,
        subtitles_error=subtitles_error,
        pytubefix_ok=pytubefix_ok,
        pytubefix_error=pytubefix_error,
    )


def _status(ok: bool) -> str:
    return 'OK' if ok else 'FAIL'


def print_result(result: ProxyCheckResult, *, verbose: bool) -> None:
    overall = _status(result.ok)
    print(f'{result.label}  [{overall}]')
    if not result.subtitles_ok or verbose:
        print(f'  subtitles (youtube-transcript-api): {_status(result.subtitles_ok)}')
        if result.subtitles_error:
            print(f'    {result.subtitles_error}')
    if not result.pytubefix_ok or verbose:
        print(f'  metadata (pytubefix): {_status(result.pytubefix_ok)}')
        if result.pytubefix_error:
            print(f'    {result.pytubefix_error}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Test YOUTUBE_PROXIES from .env against YouTube (subtitles + pytubefix).',
    )
    parser.add_argument(
        '--env-file',
        default='.env',
        help='Path to .env file (default: .env)',
    )
    parser.add_argument(
        '--video-id',
        default=DEFAULT_VIDEO_ID,
        help=f'YouTube video ID for subtitle check (default: {DEFAULT_VIDEO_ID})',
    )
    parser.add_argument(
        '--subtitles-only',
        action='store_true',
        help='Only run youtube-transcript-api check',
    )
    parser.add_argument(
        '--pytubefix-only',
        action='store_true',
        help='Only run pytubefix metadata check',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print OK lines for each check, not only failures',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.subtitles_only and args.pytubefix_only:
        print('Use at most one of --subtitles-only and --pytubefix-only', file=sys.stderr)
        return 2

    logger.remove()
    logger.add(sys.stderr, level='WARNING')

    load_dotenv(args.env_file)
    proxies = load_proxies_from_env()
    if not proxies:
        print('No valid proxies in YOUTUBE_PROXIES', file=sys.stderr)
        return 2

    video_url = f'https://www.youtube.com/watch?v={args.video_id}'
    skip_subtitles = args.pytubefix_only
    skip_pytubefix = args.subtitles_only

    print(f'Checking {len(proxies)} proxy/proxies (video_id={args.video_id})')
    print()

    results: list[ProxyCheckResult] = []
    for proxy_url in proxies:
        result = check_proxy(
            proxy_url,
            video_id=args.video_id,
            video_url=video_url,
            skip_subtitles=skip_subtitles,
            skip_pytubefix=skip_pytubefix,
        )
        results.append(result)
        print_result(result, verbose=args.verbose)
        print()

    failed = sum(1 for r in results if not r.ok)
    if failed:
        print(f'{failed}/{len(results)} proxy/proxies failed')
        return 1

    print(f'All {len(results)} proxy/proxies passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
