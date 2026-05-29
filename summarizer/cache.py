import json
import shutil
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / 'cache'
TRANSCRIPTS_DIR = CACHE_DIR / 'transcripts'
SUMMARIES_DIR = CACHE_DIR / 'summaries'
AUDIO_DIR = CACHE_DIR / 'audio'

SOURCE_ATTRIBUTION_LINE = 'This summary was obtained from the following source:'


def youtube_watch_url(video_id: str) -> str:
    return f'https://www.youtube.com/watch?v={video_id}'


def with_source_attribution(text: str, video_id: str) -> str:
    return (
        f'{text.rstrip()}\n\n{SOURCE_ATTRIBUTION_LINE}\n'
        f'{youtube_watch_url(video_id)}\n'
    )


def strip_source_attribution(text: str, video_id: str) -> str:
    suffix = f'\n\n{SOURCE_ATTRIBUTION_LINE}\n{youtube_watch_url(video_id)}'
    stripped = text.rstrip()
    if stripped.endswith(suffix):
        return stripped[: -len(suffix)].rstrip()
    return text


def transcript_path(video_id: str) -> Path:
    return TRANSCRIPTS_DIR / f'{video_id}.txt'


def _meta_path(video_id: str) -> Path:
    return TRANSCRIPTS_DIR / f'{video_id}.meta.json'


def load_transcript(video_id: str) -> Optional[dict]:
    txt_path = transcript_path(video_id)
    meta_path = _meta_path(video_id)
    if not txt_path.exists() or not meta_path.exists():
        return None
    text = txt_path.read_text(encoding='utf-8')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    return {'text': text, **meta}


def save_transcript(video_id: str, text: str, source: str, language: str):
    transcript_path(video_id).write_text(text, encoding='utf-8')
    meta = {
        'source': source,
        'language': language,
        'duration': 0,
        'created_at': time.time(),
    }
    _meta_path(video_id).write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')


def summary_path(video_id: str, size: str, language: str, provider: str) -> Path:
    return SUMMARIES_DIR / f'{video_id}_{size}_{language}_{provider}.txt'


def summary_md_path(video_id: str, size: str, language: str, provider: str) -> Path:
    return SUMMARIES_DIR / f'{video_id}_{size}_{language}_{provider}.md'


def audio_path(
    video_id: str,
    size: str,
    language: str,
    provider: str,
    voice_id: str,
) -> Path:
    return AUDIO_DIR / f'{video_id}_{size}_{language}_{provider}_{voice_id}.mp3'


def load_summary(video_id: str, size: str, language: str, provider: str) -> Optional[str]:
    path = summary_path(video_id, size, language, provider)
    if not path.exists():
        return None
    return path.read_text(encoding='utf-8')


def load_summary_md(video_id: str, size: str, language: str, provider: str) -> Optional[str]:
    path = summary_md_path(video_id, size, language, provider)
    if not path.exists():
        return None
    return path.read_text(encoding='utf-8')


def load_audio(
    video_id: str,
    size: str,
    language: str,
    provider: str,
    voice_id: str,
) -> Optional[Path]:
    path = audio_path(video_id, size, language, provider, voice_id)
    if not path.exists():
        return None
    return path


def save_summary(video_id: str, size: str, language: str, provider: str, summary: str):
    summary_path(video_id, size, language, provider).write_text(summary, encoding='utf-8')


def save_summary_md(video_id: str, size: str, language: str, provider: str, summary_md: str):
    summary_md_path(video_id, size, language, provider).write_text(summary_md, encoding='utf-8')


def save_audio(
    src_path: str | Path,
    video_id: str,
    size: str,
    language: str,
    provider: str,
    voice_id: str,
):
    shutil.copy2(src_path, audio_path(video_id, size, language, provider, voice_id))
