from .config import App
from .keyboards import SIZE_LABELS
from .tts import LANGUAGE_LABELS, VOICE_GROUP_LABELS, get_voice_label, resolve_voice

# Screen titles (used for edit_text routing)
LANGUAGE_PICKER_TITLE = '🌍 Choose summary language:'
VOICE_GROUPS_TITLE = '🎙 Choose a voice group, then pick a voice:'
VOICE_LIST_PREFIX = '🎤 Voices for '

SOURCE_CODE_BUTTON = '💻 View Source Code'

START_PASSWORD_PROMPT = '🔒 This bot is private. Send the access password to continue.'
PASSWORD_PROMPT = '🔒 Send the access password to continue.'
PASSWORD_REQUIRED_FIRST = '🔒 Enter the access password first.'
PASSWORD_INCORRECT = '❌ Incorrect password. Try again.'

VOICE_RESET_TOAST = '↩️ Voice reset to language default'
UNKNOWN_VOICE = '❓ Unknown voice'
INVALID_OPTION = '⚠️ Invalid option'
INVALID_YOUTUBE_URL = (
    '😕 Could not recognize the YouTube video ID. '
    'Send a direct link (watch, youtu.be, shorts, or live).'
)
UNKNOWN_VOICE_GROUP = '❓ Unknown group'

BCAST_REPLY_HINT = '📢 Reply to a message with /bcast to broadcast.'
BCAST_STARTED = '📢 Broadcasting...'

STATUS_EXTRACTING = '📝 Extracting transcript...'
STATUS_GENERATING_SUMMARY = '✨ Generating summary...'
STATUS_GENERATING_AUDIO = '🎧 Generating audio version...'
FAIL_TRANSCRIPT = '😕 Failed to extract transcript.'
FAIL_SUMMARY = '😕 Failed to generate summary.'
SUMMARY_CAPTION = '✅ Summary (Plain Text)'
SUMMARY_MD_CAPTION = '✅ Summary (Markdown)'


def _settings_lines(settings: dict) -> str:
    size = settings.get('size', App.DEFAULT_SIZE)
    lang = settings.get('language', App.DEFAULT_LANG)
    voice = settings.get('voice')
    effective = resolve_voice(voice, lang)
    voice_line = get_voice_label(effective)
    if not voice:
        voice_line += ' (default)'
    lang_line = LANGUAGE_LABELS.get(lang, lang)
    return (
        f'• 📏 Size: {SIZE_LABELS.get(size, size)}\n'
        f'• 🌐 Language: {lang_line} (`{lang}`)\n'
        f'• 🔊 TTS voice: {voice_line}'
    )


def format_settings_text(settings: dict) -> str:
    return (
        f'⚙️ Your settings:\n{_settings_lines(settings)}\n\n'
        f'📺 Send a YouTube link to summarize.'
    )


def format_start_text(settings: dict) -> str:
    return (
        f'👋 Send me a YouTube link and I will summarize it.\n\n'
        f'⚙️ Current settings:\n{_settings_lines(settings)}\n\n'
        f'Use /settings or the **Menu** button to change options.'
    )


def format_voice_groups_text() -> str:
    return VOICE_GROUPS_TITLE


def format_voice_list_text(group: str) -> str:
    label = VOICE_GROUP_LABELS.get(group, group)
    return f'{VOICE_LIST_PREFIX}{label}:'


def parse_voice_group_from_list_text(text: str) -> str | None:
    if not text.startswith(VOICE_LIST_PREFIX):
        return None
    label = text[len(VOICE_LIST_PREFIX):].rstrip(':')
    for code, group_label in VOICE_GROUP_LABELS.items():
        if group_label == label:
            return code
    return None


def format_unsupported_language(langs: str) -> str:
    return f'😕 Unsupported language. Choose from: {langs}'


def format_language_set(lang: str) -> str:
    return f'🌐 Language set to: {LANGUAGE_LABELS.get(lang, lang)}'


def format_size_set_command(size_key: str) -> str:
    return f'📏 Summary size set to: {SIZE_LABELS.get(size_key, size_key)}'


def format_size_toast(size_key: str) -> str:
    return f'📏 Size: {SIZE_LABELS[size_key]}'


def format_language_toast(lang: str) -> str:
    return f'🌐 Language: {LANGUAGE_LABELS.get(lang, lang)}'


def format_voice_toast(voice_id: str) -> str:
    return f'🔊 Voice: {get_voice_label(voice_id)}'


def format_total_users(count: int) -> str:
    return f'👥 Total users: {count}'


def format_bcast_finished(errors: int) -> str:
    return f'📢 Broadcast finished with {errors} errors.'


def format_error(error_text: str) -> str:
    return f'⚠️ An error occurred: {error_text}'
