# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Server

```powershell
cd C:\dev\projects\news-dj
C:\Users\syyty\anaconda3\python.exe -m uvicorn main:app --reload --port 8000
```

The app runs at http://localhost:8000. No build step required.

## Environment

- Python: `C:\Users\syyty\anaconda3\python.exe` (3.11.7, Anaconda)
- `pip` is NOT on PATH in bash — use `C:\Users\syyty\anaconda3\python.exe -m pip`
- Pydantic v1 (1.10.12) — use v1-compatible syntax (no `model_dump()`, use `.dict()`)

## Summarizer Engine

Controlled by env var `SUMMARIZER` or auto-detected:
- `SUMMARIZER=claude` → `claude-haiku-4-5-20251001` (requires `ANTHROPIC_API_KEY`)
- `SUMMARIZER=ollama` → `qwen3.5` at `http://localhost:11434`
- Auto: Claude if `ANTHROPIC_API_KEY` is set, else Ollama

## Architecture

All DB operations follow a **sync `_fn()` + async wrapper via `asyncio.to_thread()`** pattern. Never call sync DB functions directly from async routes — always use the async wrappers in `database.py`.

### Data flow
1. `main.py` — FastAPI routes; delegates all logic to modules below
2. `database.py` — SQLite + FTS5 (WAL mode). Schema migrations run inline in `init_db()` via `ALTER TABLE ... ADD COLUMN` wrapped in try/except. RSS sources seeded on first run.
3. `news_fetcher.py` — Fetches RSS feeds concurrently via `asyncio.gather`; scrapes individual URLs with httpx + BeautifulSoup. Body text capped at 5000 chars.
4. `summarizer.py` — Japanese summarization and title translation. SSE streaming via `AsyncGenerator`. Claude uses `client.messages.stream()`; Ollama uses `httpx.AsyncClient.stream()`.
5. `classifier.py` — Keyword-scoring genre classifier (no ML). 5 genres: `research`, `tools`, `business`, `society`, `build_ideas`. Title weighted 2×, body first 600 chars weighted 1×. High-signal keywords score 3× normal.

### SSE endpoints
Several endpoints return `StreamingResponse` with `text/event-stream`. Each SSE line format: `data: <JSON>\n\n`. Terminal event includes `{"done": true}`.

### FTS5 search
`articles_fts` is a content table backed by `articles`. Updated via triggers on INSERT/UPDATE/DELETE. Search query passed directly to `MATCH` — no escaping currently applied.

### RSS source management
Sources stored in `rss_sources` table (not hardcoded). Default 10 sources seeded on first run. `POST /api/fetch-rss` reads active sources from DB at call time.
