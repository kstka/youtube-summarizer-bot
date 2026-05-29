import os
import re
import subprocess
import asyncio
import base64
import aiohttp
from loguru import logger
from typing import Optional, Tuple

from .config import Audio, App
from .http_retry import LLM_CLIENT_TIMEOUT, RETRIABLE_EXC, with_retries
from .llm import clean_ads
from . import cache

SUPPORTED_LANGS = ['en', 'ja', 'ko', 'de', 'fr', 'ru', 'it', 'es', 'pl', 'uk', 'nl', 'zh-TW', 'zh-CN']


def extract_video_id(url: str) -> str:
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return re.sub(r'[^a-zA-Z0-9_-]', '', url)[:20]


async def try_subtitles(youtube_url: str, tmp_dir: str) -> Optional[str]:
    loop = asyncio.get_event_loop()

    def fetch():
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            VideoUnavailable,
            InvalidVideoId,
        )

        video_id = extract_video_id(youtube_url)
        api = YouTubeTranscriptApi()

        try:
            transcript = api.fetch(video_id, languages=SUPPORTED_LANGS)
            raw = transcript.to_raw_data()
        except (NoTranscriptFound, VideoUnavailable, InvalidVideoId):
            return None

        lines = []
        prev = None
        for entry in raw:
            t = entry['text'].strip()
            if t and t != prev:
                lines.append(t)
                prev = t
        return ' '.join(lines) if lines else None

    return await loop.run_in_executor(None, fetch)


async def download_audio(youtube_url: str, tmp_dir: str) -> Optional[str]:
    loop = asyncio.get_event_loop()

    def download():
        import pytubefix as pytube

        video_id = extract_video_id(youtube_url)
        temp_mp4 = os.path.join(tmp_dir, f'audio_{video_id}.mp4')
        output_mp3 = os.path.join(tmp_dir, f'audio_{video_id}.mp3')

        try:
            yt = pytube.YouTube(youtube_url)
            stream = yt.streams.get_audio_only()
            stream.download(output_path=tmp_dir, filename=f'audio_{video_id}.mp4')

            subprocess.run([
                'ffmpeg', '-y', '-i', temp_mp4,
                '-ac', '1', '-ar', '16000', '-b:a', '32k',
                output_mp3
            ], capture_output=True, check=True)

            os.remove(temp_mp4)
            return output_mp3
        except pytube.exceptions.VideoUnavailable:
            if os.path.exists(temp_mp4):
                os.remove(temp_mp4)
            return None
        except Exception:
            if os.path.exists(temp_mp4):
                os.remove(temp_mp4)
            if os.path.exists(output_mp3):
                os.remove(output_mp3)
            raise

    return await loop.run_in_executor(None, download)


async def transcribe_via_openrouter(audio_path: str, api_key: str) -> Optional[str]:
    if not api_key:
        return None

    audio_size = os.path.getsize(audio_path)
    if audio_size > 25 * 1024 * 1024:
        logger.warning('Audio payload > 25 MB ({} bytes), proceeding anyway', audio_size)

    with open(audio_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': Audio.MODEL,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'Transcribe this audio verbatim. Return only the transcription. Maintain original language.'},
                    {
                        'type': 'input_audio',
                        'input_audio': {
                            'data': audio_b64,
                            'format': 'mp3',
                        },
                    },
                ],
            }
        ],
        'max_tokens': 4096,
    }

    try:
        async with aiohttp.ClientSession(timeout=LLM_CLIENT_TIMEOUT) as session:
            async with session.post(f'{Audio.BASE_URL}/chat/completions', json=payload, headers=headers) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    logger.error('OpenRouter audio request failed: {} {}', resp.status, err_text[:500])
                    if resp.status == 429 or resp.status >= 500:
                        raise aiohttp.ClientResponseError(
                            resp.request_info, resp.history, status=resp.status,
                            message=f'HTTP {resp.status}', headers=resp.headers
                        )
                    return None
                data = await resp.json()
                return data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
    except RETRIABLE_EXC:
        raise
    except Exception:
        logger.exception('OpenRouter transcription failed')
        return None


async def try_audio(youtube_url: str, api_key: str, tmp_dir: str) -> Optional[str]:
    audio_path = await download_audio(youtube_url, tmp_dir)
    if not audio_path:
        return None

    text = await transcribe_via_openrouter(audio_path, api_key)

    if os.path.exists(audio_path):
        os.remove(audio_path)

    return text


async def get_transcript(url: str, openrouter_api_key: str, tmp_dir: str) -> Tuple[str, str]:
    vid = extract_video_id(url)

    cached = cache.load_transcript(vid)
    if cached:
        logger.info('Transcript cache hit video_id={}', vid)
        return cached['text'], 'cache'

    logger.info('Fetching transcript video_id={} method=subtitles', vid)
    text = await with_retries(lambda: try_subtitles(url, tmp_dir))
    source = 'subtitles' if text else None

    if not text:
        logger.info('Subtitles unavailable video_id={} method=audio', vid)
        text = await with_retries(lambda: try_audio(url, openrouter_api_key, tmp_dir))
        source = 'audio' if text else None

    if not text:
        logger.warning('Transcript extraction failed video_id={}', vid)
        return '', 'failed'

    cleaned = await clean_ads(text, language='auto')
    cache.save_transcript(vid, cleaned, source=source, language='auto')
    logger.info('Transcript cached video_id={} source={} chars={}', vid, source, len(cleaned))
    return cleaned, source
