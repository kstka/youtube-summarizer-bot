# Fix Plan

## A. Dependencies (`requirements.txt`)
Add:
```
webvtt-py>=0.5.0
```

## B. Cache module (`cache.py` — new file)

Directory structure:
```
cache/
  transcripts/<video_id>.txt          # raw transcript text (ad-cleaned)
  transcripts/<video_id>.meta.json    # {source, language, duration, created_at}
  summaries/<video_id>__<size>__<lang>__<provider>__<timestamp>.txt
```

API:
```python
def transcript_path(video_id: str) -> Path
def load_transcript(video_id: str) -> Optional[dict]   # text + meta or None
def save_transcript(video_id, text, source, language)
def save_summary(video_id, size, language, provider, summary)   # always append-new, NOT a lookup
```
- `transcripts/` is read before downloading; cached file is used directly if present.
- `summaries/` is write-only: never read back to serve to users. Stored for analysis.
- `__` (double underscore) as separator to avoid collisions with `_` in video_id.

## C. `transcript.py` — rewrite

### C.1 Subtitles via yt-dlp download + webvtt-py
```python
ydl_opts = {
    'skip_download': True,
    'writesubtitles': True,
    'writeautomaticsub': True,
    'subtitleslangs': SUPPORTED_LANGS,
    'subtitlesformat': 'vtt',
    'outtmpl': str(tmp_dir / 'sub.%(ext)s'),
    'retries': 5,
    'fragment_retries': 5,
    'quiet': True,
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=True)
# find sub.<lang>.vtt by language priority → parse with webvtt.read()
```
Parsing: join all `cap.text` with spaces; deduplicate consecutive identical lines (auto-caption scroll artifact).

Remove `urllib.request` import entirely.

### C.2 Audio fallback (no SponsorBlock)
```python
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '32',
    }],
    'postprocessor_args': ['-ac', '1', '-ar', '16000'],   # mono, 16 kHz
    'outtmpl': str(tmp_dir / 'audio_%(id)s.%(ext)s'),
    'retries': 5,
    'quiet': True,
}
```
Reduces 30–40 MB to ~5–10 MB for a 1-hour video.

### C.3 OpenRouter transcription — improvements
- `ClientTimeout(total=600, connect=30, sock_read=600)`.
- Retries (3, backoff 2/5/15) for: `aiohttp.ClientError`, `asyncio.TimeoutError`, HTTP 429, HTTP 5xx.
- If payload > 25 MB — log warning, but proceed anyway.
- On final fail — specific error message to user (HTTP status / error text).

### C.4 Universal retry helper
```python
async def with_retries(coro_factory, attempts=3, base_delay=2.0, multiplier=3.0):
    for i in range(attempts):
        try:
            return await coro_factory()
        except RETRIABLE_EXC as e:
            if i == attempts - 1:
                raise
            await asyncio.sleep(base_delay * (multiplier ** i))
```

### C.5 LLM ad-cleaning (new function in `summarizer.py`)
```python
async def clean_ads(transcript: str, language: str) -> str:
    system = (
        'You are a text cleaner. Remove sponsorship reads, paid promotions, '
        'self-promotion blocks, "like and subscribe" calls, intro/outro filler, '
        'and any explicit ad reads from the following transcript. Preserve all '
        'substantive content verbatim. Output ONLY the cleaned text, no explanations.'
    )
    # call via the same provider as summarization (App.LLM_PROVIDER)
    # max_tokens large, temperature=0.1
```
Called between "got transcript" and "saved to cache". Cache stores the cleaned text.

### C.6 Main flow
```python
async def get_transcript(url, openrouter_api_key, tmp_dir) -> tuple[str, str]:
    vid = extract_video_id(url)

    cached = cache.load_transcript(vid)
    if cached:
        return cached['text'], 'cache'

    text = await with_retries(lambda: try_subtitles(url, tmp_dir))
    source = 'subtitles' if text else None

    if not text:
        text = await with_retries(lambda: try_audio(url, openrouter_api_key, tmp_dir))
        source = 'audio' if text else None

    if not text:
        return '', 'failed'

    cleaned = await clean_ads(text, language='auto')  # LLM ad cleanup
    cache.save_transcript(vid, cleaned, source=source, language='auto')
    return cleaned, source
```

## D. `main.py` — changes

Flow:
```
status: 'Extracting transcript...'
  -> get_transcript() (internally: cache → subtitles → audio → LLM ad-clean)
status: 'Generating summary...'
  -> get_summary(transcript, size, lang, provider)
  -> cache.save_summary(...)        # for analysis only, not for serving
  -> send .txt
status: 'Generating audio version...'
  -> tts.synthesize()
  -> send .mp3
delete status
```

On cache hit — no visible difference (option 5a): status "Generating summary..." appears almost instantly.

## E. `.gitignore`
Add:
```
cache/
```

## F. File list

| File | Action |
|------|--------|
| `requirements.txt` | + `webvtt-py>=0.5.0` |
| `cache.py` | **new** — file-based transcript cache + summary log |
| `transcript.py` | rewrite: subtitles via yt-dlp download + webvtt-py, audio 32k mono, retries, remove `urllib` |
| `summarizer.py` | add `clean_ads()` (LLM ad filtering) |
| `main.py` | pass `tmp_dir` to `get_transcript`; call `cache.save_summary()` after generation |
| `.gitignore` | + `cache/` |
| `README.md` | update sections "Features", "How It Works", "Dependencies" |
| `PLAN.md` | **this file** |

## G. Success criteria
1. Video with subtitles processes without HTTP 429 (yt-dlp downloads internally).
2. Video without subtitles (~1 hour): final mp3 < 10 MB, OpenRouter accepts it.
3. Transcript is cleaned via LLM-cleaner before summarization — ads, sponsorship and "like/subscribe" calls removed.
4. Re-sending the same URL → transcript loaded from `cache/transcripts/<id>.txt`, no re-download.
5. Every generated summary is saved to `cache/summaries/<id>__<size>__<lang>__<provider>__<timestamp>.txt`.
6. Network failures → 3 retries with backoff 2/5/15 seconds.
