import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

DB_PATH = Path(__file__).parent / "news.sqlite"

DEFAULT_RSS_SOURCES = [
    ("TechCrunch AI",       "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/"),
    ("AI News",             "https://www.artificialintelligence-news.com/feed/"),
    ("Reddit r/artificial", "https://www.reddit.com/r/artificial/.rss"),
    ("Reddit r/LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/.rss"),
    ("Hacker News",         "https://hnrss.org/newest?q=AI+OR+LLM+OR+Claude+OR+ChatGPT&count=20"),
    ("OpenAI Blog",         "https://openai.com/blog/rss.xml"),
    ("Google AI Blog",      "https://blog.research.google/feeds/posts/default"),
    ("Anthropic",           "https://www.anthropic.com/rss.xml"),
    ("The Decoder",         "https://the-decoder.com/feed/"),
]


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            url           TEXT    UNIQUE NOT NULL,
            title         TEXT    NOT NULL,
            source        TEXT,
            published_at  TEXT,
            fetched_at    TEXT    NOT NULL,
            body_text     TEXT,
            summary_ja    TEXT,
            summarized_at TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts
        USING fts5(
            title,
            body_text,
            summary_ja,
            content=articles,
            content_rowid=id,
            tokenize='unicode61 remove_diacritics 2'
        );

        CREATE TRIGGER IF NOT EXISTS articles_ai
        AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title, body_text, summary_ja)
            VALUES (new.id, new.title, new.body_text, new.summary_ja);
        END;

        CREATE TRIGGER IF NOT EXISTS articles_ad
        AFTER DELETE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, body_text, summary_ja)
            VALUES ('delete', old.id, old.title, old.body_text, old.summary_ja);
        END;

        CREATE TRIGGER IF NOT EXISTS articles_au
        AFTER UPDATE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, body_text, summary_ja)
            VALUES ('delete', old.id, old.title, old.body_text, old.summary_ja);
            INSERT INTO articles_fts(rowid, title, body_text, summary_ja)
            VALUES (new.id, new.title, new.body_text, new.summary_ja);
        END;

        CREATE TABLE IF NOT EXISTS rss_sources (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            url        TEXT    UNIQUE NOT NULL,
            is_active  INTEGER NOT NULL DEFAULT 1,
            created_at TEXT    NOT NULL
        );
    """)
    conn.commit()

    # マイグレーション: 既存DBへのカラム追加
    for col_def in [
        "ALTER TABLE articles ADD COLUMN title_ja TEXT",
        "ALTER TABLE articles ADD COLUMN genre TEXT",
        "ALTER TABLE articles ADD COLUMN is_favorite INTEGER DEFAULT 0",
        "ALTER TABLE articles ADD COLUMN is_read INTEGER DEFAULT 0",
    ]:
        try:
            conn.execute(col_def)
            conn.commit()
        except Exception:
            pass  # すでに存在する場合はスキップ

    # RSSソースのシード（テーブルが空なら初期ソースを挿入）
    count = conn.execute("SELECT COUNT(*) FROM rss_sources").fetchone()[0]
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        conn.executemany(
            "INSERT OR IGNORE INTO rss_sources (name, url, is_active, created_at) VALUES (?, ?, 1, ?)",
            [(name, url, now) for name, url in DEFAULT_RSS_SOURCES],
        )
        conn.commit()

    conn.close()


def _escape_fts5(query: str) -> str:
    """FTS5クエリの各トークンをダブルクォートで囲んで特殊文字をエスケープする。"""
    tokens = query.strip().split()
    escaped = []
    for t in tokens:
        t_clean = t.replace('"', '')
        if t_clean:
            escaped.append(f'"{t_clean}"')
    return ' '.join(escaped)


# ── Sync helpers ──────────────────────────────────────────────────────────

def _insert_article(url: str, title: str, source: str, published_at: Optional[str],
                    body_text: Optional[str] = None) -> Optional[int]:
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT OR IGNORE INTO articles
               (url, title, source, published_at, fetched_at, body_text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [url, title, source, published_at, now, body_text],
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        conn.close()


def _list_articles(search: str = "", sources: list = None,
                   genres: list = None, favorite_only: bool = False,
                   unread_only: bool = False, days_ago: int = None,
                   limit: int = 100, offset: int = 0) -> list[dict]:
    conn = _get_conn()
    try:
        sources = sources or []
        genres  = genres  or []

        def _in_clause(col: str, vals: list) -> tuple[str, list]:
            if not vals:
                return "", []
            ph = ",".join("?" * len(vals))
            return f"{col} IN ({ph})", list(vals)

        if search:
            escaped_search = _escape_fts5(search)
            conditions = ["articles_fts MATCH ?"]
            params: list = [escaped_search]
            src_cond, src_p = _in_clause("a.source", sources)
            gen_cond, gen_p = _in_clause("a.genre",  genres)
            if src_cond: conditions.append(src_cond); params.extend(src_p)
            if gen_cond: conditions.append(gen_cond); params.extend(gen_p)
            if favorite_only: conditions.append("a.is_favorite = 1")
            if unread_only:   conditions.append("COALESCE(a.is_read, 0) = 0")
            if days_ago is not None:
                conditions.append("a.fetched_at >= datetime('now', ?)")
                params.append(f"-{days_ago} days")
            where = " AND ".join(conditions)
            sql = f"""
                SELECT a.*
                FROM articles a
                JOIN articles_fts f ON f.rowid = a.id
                WHERE {where}
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
        else:
            conditions = []
            params = []
            src_cond, src_p = _in_clause("source", sources)
            gen_cond, gen_p = _in_clause("genre",  genres)
            if src_cond: conditions.append(src_cond); params.extend(src_p)
            if gen_cond: conditions.append(gen_cond); params.extend(gen_p)
            if favorite_only: conditions.append("is_favorite = 1")
            if unread_only:   conditions.append("COALESCE(is_read, 0) = 0")
            if days_ago is not None:
                conditions.append("fetched_at >= datetime('now', ?)")
                params.append(f"-{days_ago} days")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"""
                SELECT * FROM articles
                {where}
                ORDER BY fetched_at DESC
                LIMIT ? OFFSET ?
            """

        params.extend([limit, offset])
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            if search and ("fts5" in str(e).lower() or "syntax" in str(e).lower()):
                return []  # 不正な FTS5 クエリは空リストで安全に処理
            raise
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _get_article(article_id: int) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", [article_id]).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _get_article_by_url(url: str) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM articles WHERE url = ?", [url]).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _update_summary(article_id: int, summary_ja: str) -> None:
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        # Sanitize lone surrogates (invalid UTF-8 from model output) before SQLite storage
        summary_ja = summary_ja.encode('utf-8', 'replace').decode('utf-8')
        conn.execute(
            "UPDATE articles SET summary_ja = ?, summarized_at = ? WHERE id = ?",
            [summary_ja, now, article_id],
        )
        conn.commit()
    finally:
        conn.close()


def _update_genre(article_id: int, genre: str) -> None:
    conn = _get_conn()
    try:
        conn.execute("UPDATE articles SET genre = ? WHERE id = ?", [genre, article_id])
        conn.commit()
    finally:
        conn.close()


def _update_title_ja(article_id: int, title_ja: str) -> None:
    conn = _get_conn()
    try:
        title_ja = title_ja.encode('utf-8', 'replace').decode('utf-8')
        conn.execute("UPDATE articles SET title_ja = ? WHERE id = ?", [title_ja, article_id])
        conn.commit()
    finally:
        conn.close()


def _toggle_favorite(article_id: int) -> bool:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT is_favorite FROM articles WHERE id = ?", [article_id]).fetchone()
        if not row:
            return False
        new_val = 0 if row["is_favorite"] else 1
        conn.execute("UPDATE articles SET is_favorite = ? WHERE id = ?", [new_val, article_id])
        conn.commit()
        return bool(new_val)
    finally:
        conn.close()


def _mark_read(article_id: int, is_read: bool = True) -> None:
    conn = _get_conn()
    try:
        conn.execute("UPDATE articles SET is_read = ? WHERE id = ?", [int(is_read), article_id])
        conn.commit()
    finally:
        conn.close()


def _delete_article(article_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM articles WHERE id = ?", [article_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _count_articles() -> int:
    conn = _get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    finally:
        conn.close()


def _count_articles_filtered(search: str = "", sources: list = None,
                              genres: list = None, favorite_only: bool = False,
                              unread_only: bool = False, days_ago: int = None) -> int:
    conn = _get_conn()
    try:
        sources = sources or []
        genres  = genres  or []

        def _in_clause(col: str, vals: list):
            if not vals:
                return "", []
            ph = ",".join("?" * len(vals))
            return f"{col} IN ({ph})", list(vals)

        if search:
            escaped_search = _escape_fts5(search)
            conditions = ["articles_fts MATCH ?"]
            params: list = [escaped_search]
            src_cond, src_p = _in_clause("a.source", sources)
            gen_cond, gen_p = _in_clause("a.genre",  genres)
            if src_cond: conditions.append(src_cond); params.extend(src_p)
            if gen_cond: conditions.append(gen_cond); params.extend(gen_p)
            if favorite_only: conditions.append("a.is_favorite = 1")
            if unread_only:   conditions.append("COALESCE(a.is_read, 0) = 0")
            if days_ago is not None:
                conditions.append("a.fetched_at >= datetime('now', ?)")
                params.append(f"-{days_ago} days")
            where = " AND ".join(conditions)
            sql = f"""
                SELECT COUNT(*) FROM articles a
                JOIN articles_fts f ON f.rowid = a.id
                WHERE {where}
            """
        else:
            conditions = []
            params = []
            src_cond, src_p = _in_clause("source", sources)
            gen_cond, gen_p = _in_clause("genre",  genres)
            if src_cond: conditions.append(src_cond); params.extend(src_p)
            if gen_cond: conditions.append(gen_cond); params.extend(gen_p)
            if favorite_only: conditions.append("is_favorite = 1")
            if unread_only:   conditions.append("COALESCE(is_read, 0) = 0")
            if days_ago is not None:
                conditions.append("fetched_at >= datetime('now', ?)")
                params.append(f"-{days_ago} days")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            sql = f"SELECT COUNT(*) FROM articles {where}"

        try:
            return conn.execute(sql, params).fetchone()[0]
        except sqlite3.OperationalError:
            return 0
    finally:
        conn.close()


# ── RSS sources ────────────────────────────────────────────────────────────

def _get_rss_sources() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM rss_sources ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _add_rss_source(name: str, url: str) -> Optional[dict]:
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT OR IGNORE INTO rss_sources (name, url, is_active, created_at) VALUES (?, ?, 1, ?)",
            [name, url, now],
        )
        conn.commit()
        if cur.rowcount == 0:
            return None  # 重複URL
        row = conn.execute("SELECT * FROM rss_sources WHERE id = ?", [cur.lastrowid]).fetchone()
        return dict(row)
    finally:
        conn.close()


def _delete_rss_source(source_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM rss_sources WHERE id = ?", [source_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _toggle_rss_source(source_id: int) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM rss_sources WHERE id = ?", [source_id]).fetchone()
        if not row:
            return None
        new_val = 0 if row["is_active"] else 1
        conn.execute("UPDATE rss_sources SET is_active = ? WHERE id = ?", [new_val, source_id])
        conn.commit()
        row = conn.execute("SELECT * FROM rss_sources WHERE id = ?", [source_id]).fetchone()
        return dict(row)
    finally:
        conn.close()


# ── Async wrappers ────────────────────────────────────────────────────────

async def insert_article(url: str, title: str, source: str,
                         published_at: Optional[str],
                         body_text: Optional[str] = None) -> Optional[int]:
    return await asyncio.to_thread(_insert_article, url, title, source, published_at, body_text)


async def list_articles(search: str = "", sources: list = None, genres: list = None,
                        favorite_only: bool = False, unread_only: bool = False,
                        days_ago: int = None,
                        limit: int = 100, offset: int = 0) -> list[dict]:
    return await asyncio.to_thread(
        _list_articles, search, sources or [], genres or [],
        favorite_only, unread_only, days_ago, limit, offset,
    )


async def get_article(article_id: int) -> Optional[dict]:
    return await asyncio.to_thread(_get_article, article_id)


async def get_article_by_url(url: str) -> Optional[dict]:
    return await asyncio.to_thread(_get_article_by_url, url)


async def update_summary(article_id: int, summary_ja: str) -> None:
    await asyncio.to_thread(_update_summary, article_id, summary_ja)


async def update_genre(article_id: int, genre: str) -> None:
    await asyncio.to_thread(_update_genre, article_id, genre)


async def update_title_ja(article_id: int, title_ja: str) -> None:
    await asyncio.to_thread(_update_title_ja, article_id, title_ja)


async def toggle_favorite(article_id: int) -> bool:
    return await asyncio.to_thread(_toggle_favorite, article_id)


async def mark_read(article_id: int, is_read: bool = True) -> None:
    await asyncio.to_thread(_mark_read, article_id, is_read)


async def delete_article(article_id: int) -> bool:
    return await asyncio.to_thread(_delete_article, article_id)


async def count_articles() -> int:
    return await asyncio.to_thread(_count_articles)


async def count_articles_filtered(search: str = "", sources: list = None,
                                   genres: list = None, favorite_only: bool = False,
                                   unread_only: bool = False, days_ago: int = None) -> int:
    return await asyncio.to_thread(
        _count_articles_filtered, search, sources or [], genres or [],
        favorite_only, unread_only, days_ago,
    )


async def get_rss_sources() -> list[dict]:
    return await asyncio.to_thread(_get_rss_sources)


async def add_rss_source(name: str, url: str) -> Optional[dict]:
    return await asyncio.to_thread(_add_rss_source, name, url)


async def delete_rss_source(source_id: int) -> bool:
    return await asyncio.to_thread(_delete_rss_source, source_id)


async def toggle_rss_source(source_id: int) -> Optional[dict]:
    return await asyncio.to_thread(_toggle_rss_source, source_id)
