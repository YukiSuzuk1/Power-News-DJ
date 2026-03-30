import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
import json
from pydantic import BaseModel, AnyHttpUrl
from typing import Optional, List
import database
import news_fetcher
import summarizer
import classifier

logger = logging.getLogger(__name__)

# AI エンドポイントの同時実行を 1 に制限（コスト/DoS対策）
_ai_semaphore = asyncio.Semaphore(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'"
        )
        return response


app = FastAPI(title="AI News DJ", lifespan=lifespan)
app.add_middleware(_SecurityHeadersMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic Models ───────────────────────────────────────────────────────

class ArticleOut(BaseModel):
    id: int
    url: str
    title: str
    source: Optional[str] = None
    published_at: Optional[str] = None
    fetched_at: str
    body_text: Optional[str] = None
    summary_ja: Optional[str] = None
    summarized_at: Optional[str] = None
    title_ja: Optional[str] = None
    genre: Optional[str] = None
    is_favorite: Optional[int] = 0
    is_read: Optional[int] = 0


class AddUrlRequest(BaseModel):
    url: AnyHttpUrl


class FetchResult(BaseModel):
    added: int
    skipped: int
    failed: int


class SummarizeResponse(BaseModel):
    id: int
    summary_ja: str
    engine: str


class DeleteResponse(BaseModel):
    deleted: bool


class CountResponse(BaseModel):
    count: int


class EngineResponse(BaseModel):
    engine: str


class RssSourceOut(BaseModel):
    id: int
    name: str
    url: str
    is_active: int
    created_at: str


class AddSourceRequest(BaseModel):
    name: str
    url: AnyHttpUrl


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("static/index.html")


@app.get("/api/engine", response_model=EngineResponse)
async def get_engine():
    return EngineResponse(engine=summarizer.get_engine_name())


@app.get("/api/count", response_model=CountResponse)
async def count(
    search: str = Query(""),
    source: List[str] = Query([]),
    genre: List[str] = Query([]),
    favorite_only: bool = Query(False),
    unread_only: bool = Query(False),
    days_ago: Optional[int] = Query(None, ge=1, le=365),
):
    if search or source or genre or favorite_only or unread_only or days_ago:
        n = await database.count_articles_filtered(
            search=search, sources=source, genres=genre,
            favorite_only=favorite_only, unread_only=unread_only, days_ago=days_ago,
        )
    else:
        n = await database.count_articles()
    return CountResponse(count=n)


@app.get("/api/articles", response_model=list[ArticleOut])
async def get_articles(
    search: str = Query("", description="全文検索キーワード"),
    source: List[str] = Query([], description="ソースのホスト名でフィルタ（複数可）"),
    genre: List[str] = Query([], description="ジャンルIDでフィルタ（複数可）"),
    favorite_only: bool = Query(False, description="お気に入りのみ"),
    unread_only: bool = Query(False, description="未読のみ"),
    days_ago: Optional[int] = Query(None, ge=1, le=365, description="過去N日以内"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await database.list_articles(
        search=search, sources=source, genres=genre,
        favorite_only=favorite_only, unread_only=unread_only,
        days_ago=days_ago, limit=limit, offset=offset,
    )


@app.get("/api/articles/{article_id}", response_model=ArticleOut)
async def get_article(article_id: int):
    article = await database.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    return article


@app.post("/api/fetch-rss", response_model=FetchResult)
async def fetch_rss():
    """アクティブなRSSソースをDBから読み込んで取得する。"""
    sources = await database.get_rss_sources()
    active_urls = [s["url"] for s in sources if s["is_active"]]
    articles = await news_fetcher.fetch_rss_feeds(active_urls)
    added = skipped = failed = 0
    for a in articles:
        try:
            result = await database.insert_article(
                url=a["url"], title=a["title"], source=a["source"],
                published_at=a.get("published_at"), body_text=a.get("body_text"),
            )
            if result:
                added += 1
            else:
                skipped += 1
        except Exception:
            failed += 1
    return FetchResult(added=added, skipped=skipped, failed=failed)


@app.post("/api/fetch-rss/stream")
async def fetch_rss_stream():
    """アクティブなRSSソースをひとつずつ取得し、SSEで進捗を返す。"""
    sources = await database.get_rss_sources()
    active_sources = [s for s in sources if s["is_active"]]

    async def generate():
        total_added = total_skipped = total_failed = 0
        for s in active_sources:
            url  = s["url"]
            name = s["name"]
            yield f"data: {json.dumps({'source': name, 'status': 'fetching'}, ensure_ascii=False)}\n\n"
            try:
                articles = await news_fetcher._fetch_single_feed(url)
                added = skipped = failed = 0
                for a in articles:
                    try:
                        result = await database.insert_article(
                            url=a["url"], title=a["title"], source=a["source"],
                            published_at=a.get("published_at"), body_text=a.get("body_text"),
                        )
                        if result:
                            added += 1
                        else:
                            skipped += 1
                    except Exception:
                        failed += 1
                total_added   += added
                total_skipped += skipped
                total_failed  += failed
                yield f"data: {json.dumps({'source': name, 'status': 'done', 'added': added, 'skipped': skipped, 'failed': failed}, ensure_ascii=False)}\n\n"
            except Exception as e:
                total_failed += 1
                yield f"data: {json.dumps({'source': name, 'status': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True, 'total_added': total_added, 'total_skipped': total_skipped, 'total_failed': total_failed}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream; charset=utf-8")


@app.post("/api/add-url", response_model=ArticleOut)
async def add_url(body: AddUrlRequest):
    try:
        article_data = await news_fetcher.scrape_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("URL fetch failed for %s: %s", body.url, e)
        raise HTTPException(status_code=422, detail="URLの取得に失敗しました")

    article_id = await database.insert_article(**article_data)
    if article_id is None:
        existing = await database.get_article_by_url(body.url)
        if existing:
            return existing
        raise HTTPException(status_code=409, detail="記事は既に登録されています")

    return await database.get_article(article_id)


@app.post("/api/articles/{article_id}/summarize", response_model=SummarizeResponse)
async def summarize(article_id: int):
    article = await database.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")

    engine = summarizer.get_engine_name()
    if engine == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY が設定されていません")

    try:
        async with _ai_semaphore:
            summary_ja = await summarizer.summarize_article(
                title=article["title"], url=article["url"],
                published_at=article.get("published_at"),
                body_text=article.get("body_text") or "",
            )
    except Exception as e:
        logger.error("Summarize failed (engine=%s, id=%d): %s", engine, article_id, e)
        raise HTTPException(status_code=502, detail=f"要約に失敗しました ({engine})")

    await database.update_summary(article_id, summary_ja)
    return SummarizeResponse(id=article_id, summary_ja=summary_ja, engine=engine)


@app.post("/api/articles/{article_id}/summarize/stream")
async def summarize_stream(article_id: int):
    article = await database.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")

    engine = summarizer.get_engine_name()
    if engine == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY が設定されていません")

    collected: list[str] = []

    async def generate():
        try:
            async for token in summarizer.stream_article(article):
                collected.append(token)
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            full_summary = "".join(collected)
            # Sanitize lone surrogates that SQLite cannot store as UTF-8
            full_summary = full_summary.encode('utf-8', 'replace').decode('utf-8')
            await database.update_summary(article_id, full_summary)
            yield f"data: {json.dumps({'done': True, 'summary': full_summary}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream; charset=utf-8")


@app.post("/api/articles/{article_id}/read")
async def mark_read(article_id: int):
    """記事を既読にする。"""
    article = await database.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    await database.mark_read(article_id)
    return {"id": article_id, "is_read": 1}


@app.post("/api/articles/{article_id}/favorite")
async def toggle_favorite(article_id: int):
    """お気に入りをトグルする。"""
    article = await database.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    new_val = await database.toggle_favorite(article_id)
    return {"id": article_id, "is_favorite": int(new_val)}


@app.post("/api/classify-all")
async def classify_all_articles():
    articles = await database.list_articles(limit=2000)
    for a in articles:
        genre = classifier.classify_article(a.get("title", ""), a.get("body_text"))
        await database.update_genre(a["id"], genre)
    return {"classified": len(articles)}


@app.post("/api/articles/{article_id}/translate-title")
async def translate_title(article_id: int):
    article = await database.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    try:
        async with _ai_semaphore:
            title_ja = await summarizer.translate_title(article["title"])
    except Exception as e:
        logger.error("Title translate failed (id=%d): %s", article_id, e)
        raise HTTPException(status_code=502, detail="タイトルの翻訳に失敗しました")
    await database.update_title_ja(article_id, title_ja)
    return {"id": article_id, "title_ja": title_ja}


@app.post("/api/translate-titles/stream")
async def translate_all_titles_stream():
    articles = await database.list_articles(limit=500)
    def _needs_translation(a: dict) -> bool:
        title = a.get("title", "")
        title_ja = a.get("title_ja", "")
        if not title:
            return False
        if not title_ja:
            return True
        # 元タイトルが英語なのに title_ja も日本語でない場合は再翻訳
        if not summarizer._is_japanese(title) and not summarizer._is_japanese(title_ja):
            return True
        return False

    untranslated = [a for a in articles if _needs_translation(a)]

    async def generate():
        count = 0
        for a in untranslated:
            try:
                title_ja = await summarizer.translate_title(a["title"])
                await database.update_title_ja(a["id"], title_ja)
                count += 1
                yield f"data: {json.dumps({'id': a['id'], 'title_ja': title_ja}, ensure_ascii=False)}\n\n"
            except Exception as e:
                err_msg = str(e)
                yield f"data: {json.dumps({'id': a['id'], 'error': err_msg}, ensure_ascii=False)}\n\n"
                # API残高不足など致命的なエラーは継続不可なので停止
                if "credit" in err_msg.lower() or "balance" in err_msg.lower() or "quota" in err_msg.lower():
                    return
        yield f"data: {json.dumps({'done': True, 'count': count}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream; charset=utf-8")


@app.post("/api/digest/stream")
async def digest_stream():
    """今日の記事タイトルからダイジェストをSSEで生成する。"""
    from datetime import date
    today = date.today().isoformat()
    articles = await database.list_articles(limit=200)
    # 今日 or 直近の記事タイトルを収集（翻訳済み優先）
    titles = [
        a.get("title_ja") or a.get("title", "")
        for a in articles
        if (a.get("published_at") or "")[:10] == today or (a.get("fetched_at") or "")[:10] == today
    ]
    if not titles:
        # 今日の記事がなければ最新30件を使う
        titles = [a.get("title_ja") or a.get("title", "") for a in articles[:30]]

    collected: list[str] = []

    async def generate():
        try:
            async for token in summarizer.stream_digest(titles):
                collected.append(token)
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'count': len(titles)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream; charset=utf-8")


@app.delete("/api/articles/{article_id}", response_model=DeleteResponse)
async def delete_article(article_id: int):
    deleted = await database.delete_article(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="記事が見つかりません")
    return DeleteResponse(deleted=True)


# ── RSS Source Management ─────────────────────────────────────────────────

@app.get("/api/sources", response_model=list[RssSourceOut])
async def get_sources():
    return await database.get_rss_sources()


@app.post("/api/sources", response_model=RssSourceOut)
async def add_source(body: AddSourceRequest):
    result = await database.add_rss_source(body.name, body.url)
    if result is None:
        raise HTTPException(status_code=409, detail="このURLは既に登録されています")
    return result


@app.delete("/api/sources/{source_id}", response_model=DeleteResponse)
async def delete_source(source_id: int):
    deleted = await database.delete_rss_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ソースが見つかりません")
    return DeleteResponse(deleted=True)


@app.patch("/api/sources/{source_id}/toggle", response_model=RssSourceOut)
async def toggle_source(source_id: int):
    result = await database.toggle_rss_source(source_id)
    if result is None:
        raise HTTPException(status_code=404, detail="ソースが見つかりません")
    return result
