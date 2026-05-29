from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands


BOT_COMMANDS = [
    BotCommand(command='start', description='ℹ️ Help and current settings'),
    BotCommand(command='settings', description='⚙️ Open settings menu'),
    BotCommand(command='language', description='🌐 Summary language'),
    BotCommand(command='voice', description='🔊 TTS voice'),
    BotCommand(command='short', description='📄 Short summary'),
    BotCommand(command='medium', description='📰 Medium summary'),
    BotCommand(command='long', description='📚 Long summary'),
]


async def setup_bot_menu(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
