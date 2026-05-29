import os
import tempfile

from loguru import logger

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile, FSInputFile

from .config import Telegram, App, Sentry
from .database import db
from .transcript import get_transcript, extract_video_id
from .llm import get_summary, format_summary_markdown
from .tts import (
    synthesize,
    SUPPORTED_LANGUAGES,
    VOICE_IDS,
    VOICE_GROUP_LABELS,
    resolve_voice,
)
from .bot_menu import setup_bot_menu
from .auth_middleware import AuthMiddleware
from .keyboards import (
    settings_keyboard,
    language_keyboard,
    voice_groups_keyboard,
    voice_list_keyboard,
    SIZE_LABELS,
)
from .messages import (
    BCAST_REPLY_HINT,
    BCAST_STARTED,
    FAIL_SUMMARY,
    FAIL_TRANSCRIPT,
    INVALID_OPTION,
    LANGUAGE_PICKER_TITLE,
    SOURCE_CODE_BUTTON,
    STATUS_EXTRACTING,
    STATUS_GENERATING_AUDIO,
    STATUS_GENERATING_SUMMARY,
    SUMMARY_CAPTION,
    SUMMARY_MD_CAPTION,
    UNKNOWN_VOICE,
    UNKNOWN_VOICE_GROUP,
    VOICE_GROUPS_TITLE,
    VOICE_RESET_TOAST,
    format_bcast_finished,
    format_error,
    format_language_set,
    format_language_toast,
    format_settings_text,
    format_size_set_command,
    format_size_toast,
    format_start_text,
    format_total_users,
    format_unsupported_language,
    format_voice_groups_text,
    format_voice_list_text,
    format_voice_toast,
    parse_voice_group_from_list_text,
)
from . import cache

bot = Bot(
    token=Telegram.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()
dp.update.outer_middleware(AuthMiddleware())


async def _user_settings(user_id: int) -> dict:
    await db.ensure_user(user_id)
    return await db.get_settings(user_id) or {}


@dp.message(Command('start'))
async def start_command(message: types.Message):
    settings = await _user_settings(message.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text=SOURCE_CODE_BUTTON,
        url='https://github.com/kstka/youtube-summarizer-bot'
    ))
    await message.answer(
        format_start_text(settings),
        reply_markup=builder.as_markup(),
    )


@dp.message(Command('settings'))
async def show_settings(message: types.Message):
    settings = await _user_settings(message.from_user.id)
    await message.answer(
        format_settings_text(settings),
        reply_markup=settings_keyboard(
            settings.get('size', App.DEFAULT_SIZE),
            settings.get('language', App.DEFAULT_LANG),
            settings.get('voice'),
        ),
    )


@dp.message(Command('language'))
async def set_language(message: types.Message):
    settings = await _user_settings(message.from_user.id)
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        lang = settings.get('language', App.DEFAULT_LANG)
        return await message.answer(
            LANGUAGE_PICKER_TITLE,
            reply_markup=language_keyboard(lang),
        )
    lang = args[1].strip().lower()
    if lang not in SUPPORTED_LANGUAGES:
        langs = ', '.join(SUPPORTED_LANGUAGES)
        return await message.answer(format_unsupported_language(langs))
    await db.set_language(message.from_user.id, lang)
    logger.info('Language set user_id={} language={}', message.from_user.id, lang)
    await message.answer(format_language_set(lang))


@dp.message(Command('voice'))
async def voice_command(message: types.Message):
    settings = await _user_settings(message.from_user.id)
    await message.answer(
        format_voice_groups_text(),
        reply_markup=voice_groups_keyboard(settings.get('voice')),
    )


@dp.message(Command('short'))
async def set_short(message: types.Message):
    await db.ensure_user(message.from_user.id)
    await db.set_size(message.from_user.id, 'short')
    logger.info('Size set user_id={} size=short', message.from_user.id)
    await message.answer(format_size_set_command('short'))


@dp.message(Command('medium'))
async def set_medium(message: types.Message):
    await db.ensure_user(message.from_user.id)
    await db.set_size(message.from_user.id, 'medium')
    logger.info('Size set user_id={} size=medium', message.from_user.id)
    await message.answer(format_size_set_command('medium'))


@dp.message(Command('long'))
async def set_long(message: types.Message):
    await db.ensure_user(message.from_user.id)
    await db.set_size(message.from_user.id, 'long')
    logger.info('Size set user_id={} size=long', message.from_user.id)
    await message.answer(format_size_set_command('long'))


@dp.callback_query(F.data.startswith('set:'))
async def handle_set_callback(callback: types.CallbackQuery):
    parts = callback.data.split(':', 2)
    if len(parts) != 3:
        await callback.answer()
        return

    _, kind, value = parts
    user_id = callback.from_user.id
    await db.ensure_user(user_id)

    if kind == 'size' and value in SIZE_LABELS:
        await db.set_size(user_id, value)
        logger.info('Size set user_id={} size={}', user_id, value)
        await callback.answer(format_size_toast(value))
    elif kind == 'lang' and value in SUPPORTED_LANGUAGES:
        await db.set_language(user_id, value)
        logger.info('Language set user_id={} language={}', user_id, value)
        await callback.answer(format_language_toast(value))
    elif kind == 'voice':
        if value == 'default':
            await db.set_voice(user_id, None)
            logger.info('Voice reset user_id={}', user_id)
            await callback.answer(VOICE_RESET_TOAST)
        elif value in VOICE_IDS:
            await db.set_voice(user_id, value)
            logger.info('Voice set user_id={} voice={}', user_id, value)
            await callback.answer(format_voice_toast(value))
        else:
            await callback.answer(UNKNOWN_VOICE, show_alert=True)
            return
    else:
        await callback.answer(INVALID_OPTION, show_alert=True)
        return

    if not callback.message:
        return

    settings = await db.get_settings(user_id) or {}
    size = settings.get('size', App.DEFAULT_SIZE)
    lang = settings.get('language', App.DEFAULT_LANG)
    voice = settings.get('voice')
    text = callback.message.text or ''

    group = parse_voice_group_from_list_text(text)
    if group:
        await callback.message.edit_text(
            format_voice_list_text(group),
            reply_markup=voice_list_keyboard(group, voice),
        )
        return

    if text.startswith(LANGUAGE_PICKER_TITLE):
        await callback.message.edit_text(
            LANGUAGE_PICKER_TITLE,
            reply_markup=language_keyboard(lang),
        )
        return

    if text.startswith(VOICE_GROUPS_TITLE):
        await callback.message.edit_text(
            format_voice_groups_text(),
            reply_markup=voice_groups_keyboard(voice),
        )
        return

    await callback.message.edit_text(
        format_settings_text(settings),
        reply_markup=settings_keyboard(size, lang, voice),
    )


@dp.callback_query(F.data.startswith('voice:'))
async def handle_voice_nav_callback(callback: types.CallbackQuery):
    action = callback.data.split(':', 1)[1]
    user_id = callback.from_user.id
    settings = await _user_settings(user_id)
    voice = settings.get('voice')

    if action == 'open':
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                format_voice_groups_text(),
                reply_markup=voice_groups_keyboard(voice),
            )
        return

    if action == 'back':
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                format_voice_groups_text(),
                reply_markup=voice_groups_keyboard(voice),
            )
        return

    if action.startswith('grp:'):
        group = action[4:]
        if group not in VOICE_GROUP_LABELS:
            await callback.answer(UNKNOWN_VOICE_GROUP, show_alert=True)
            return
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                format_voice_list_text(group),
                reply_markup=voice_list_keyboard(group, voice),
            )
        return

    await callback.answer()


@dp.message(Command('users'))
async def users_command(message: types.Message):
    if message.from_user.id != Telegram.ADMIN_USER_ID:
        return
    count = await db.count_users()
    await message.answer(format_total_users(count))


@dp.message(Command('bcast'))
async def bcast_command(message: types.Message):
    if message.from_user.id != Telegram.ADMIN_USER_ID:
        return
    if not message.reply_to_message:
        return await message.answer(BCAST_REPLY_HINT)
    msg = message.reply_to_message
    status_msg = await message.answer(BCAST_STARTED)
    errors = 0
    users = await db.fetch_all_user_ids()
    logger.info('Broadcast started recipients={}', len(users))
    for uid in users:
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=message.chat.id,
                message_id=msg.message_id
            )
        except Exception:
            errors += 1
    await status_msg.edit_text(format_bcast_finished(errors))
    logger.info('Broadcast finished recipients={} errors={}', len(users), errors)


def _summary_attachment_basename(video_id: str, size: str, lang: str) -> str:
    return f'summary_{size}_{lang}_{video_id}'


async def _send_summary_file(
    message: types.Message,
    video_id: str,
    size: str,
    lang: str,
    content: str,
    ext: str,
    caption: str,
):
    basename = _summary_attachment_basename(video_id, size, lang)
    await message.answer_document(
        BufferedInputFile(
            content.encode('utf-8'),
            filename=f'{basename}.{ext}',
        ),
        caption=caption,
    )


async def _resolve_summary_markdown(
    video_id: str,
    size: str,
    lang: str,
    provider: str,
    summary_body: str,
) -> str | None:
    cached_md = cache.load_summary_md(video_id, size, lang, provider)
    if cached_md:
        return cached_md
    summary_md = await format_summary_markdown(summary_body, lang, provider)
    if not summary_md:
        return None
    summary_md = cache.with_source_attribution(summary_md, video_id)
    cache.save_summary_md(video_id, size, lang, provider, summary_md)
    return summary_md


async def _send_summary_documents(
    message: types.Message,
    video_id: str,
    size: str,
    lang: str,
    provider: str,
    summary_for_files: str,
    summary_body: str,
) -> bool:
    summary_md = await _resolve_summary_markdown(
        video_id, size, lang, provider, summary_body,
    )
    if not summary_md:
        return False
    await _send_summary_file(
        message, video_id, size, lang, summary_for_files, 'txt', SUMMARY_CAPTION,
    )
    await _send_summary_file(
        message, video_id, size, lang, summary_md, 'md', SUMMARY_MD_CAPTION,
    )
    return True


async def _send_summary_audio(
    message: types.Message, video_id: str, size: str, lang: str, mp3_path: str | os.PathLike,
):
    basename = _summary_attachment_basename(video_id, size, lang)
    audio_bytes = os.path.getsize(mp3_path)
    await message.answer_audio(
        FSInputFile(mp3_path, filename=f'{basename}.mp3'),
        title=basename,
        performer='YouTube Summarizer Bot',
    )
    logger.info(
        'Audio sent user_id={} video_id={} bytes={}',
        message.from_user.id, video_id, audio_bytes,
    )


@dp.message()
async def handle_message(message: types.Message):
    if not message.text:
        return
    url = message.text.strip()
    if 'youtube.com' not in url and 'youtu.be' not in url:
        return

    settings = await _user_settings(message.from_user.id)
    size = settings.get('size', App.DEFAULT_SIZE)
    lang = settings.get('language', App.DEFAULT_LANG)
    voice = settings.get('voice')
    vid = extract_video_id(url)
    provider = App.LLM_PROVIDER
    effective_voice = resolve_voice(voice, lang)
    temp_dir = tempfile.mkdtemp(prefix='yt_summary_')
    logger.info(
        'Summarize request user_id={} video_id={} size={} language={} provider={}',
        message.from_user.id, vid, size, lang, provider,
    )

    try:
        cached_summary = cache.load_summary(vid, size, lang, provider)
        cached_audio = (
            cache.load_audio(vid, size, lang, provider, effective_voice)
            if cached_summary
            else None
        )

        if cached_summary and cached_audio:
            logger.info(
                'Summary cache hit video_id={} size={} language={} provider={}',
                vid, size, lang, provider,
            )
            logger.info(
                'Audio cache hit video_id={} size={} language={} provider={} voice={}',
                vid, size, lang, provider, effective_voice,
            )
            summary_body = cache.strip_source_attribution(cached_summary, vid)
            if not await _send_summary_documents(
                message, vid, size, lang, provider, cached_summary, summary_body,
            ):
                logger.warning(
                    'Markdown summary failed user_id={} video_id={}',
                    message.from_user.id, vid,
                )
                await message.answer(FAIL_SUMMARY)
                return
            await _send_summary_audio(message, vid, size, lang, cached_audio)
            logger.info('Summarize complete user_id={} video_id={}', message.from_user.id, vid)
            return

        summary_body: str | None = None
        summary_for_files: str | None = None

        if cached_summary:
            logger.info(
                'Summary cache hit video_id={} size={} language={} provider={}',
                vid, size, lang, provider,
            )
            summary_for_files = cached_summary
            summary_body = cache.strip_source_attribution(cached_summary, vid)
            status_msg = await message.answer(STATUS_GENERATING_AUDIO)
        else:
            status_msg = await message.answer(STATUS_EXTRACTING)
            transcript, source = await get_transcript(
                url,
                openrouter_api_key=os.environ.get('OPENROUTER_API_KEY', ''),
                tmp_dir=temp_dir,
            )

            if not transcript:
                logger.warning('Transcript failed user_id={} video_id={}', message.from_user.id, vid)
                await status_msg.edit_text(FAIL_TRANSCRIPT)
                return

            logger.info(
                'Transcript ready user_id={} video_id={} source={} chars={}',
                message.from_user.id, vid, source, len(transcript),
            )

            await status_msg.edit_text(STATUS_GENERATING_SUMMARY)
            summary_body = await get_summary(
                transcript=transcript,
                size=size,
                language=lang,
                provider=provider,
            )

            if not summary_body:
                logger.warning('Summary failed user_id={} video_id={}', message.from_user.id, vid)
                await status_msg.edit_text(FAIL_SUMMARY)
                return

            logger.info(
                'Summary ready user_id={} video_id={} chars={}',
                message.from_user.id, vid, len(summary_body),
            )
            summary_for_files = cache.with_source_attribution(summary_body, vid)
            cache.save_summary(vid, size, lang, provider, summary_for_files)

        if not await _send_summary_documents(
            message, vid, size, lang, provider, summary_for_files, summary_body,
        ):
            logger.warning(
                'Markdown summary failed user_id={} video_id={}',
                message.from_user.id, vid,
            )
            await status_msg.edit_text(FAIL_SUMMARY)
            return

        if not cached_summary:
            await status_msg.edit_text(STATUS_GENERATING_AUDIO)
        mp3_path = os.path.join(
            temp_dir, f'{_summary_attachment_basename(vid, size, lang)}.mp3',
        )
        result = await synthesize(summary_body, language=lang, voice=voice, output_path=mp3_path)

        if result and os.path.exists(result):
            cache.save_audio(
                result,
                vid,
                size,
                lang,
                provider,
                effective_voice,
            )
            await _send_summary_audio(message, vid, size, lang, result)
        else:
            logger.warning('Audio skipped user_id={} video_id={}', message.from_user.id, vid)

        await status_msg.delete()
        logger.info('Summarize complete user_id={} video_id={}', message.from_user.id, vid)

    except Exception as e:
        logger.exception('Summarize failed user_id={} video_id={}', message.from_user.id, vid)
        error_text = str(e)
        if len(error_text) > 200:
            error_text = error_text[:200] + '...'
        await message.answer(format_error(error_text), parse_mode=None)
    finally:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)


async def main(sentry_enabled: bool = False):
    if sentry_enabled:
        logger.info('Sentry enabled environment={}', Sentry.ENVIRONMENT)
    await db.init_db()
    logger.info('Database ready path={}', db.db_path)
    if App.ACCESS_PASSWORD.strip():
        logger.info('Access password gate enabled')
    else:
        logger.warning('Access password gate disabled (ACCESS_PASSWORD is empty)')
    await setup_bot_menu(bot)
    logger.info('Bot menu commands registered')
    logger.info('Bot starting polling')
    await dp.start_polling(bot)
