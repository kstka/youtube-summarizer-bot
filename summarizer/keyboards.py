from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .tts import (
    LANGUAGE_LABELS,
    LANGUAGE_ORDER,
    VOICE_GROUP_LABELS,
    VOICE_GROUPS_ORDER,
    VOICE_LABEL_BY_ID,
    VOICES_BY_GROUP,
)

SIZE_LABELS = {
    'short': '📄 Short',
    'medium': '📰 Medium',
    'long': '📚 Long',
}


def _mark(current: str, value: str, label: str) -> str:
    return f'✅ {label}' if current == value else label


def _lang_buttons(current_lang: str) -> list[InlineKeyboardButton]:
    buttons = []
    for lang in LANGUAGE_ORDER:
        buttons.append(InlineKeyboardButton(
            text=_mark(current_lang, lang, LANGUAGE_LABELS[lang]),
            callback_data=f'set:lang:{lang}',
        ))
    return buttons


def settings_keyboard(current_size: str, current_lang: str, current_voice: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(*[
        InlineKeyboardButton(
            text=_mark(current_size, size, SIZE_LABELS[size]),
            callback_data=f'set:size:{size}',
        )
        for size in ('short', 'medium', 'long')
    ])

    lang_buttons = _lang_buttons(current_lang)
    builder.row(*lang_buttons[:2])
    for i in range(2, len(lang_buttons), 3):
        builder.row(*lang_buttons[i:i + 3])

    voice_btn = '🔊 Voice…'
    if current_voice and current_voice in VOICE_LABEL_BY_ID:
        voice_btn = f'🔊 Voice: {VOICE_LABEL_BY_ID[current_voice]}'
    builder.row(InlineKeyboardButton(text=voice_btn, callback_data='voice:open'))

    return builder.as_markup()


def language_keyboard(current_lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    lang_buttons = _lang_buttons(current_lang)
    builder.row(*lang_buttons[:2])
    for i in range(2, len(lang_buttons), 3):
        builder.row(*lang_buttons[i:i + 3])
    return builder.as_markup()


def voice_groups_keyboard(current_voice: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    group_buttons = [
        InlineKeyboardButton(
            text=VOICE_GROUP_LABELS[g],
            callback_data=f'voice:grp:{g}',
        )
        for g in VOICE_GROUPS_ORDER
    ]
    builder.row(*group_buttons[:2])
    for i in range(2, len(group_buttons), 3):
        builder.row(*group_buttons[i:i + 3])

    if current_voice:
        builder.row(InlineKeyboardButton(
            text='↩️ Reset to language default',
            callback_data='set:voice:default',
        ))

    return builder.as_markup()


def voice_list_keyboard(group: str, current_voice: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = VOICES_BY_GROUP.get(group, [])
    for i in range(0, len(options), 2):
        row = []
        for opt in options[i:i + 2]:
            row.append(InlineKeyboardButton(
                text=_mark(current_voice or '', opt.id, opt.label),
                callback_data=f'set:voice:{opt.id}',
            ))
        builder.row(*row)

    builder.row(InlineKeyboardButton(text='⬅️ Back', callback_data='voice:back'))
    return builder.as_markup()
