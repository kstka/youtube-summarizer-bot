import secrets

from aiogram import BaseMiddleware, types
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger

from .config import App, Telegram
from .database import db
from .messages import (
    SOURCE_CODE_BUTTON,
    START_PASSWORD_PROMPT,
    PASSWORD_PROMPT,
    PASSWORD_REQUIRED_FIRST,
    PASSWORD_INCORRECT,
    format_start_text,
)


def _gate_enabled() -> bool:
    return bool(App.ACCESS_PASSWORD.strip())


def _password_matches(text: str) -> bool:
    expected = App.ACCESS_PASSWORD.strip()
    provided = text.strip()
    return secrets.compare_digest(provided, expected)


def _looks_like_youtube_url(text: str) -> bool:
    return 'youtube.com' in text or 'youtu.be' in text


def _is_start_command(text: str) -> bool:
    command = text.split(maxsplit=1)[0]
    return command == '/start' or command.startswith('/start@')


def _unwrap_event(event: TelegramObject) -> TelegramObject | None:
    if isinstance(event, Update):
        if event.message:
            return event.message
        if event.callback_query:
            return event.callback_query
        return None
    return event


def _start_reply_markup():
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text=SOURCE_CODE_BUTTON,
        url='https://github.com/kstka/youtube-summarizer-bot',
    ))
    return builder.as_markup()


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        original_event = event
        event = _unwrap_event(event)
        if event is None:
            return await handler(original_event, data)

        user = data.get('event_from_user')
        if user is None:
            return await handler(original_event, data)

        user_id = user.id
        if user_id == Telegram.ADMIN_USER_ID or not _gate_enabled():
            return await handler(original_event, data)

        if await db.is_authorized(user_id):
            return await handler(original_event, data)

        if isinstance(event, CallbackQuery):
            await event.answer(PASSWORD_REQUIRED_FIRST, show_alert=True)
            return

        if not isinstance(event, Message):
            return await handler(original_event, data)

        text = (event.text or '').strip()
        if text and _password_matches(text):
            await db.ensure_user(user_id)
            logger.info('User authorized user_id={}', user_id)
            settings = await db.get_settings(user_id) or {}
            await event.answer(
                format_start_text(settings),
                reply_markup=_start_reply_markup(),
            )
            return

        if _looks_like_youtube_url(text):
            await event.answer(PASSWORD_REQUIRED_FIRST)
            return

        if text and _is_start_command(text):
            await event.answer(START_PASSWORD_PROMPT)
            return

        if text.startswith('/'):
            await event.answer(PASSWORD_PROMPT)
            return

        if text:
            await event.answer(PASSWORD_INCORRECT)
            return

        await event.answer(PASSWORD_PROMPT)
