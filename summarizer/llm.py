import aiohttp
from loguru import logger
from typing import Any, Optional

from .config import DeepSeek, OpenRouter, App
from .http_retry import LLM_CLIENT_TIMEOUT, RETRIABLE_EXC, with_retries

SIZE_INSTRUCTIONS = {
    'short': (
        'Write a short self-contained narrative summary for audio playback. '
        'Do not describe the content from the outside. Present the main idea directly. '
        'Do not mention "the author", "the speaker", "the video", "the transcript", or "the viewer". '
        'Start immediately with the central idea. '
        'Explain what the content is really about, what conclusion follows from it, and why it matters. '
        'Keep only the core thesis and the strongest supporting ideas. '
        'Remove repetitions, secondary examples, names that are not essential, and side remarks. '
        'Target length: 900-1400 characters including spaces. '
        'Use 2-3 short paragraphs.'
    ),

    'medium': (
        'Write a self-contained narrative summary for audio playback. '
        'Do not describe the content from the outside. Present the ideas directly as a coherent explanation. '
        'Do not mention "the author", "the speaker", "the video", "the transcript", or "the viewer". '
        'Do not write phrases like "the main point is that the author wants to show". '
        'Start immediately with the central idea. '
        'Explain the main thesis, the logic of the argument, the most important contrasts, and the final takeaway. '
        'Keep only ideas that are necessary to understand the message. '
        'Remove repetitions, weak examples, long lists, secondary names, personal digressions, and minor details. '
        'The result should sound like a clear explanatory mini-essay, not like notes about a video. '
        'Target length: 1800-2400 characters including spaces. '
        'This limit is strict. Prefer a shorter summary over a complete but long one. '
        'Use 4-5 short paragraphs.'
    ),

    'long': (
        'Write a detailed self-contained narrative summary for audio playback. '
        'Do not describe the content from the outside. Present the ideas directly as a coherent explanation. '
        'Do not mention "the author", "the speaker", "the video", "the transcript", or "the viewer". '
        'Reconstruct the argument from beginning to end, but remove repetition and filler. '
        'Explain the central thesis, supporting arguments, important examples, key contrasts, shifts in emphasis, and final takeaway. '
        'Separate central ideas from minor details. '
        'Preserve nuance, causal links, and the internal logic of the content. '
        'If something is unclear or the subtitles are fragmented, state the uncertainty briefly without inventing missing facts. '
        'The result should let a person understand the message, reasoning, and tone without reading the transcript. '
        'Target length: 4000-5500 characters including spaces. '
        'Use short paragraphs and natural transitions.'
    ),
}

BASE_SYSTEM_PROMPT = (
    'You are an interpretive summarization assistant creating summaries for audio playback.\n'
    'Your task is to turn subtitles into a clear, coherent narrative that explains the meaning of the content.\n'
    'Do not create a meta-summary. Do not describe what someone says, explains, discusses, argues, or tries to prove.\n'
    'Instead, express the intended message directly, as a standalone explanation.\n'
    'Avoid phrases like "the author says", "the speaker explains", "the video discusses", "the transcript shows", or similar constructions.\n'
    'Use only the provided transcript or subtitles. Do not add outside facts.\n'
    'Separate central ideas from minor details. Remove repetition, filler, weak examples, and unnecessary names.\n'
    'Preserve the main thesis, argument logic, important contrasts, causal links, and final takeaway.\n'
    'The result should sound natural when converted to speech.\n'
    'Prefer clarity, flow, and meaning over exhaustive coverage.\n'
    'Output plain text only — no markdown formatting, no headings, no bullet points, no code blocks.\n'
)


def build_prompt(transcript: str, size: str, language: str) -> tuple[str, str]:
    size_instruction = SIZE_INSTRUCTIONS.get(size, SIZE_INSTRUCTIONS['medium'])
    system = (
        f'{BASE_SYSTEM_PROMPT}\n'
        f'Reply strictly in {language}.\n'
        f'Summary detail level: {size_instruction}'
    )
    user = f'Summarize the following content:\n\n{transcript}'
    return system, user


def get_provider_config(provider: str):
    if provider == 'deepseek':
        if not DeepSeek.API_KEY:
            raise ValueError('DEEPSEEK_API_KEY is not configured')
        return DeepSeek.BASE_URL, DeepSeek.API_KEY, DeepSeek.MODEL
    elif provider == 'openrouter':
        if not OpenRouter.API_KEY:
            raise ValueError('OPENROUTER_API_KEY is not configured')
        return OpenRouter.BASE_URL, OpenRouter.API_KEY, OpenRouter.MODEL
    else:
        raise ValueError(f'Unknown LLM provider: {provider}')


MARKDOWN_FORMAT_SYSTEM_PROMPT = (
    'You format existing summaries as Markdown. Use ## headings, bullet lists, '
    'and emphasis where appropriate. Do NOT add facts beyond the provided text. '
    'Do NOT use phrases like "Here is the summary". Output ONLY the formatted Markdown.'
)


async def _post_chat_completion(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    error_label: str,
) -> Optional[dict]:
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status == 429 or resp.status >= 500:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=resp.status,
                message=f'HTTP {resp.status}', headers=resp.headers,
            )
        if resp.status != 200:
            logger.error('{} status={}', error_label, resp.status)
            return None
        return await resp.json()


def _message_content(data: dict) -> str:
    return data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()


async def format_summary_markdown(
    summary: str, language: str, provider: str = 'deepseek',
) -> Optional[str]:
    try:
        base_url, api_key, model = get_provider_config(provider)
    except ValueError as e:
        return str(e)

    system = f'{MARKDOWN_FORMAT_SYSTEM_PROMPT}\nReply strictly in {language}.'
    user = summary

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.3,
        'max_tokens': 4096,
    }

    url = f'{base_url}/chat/completions'

    async def _call():
        async with aiohttp.ClientSession(timeout=LLM_CLIENT_TIMEOUT) as session:
            data = await _post_chat_completion(
                session, url, payload, headers, 'Markdown format request failed',
            )
            if data is None:
                return None
            return _message_content(data)

    try:
        return await with_retries(_call)
    except RETRIABLE_EXC:
        logger.exception('Markdown format call failed after retries')
        return None
    except Exception:
        logger.exception('Markdown format call failed')
        return None


async def get_summary(transcript: str, size: str, language: str, provider: str = 'deepseek') -> Optional[str]:
    try:
        base_url, api_key, model = get_provider_config(provider)
    except ValueError as e:
        return str(e)

    system, user = build_prompt(transcript, size, language)

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.5,
        'max_tokens': 4096,
    }

    url = f'{base_url}/chat/completions'

    async def _call():
        async with aiohttp.ClientSession(timeout=LLM_CLIENT_TIMEOUT) as session:
            data = await _post_chat_completion(
                session, url, payload, headers, 'LLM request failed',
            )
            if data is None:
                return None
            return _message_content(data)

    try:
        return await with_retries(_call)
    except RETRIABLE_EXC:
        logger.exception('LLM call failed after retries')
        return None
    except Exception:
        logger.exception('LLM call failed')
        return None


async def clean_ads(transcript: str, language: str) -> str:
    try:
        base_url, api_key, model = get_provider_config(App.LLM_PROVIDER)
    except ValueError:
        return transcript

    system = (
        'You are a text cleaner. Remove sponsorship reads, paid promotions, '
        'self-promotion blocks, "like and subscribe" calls, intro/outro filler, '
        'and any explicit ad reads from the following transcript. Preserve all '
        'substantive content verbatim. Output ONLY the cleaned text, no explanations.'
    )
    user = f'Clean the following transcript (language: {language}):\n\n{transcript}'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.1,
        'max_tokens': 8192,
    }

    url = f'{base_url}/chat/completions'

    async def _call():
        async with aiohttp.ClientSession(timeout=LLM_CLIENT_TIMEOUT) as session:
            data = await _post_chat_completion(
                session, url, payload, headers, 'Ad cleaning failed',
            )
            if data is None:
                return transcript
            result = _message_content(data)
            return result if result else transcript

    try:
        return await with_retries(_call)
    except RETRIABLE_EXC:
        logger.exception('Ad cleaning call failed after retries')
        return transcript
    except Exception:
        logger.exception('Ad cleaning call failed')
        return transcript
