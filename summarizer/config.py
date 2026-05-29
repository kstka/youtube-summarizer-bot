import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Telegram:
    BOT_TOKEN: str = os.environ.get('BOT_TOKEN', '')
    ADMIN_USER_ID: int = int(os.environ.get('ADMIN_USER_ID', 0))


@dataclass
class DeepSeek:
    API_KEY: str = os.environ.get('DEEPSEEK_API_KEY', '')
    MODEL: str = os.environ.get('DEEPSEEK_MODEL', 'deepseek-v4-pro')
    BASE_URL: str = 'https://api.deepseek.com/v1'


@dataclass
class OpenRouter:
    API_KEY: str = os.environ.get('OPENROUTER_API_KEY', '')
    MODEL: str = os.environ.get('OPENROUTER_MODEL', 'google/gemini-3-flash')
    BASE_URL: str = 'https://openrouter.ai/api/v1'


@dataclass
class Audio:
    MODEL: str = os.environ.get('AUDIO_MODEL', 'google/gemini-2.5-flash')
    BASE_URL: str = 'https://openrouter.ai/api/v1'


@dataclass
class App:
    DB_PATH: str = os.environ.get('DB_PATH', 'database/bot.sqlite3')
    DEFAULT_SIZE: str = 'medium'
    DEFAULT_LANG: str = 'ru'
    LLM_PROVIDER: str = os.environ.get('LLM_PROVIDER', 'deepseek')
    ACCESS_PASSWORD: str = os.environ.get('ACCESS_PASSWORD', '')


@dataclass
class Logging:
    DIR: str = os.environ.get('LOG_DIR', 'logs')
    ROTATION: str = os.environ.get('LOG_ROTATION', '10 MB')
    RETENTION: str = os.environ.get('LOG_RETENTION', '14 days')


@dataclass
class Sentry:
    DSN: str = os.environ.get('SENTRY_DSN', '')
    ENVIRONMENT: str = os.environ.get('SENTRY_ENVIRONMENT', 'production')
