# Agent guidelines

## Documentation

- **README.md** must be written in **English** (project overview, installation, configuration, and operator docs).
- User-facing bot messages in Telegram stay localized per product requirements; do not use README for in-bot copy.

## Python and tests

- Run **all** Python invocations for tests (pytest, one-off scripts, `python -m …`) from the project virtual environment at **`venv/`** — not the system interpreter.
- Prefer explicit paths without activation: `venv/bin/python -m pytest`, `venv/bin/python script.py`.
- Alternatively activate first: `source venv/bin/activate` (Linux/macOS), then run commands as usual.
- If `venv/` is missing, create it per [README.md](README.md) (`python3 -m venv venv`, `pip install -r requirements.txt`) before running tests.

## Runtime directories

- Application code must **not** create directories (`mkdir`, `makedirs`, `Path.mkdir`, etc.) or check whether parent dirs exist before writing.
- Required dirs live in the repo with a **`.dummy`** placeholder so git tracks empty folders.
- When adding a new persistent path: add `path/.dummy`, adjust `.gitignore` to ignore runtime files but keep `.dummy`, and do not add mkdir in code.
- If `LOG_DIR` or `DB_PATH` in `.env` point outside the default tree, the operator creates that layout manually (not handled in code).

## Logging

Log **key steps** of bot activity so operators can follow a request through the pipeline without reading every line of code.

- Use **loguru**: `from loguru import logger` in each module.
- Configure logging once at startup via [`summarizer/logging_setup.py`](summarizer/logging_setup.py) (`setup_logging()` in `main.py` before other app code).
- Keep loguru’s **default stderr format** — do not add a custom `format=` on handlers.
- Rotating file logs live under **`logs/`** (`logs/bot.log`, rotation/retention from `config.Logging`).
- **INFO** — lifecycle milestones: bot start, access password gate enabled/disabled at startup, successful user authorization (`user_id`), incoming summarize request, transcript source (cache / subtitles / audio), summary cache hit, audio cache hit, summary and TTS completion, settings changes, admin broadcast start/finish.
- **WARNING** — recoverable or user-facing failures (empty transcript, summary failed, oversized audio truncated).
- **ERROR** / **exception** — unexpected failures and failed HTTP/API calls (include status code, not full response bodies).

Keep volume low:

- Do **not** log full transcripts, summaries, or API keys.
- Do **not** log per-user broadcast delivery; log broadcast totals only.
- Do **not** add debug logs for routine control flow unless diagnosing a specific issue.
- Prefer one log line per pipeline stage over logging inside tight loops.

Include useful context in messages: `user_id`, `video_id`, `source`, `provider`, `size`, `language`, and byte/character counts where helpful. Use loguru `{}` placeholders, not `%s`.

## Error monitoring (Sentry)

- Enable with `SENTRY_DSN` in `.env`; without DSN, Sentry is not initialized (console + file logs only).
- Initialized once via [`summarizer/sentry_setup.py`](summarizer/sentry_setup.py) (`init_sentry()` in `main.py` after `setup_logging()`).
- **ERROR** and above (`logger.error`, `logger.exception`) are sent to Sentry as issues; **WARNING** stays local only.
- Unhandled asyncio/aiogram exceptions are captured by the SDK automatically.
- Use loguru for failures; do not call `sentry_sdk.capture_message` for routine errors.
- Do not attach secrets, full transcripts, or full summaries to Sentry events.
