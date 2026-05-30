# YouTube Summarizer Bot

A Telegram bot that summarizes YouTube videos. Send a link and receive a text summary (`.txt` and `.md`) plus an audio version (`.mp3`) of the summary.

## Features

- **Summarization via DeepSeek or OpenRouter** — choose the LLM provider in `.env`
- **Subtitle extraction** — if the video has subtitles, the bot fetches them via `youtube-transcript-api`
- **Audio transcription** — when subtitles are missing, downloads audio (32 kbps mono) and transcribes via OpenRouter (Gemini 2.5 Flash)
- **LLM ad cleanup** — sponsor segments, self-promo, and “like/subscribe” calls are stripped before summarization
- **Transcript cache** — resending the same video reuses cached text without re-downloading
- **Configurable length** — `/short`, `/medium`, `/long` or buttons in `/settings`
- **Configurable language** — buttons in `/settings` / `/language` or `/language ru`
- **TTS voice selection** — `/voice` with language groups and ~30 edge-tts neural voices (independent of summary language)
- **Menu button** — command list next to the input field in Telegram
- **edge-tts narration** — audio summary sent as a voice message
- **SQLite** — per-user settings (no Redis)
- **Broadcast** — `/bcast` for admin messages to all users
- **Retry with backoff** — 3 retries with exponential delay on network failures (LLM API and OpenRouter transcription)

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome and current settings |
| `/settings` | Settings with inline buttons (size, language, voice) |
| `/language` | Summary language (buttons or `/language <code>`) |
| `/voice` | TTS voice (group → voice) |
| `/short` | Short summary (bullet points, 3–7 items) |
| `/medium` | Medium — structured overview by sections |
| `/long` | Long — detailed breakdown with examples |
| `/users` | User count (admin only) |
| `/bcast` | Broadcast a reply message to all users |

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/kstka/youtube-summarizer-bot.git
cd youtube-summarizer-bot
```

### 2. Create a Python virtual environment

Use a dedicated `venv/` in the project root so dependencies do not mix with the system Python:

```bash
python3 -m venv venv
```

Activate it when you work in a shell:

```bash
source venv/bin/activate
```

### 3. Install dependencies

With the virtual environment active (or using `venv/bin/pip`):

```bash
pip install -r requirements.txt
```

### 4. Install ffmpeg (required for audio fallback)

When a video has no subtitles, the bot downloads audio with `pytubefix` and converts it to mono MP3 (16 kHz, 32 kbps) with `ffmpeg` before sending it to OpenRouter for transcription. Videos with subtitles do not use `ffmpeg`.

```bash
sudo apt install ffmpeg
```

### 5. Configure environment variables

Copy the example file and edit `.env`:

```bash
cp .env.example .env
```

See [Configuration](#configuration) below for every variable.

### 6. Run the bot

```bash
python main.py
```

## Systemd service

For production on Linux, run the bot as a systemd unit under a dedicated user. The example below assumes the app lives at `/opt/youtube-summarizer-bot` and runs as user `sammy`.

### 1. Deploy the application

Install the bot under `/opt/youtube-summarizer-bot` (clone or copy the repo), then complete [steps 2–5](#installation) there: create `venv/`, install dependencies, install `ffmpeg`, and configure `.env`.

Ensure runtime directories exist and are writable by `sammy` (`logs/`, `database/`, `cache/` are tracked in git with `.dummy` placeholders; SQLite and cache files are created at runtime):

```bash
sudo mkdir -p /opt/youtube-summarizer-bot
sudo chown -R sammy:sammy /opt/youtube-summarizer-bot
```

### 2. Install the unit file

Copy the service unit from the repository and reload systemd:

```bash
sudo cp deploy/youtube-summarizer-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 3. Enable and start

```bash
sudo systemctl enable youtube-summarizer-bot
sudo systemctl start youtube-summarizer-bot
```

Check status:

```bash
sudo systemctl status youtube-summarizer-bot
```

Rotating file logs are written to `logs/bot.log` under the app directory (see [Logging](#logging)). Recent stderr output is also available in the journal:

```bash
sudo journalctl -u youtube-summarizer-bot -f
```

After updating code or `.env`, restart the service:

```bash
sudo systemctl restart youtube-summarizer-bot
```

## Configuration

All settings are loaded from `.env` via `python-dotenv` into [`summarizer/config.py`](summarizer/config.py). Required values must be set before the bot can serve requests.

### Telegram

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | yes | — | Bot token from [@BotFather](https://t.me/BotFather). |
| `ADMIN_USER_ID` | yes | `0` | Your Telegram numeric user ID. Used for `/users` and `/bcast`. |

### LLM provider

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | no | `deepseek` | Provider for summarization: `deepseek` or `openrouter`. |

### DeepSeek

Used when `LLM_PROVIDER=deepseek`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | if DeepSeek | — | API key from DeepSeek. |
| `DEEPSEEK_MODEL` | no | `deepseek-v4-pro` | Model id for summarization and transcript cleanup. |

### OpenRouter

Used when `LLM_PROVIDER=openrouter`, and always for audio transcription when subtitles are unavailable.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | if OpenRouter summarization or audio fallback | — | OpenRouter API key. Required for audio transcription even when `LLM_PROVIDER=deepseek`. |
| `OPENROUTER_MODEL` | no | `google/gemini-3-flash` | Model for summarization and transcript cleanup. |
| `AUDIO_MODEL` | no | `google/gemini-2.5-flash` | Model for transcribing downloaded audio when the video has no usable subtitles. |

At least one of `DEEPSEEK_API_KEY` or `OPENROUTER_API_KEY` must be set for the chosen provider. If `LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY` is empty, summarization will not work.

### YouTube (optional)

Used when fetching subtitles or downloading audio. Leave empty for a direct connection.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `YOUTUBE_PROXIES` | no | *(empty)* | Comma- or newline-separated proxy URLs. One proxy is chosen at random per YouTube request. Supported schemes: `http://`, `https://`, `socks5://`, `socks5h://`. |

### Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_PATH` | no | `database/bot.sqlite3` | SQLite database path for user settings. Parent directory must exist; the app does not create it. |
| `ACCESS_PASSWORD` | no | *(empty)* | Password new users must send before using the bot. Leave empty to disable the gate (recommended for local dev). |

### Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_DIR` | no | `logs` | Directory for rotating log files (`bot.log`). Must exist if you change the default. |
| `LOG_ROTATION` | no | `10 MB` | loguru rotation size (e.g. `10 MB`). |
| `LOG_RETENTION` | no | `14 days` | How long rotated log files are kept. |

Logs go to stderr and to `{LOG_DIR}/bot.log`.

### Sentry (optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTRY_DSN` | no | *(empty)* | If set, ERROR-level loguru events and unhandled exceptions are sent to [Sentry](https://sentry.io). Omit for local development. |
| `SENTRY_ENVIRONMENT` | no | `production` | Environment tag on Sentry events (e.g. `production`, `staging`). |

## How it works

1. User sends a YouTube link.
2. The bot checks the transcript cache; if the video was processed before, cached text is reused.
3. Otherwise: fetch subtitles via `youtube-transcript-api` (via a random proxy from `YOUTUBE_PROXIES` when configured).
4. If there are no subtitles: download audio with `pytubefix` (same proxy pool), convert to mono MP3 (16 kHz, 32 kbps) with `ffmpeg`, and transcribe via OpenRouter.
5. The transcript is cleaned with the LLM (ads, sponsors, “like/subscribe”).
6. Clean text is cached and sent to the configured LLM for summarization.
7. Summary is delivered as `.txt` and `.md` and stored under `cache/summaries/` keyed by `video_id`, size, language, and LLM provider.
8. Audio is generated with `edge-tts` from the plain summary, sent as `.mp3`, and cached under `cache/audio/` (same key plus TTS voice).
9. Repeat requests with the same settings serve summary and/or audio from cache without calling the LLM or TTS again.
10. On network failures: up to 3 retries with backoff 2 / 5 / 15 seconds.

## Dependencies

### Python packages

- `aiogram` — Telegram Bot API
- `youtube-transcript-api` — fetch YouTube subtitles
- `pytubefix` — download audio when subtitles are unavailable
- `PySocks` — SOCKS5 proxy support for YouTube requests
- `aiohttp` — async HTTP to LLM APIs
- `aiosqlite` — SQLite user settings
- `edge-tts` — speech synthesis (Microsoft Edge TTS)
- `python-dotenv` — load `.env`
- `loguru` — logging (console + rotation under `logs/`)
- `sentry-sdk` — error monitoring (optional, via `SENTRY_DSN`)

### System

- `ffmpeg` — convert downloaded YouTube audio to mono MP3 before transcription (audio fallback only)

## License

MIT License — see [LICENSE](LICENSE).
