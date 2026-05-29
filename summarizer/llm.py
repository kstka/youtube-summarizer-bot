import aiohttp
from loguru import logger
from typing import Any, Optional

from .config import DeepSeek, OpenRouter, App
from .http_retry import LLM_CLIENT_TIMEOUT, RETRIABLE_EXC, with_retries

SIZE_INSTRUCTIONS = {
    'short': (
        'Write a compact interpretive summary. '
        'Start with 1-2 sentences explaining the author’s central message: '
        'what the author is trying to make the viewer understand, believe, or reconsider. '
        'Then give 3-6 key points that support this message. '
        'Do not make a generic topic list. Focus on the argument and why it matters.'
    ),

    'medium': (
        'Write a structured interpretive overview. '
        'First explain the author’s main thesis and intended takeaway. '
        'Then organize the summary by the logic of the video: how the author builds the argument, '
        'which claims are central, what examples or evidence are used, and what conclusion follows. '
        'Preserve nuance, contrasts, and causal links. '
        'The reader should understand not only what was mentioned, but what the author wanted to communicate.'
    ),

    'long': (
        'Write a detailed interpretive summary. '
        'Reconstruct the author’s argument from beginning to end. '
        'Explain the central thesis, supporting arguments, examples, shifts in emphasis, implied assumptions, '
        'and final takeaway. '
        'Separate important ideas from minor details. '
        'When the transcript is ambiguous, say so instead of inventing. '
        'The goal is that a reader who did not watch the video understands the author’s message, reasoning, and tone.'
    ),    
}

BASE_SYSTEM_PROMPT = (
    'You are an interpretive summarization assistant.\n'
    'Your task is not to list topics, but to explain what the author is trying to communicate.\n'
    'Identify the central thesis, the author’s intent, the logic of the argument, and the final takeaway.\n'
    'Use only the provided transcript or subtitles. Do NOT add outside facts.\n'
    'Do not quote long passages. Paraphrase.\n'
    'If the author’s point is unclear or the subtitles are fragmented, say that clearly.\n'
    'Avoid dry generic summaries like “the video discusses X”.\n'
    'Output plain text only — no markdown tables, no code blocks.\n'
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
