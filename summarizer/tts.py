import os
from dataclasses import dataclass
from typing import Optional

import edge_tts
from loguru import logger

MAX_AUDIO_BYTES = 45 * 1024 * 1024  # 45 MB (Telegram limit is 50 MB)


@dataclass(frozen=True)
class VoiceOption:
    id: str
    label: str
    group: str


DEFAULT_VOICE_BY_LANG = {
    'en': 'en-US-GuyNeural',
    'ru': 'ru-RU-DmitryNeural',
    'de': 'de-DE-ConradNeural',
    'fr': 'fr-FR-HenriNeural',
    'es': 'es-ES-AlvaroNeural',
    'it': 'it-IT-DiegoNeural',
    'pl': 'pl-PL-MarekNeural',
    'uk': 'uk-UA-OstapNeural',
    'nl': 'nl-NL-MaartenNeural',
    'ja': 'ja-JP-KeitaNeural',
    'ko': 'ko-KR-InJoonNeural',
    'zh': 'zh-CN-YunxiNeural',
}

VOICE_OPTIONS: list[VoiceOption] = [
    VoiceOption('en-US-AriaNeural', 'Aria (US, F)', 'en'),
    VoiceOption('en-US-GuyNeural', 'Guy (US, M)', 'en'),
    VoiceOption('en-US-JennyNeural', 'Jenny (US, F)', 'en'),
    VoiceOption('en-US-ChristopherNeural', 'Christopher (US, M)', 'en'),
    VoiceOption('en-GB-SoniaNeural', 'Sonia (UK, F)', 'en'),
    VoiceOption('en-GB-RyanNeural', 'Ryan (UK, M)', 'en'),
    VoiceOption('ru-RU-SvetlanaNeural', 'Svetlana (RU, F)', 'ru'),
    VoiceOption('ru-RU-DmitryNeural', 'Dmitry (RU, M)', 'ru'),
    VoiceOption('de-DE-KatjaNeural', 'Katja (DE, F)', 'de'),
    VoiceOption('de-DE-ConradNeural', 'Conrad (DE, M)', 'de'),
    VoiceOption('fr-FR-DeniseNeural', 'Denise (FR, F)', 'fr'),
    VoiceOption('fr-FR-HenriNeural', 'Henri (FR, M)', 'fr'),
    VoiceOption('es-ES-ElviraNeural', 'Elvira (ES, F)', 'es'),
    VoiceOption('es-ES-AlvaroNeural', 'Alvaro (ES, M)', 'es'),
    VoiceOption('it-IT-ElsaNeural', 'Elsa (IT, F)', 'it'),
    VoiceOption('it-IT-DiegoNeural', 'Diego (IT, M)', 'it'),
    VoiceOption('pl-PL-AgnieszkaNeural', 'Agnieszka (PL, F)', 'pl'),
    VoiceOption('pl-PL-MarekNeural', 'Marek (PL, M)', 'pl'),
    VoiceOption('uk-UA-PolinaNeural', 'Polina (UA, F)', 'uk'),
    VoiceOption('uk-UA-OstapNeural', 'Ostap (UA, M)', 'uk'),
    VoiceOption('nl-NL-ColetteNeural', 'Colette (NL, F)', 'nl'),
    VoiceOption('nl-NL-MaartenNeural', 'Maarten (NL, M)', 'nl'),
    VoiceOption('ja-JP-NanamiNeural', 'Nanami (JP, F)', 'ja'),
    VoiceOption('ja-JP-KeitaNeural', 'Keita (JP, M)', 'ja'),
    VoiceOption('ko-KR-SunHiNeural', 'SunHi (KR, F)', 'ko'),
    VoiceOption('ko-KR-InJoonNeural', 'InJoon (KR, M)', 'ko'),
    VoiceOption('zh-CN-XiaoxiaoNeural', 'Xiaoxiao (CN, F)', 'zh'),
    VoiceOption('zh-CN-YunxiNeural', 'Yunxi (CN, M)', 'zh'),
]

VOICE_IDS = frozenset(v.id for v in VOICE_OPTIONS)
VOICE_LABEL_BY_ID = {v.id: v.label for v in VOICE_OPTIONS}
VOICES_BY_GROUP: dict[str, list[VoiceOption]] = {}
for _opt in VOICE_OPTIONS:
    VOICES_BY_GROUP.setdefault(_opt.group, []).append(_opt)

SUPPORTED_LANGUAGES = list(DEFAULT_VOICE_BY_LANG.keys())

LANGUAGE_LABELS = {
    'en': 'English',
    'ru': 'Русский',
    'de': 'Deutsch',
    'fr': 'Français',
    'es': 'Español',
    'it': 'Italiano',
    'pl': 'Polski',
    'uk': 'Українська',
    'nl': 'Nederlands',
    'ja': '日本語',
    'ko': '한국어',
    'zh': '中文',
}

VOICE_GROUP_LABELS = LANGUAGE_LABELS

_OTHER_LANGS = sorted(set(SUPPORTED_LANGUAGES) - {'en', 'ru'})
LANGUAGE_ORDER = ['en', 'ru', *_OTHER_LANGS]
VOICE_GROUPS_ORDER = LANGUAGE_ORDER


def resolve_voice(voice: Optional[str], language: str = 'en') -> str:
    if voice and voice in VOICE_IDS:
        return voice
    return DEFAULT_VOICE_BY_LANG.get(language, DEFAULT_VOICE_BY_LANG['en'])


def get_voice_label(voice_id: str) -> str:
    return VOICE_LABEL_BY_ID.get(voice_id, voice_id)


async def synthesize(
    text: str,
    language: str = 'en',
    output_path: str = 'output.mp3',
    voice: Optional[str] = None,
) -> Optional[str]:
    voice_id = resolve_voice(voice, language)
    logger.info('TTS started language={} voice={} chars={}', language, voice_id, len(text))

    try:
        communicate = edge_tts.Communicate(text, voice_id)
        await communicate.save(output_path)

        size = os.path.getsize(output_path)
        if size > MAX_AUDIO_BYTES:
            logger.warning('Audio file too large ({} bytes), truncating and retrying', size)
            max_chars = int(len(text) * (MAX_AUDIO_BYTES / size))
            truncated = text[:max_chars]
            last_period = truncated.rfind('.')
            if last_period > len(truncated) // 2:
                truncated = truncated[:last_period + 1]
            communicate = edge_tts.Communicate(truncated, voice_id)
            await communicate.save(output_path)

        logger.info('TTS complete bytes={}', os.path.getsize(output_path))
        return output_path
    except Exception:
        logger.exception('TTS synthesis failed')
        return None
