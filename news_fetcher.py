import feedparser
import httpx
import ipaddress
import socket
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from typing import Optional
import asyncio

_ALLOWED_SCHEMES = {"http", "https"}
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_blocked_address(host: str) -> bool:
    """ホストが内部/プライベートアドレスに解決される場合 True を返す。"""
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        pass  # ホスト名 — DNS 解決して確認
    try:
        infos = socket.getaddrinfo(host, None)
        for _, _, _, _, sockaddr in infos:
            addr = ipaddress.ip_address(sockaddr[0])
            if any(addr in net for net in _BLOCKED_NETWORKS):
                return True
    except OSError:
        return True  # 解決不可能なホストは拒否
    return False


def validate_url(url: str) -> None:
    """URL のスキームとホストを検証する。問題があれば ValueError を送出。"""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"許可されていないスキームです: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("ホスト名が指定されていません")
    if _is_blocked_address(host):
        raise ValueError("プライベート/内部アドレスへのアクセスは許可されていません")

RSS_FEEDS = [
    # ── Layer 1: 専門メディア（直接RSS） ──────────────────────────────────────
    "https://www.energy-storage.news/feed/",
    "https://www.pv-magazine.com/feed/",
    "https://www.pvtech.org/feed/",
    "https://www.utilitydive.com/feeds/news/",
    "https://www.canarymedia.com/feed",
    "https://reneweconomy.com.au/feed/",
    "https://cleantechnica.com/feed/",
    "https://www.renewableenergyworld.com/feed/",
    # ── Layer 2: Google News RSS - 日本語キーワード ───────────────────────────
    # 系統用蓄電池
    "https://news.google.com/rss/search?q=%E7%B3%BB%E7%B5%B1%E7%94%A8%E8%93%84%E9%9B%BB%E6%B1%A0&hl=ja&gl=JP&ceid=JP:ja",
    # 需給調整市場
    "https://news.google.com/rss/search?q=%E9%9C%80%E7%B5%A6%E8%AA%BF%E6%95%B4%E5%B8%82%E5%A0%B4&hl=ja&gl=JP&ceid=JP:ja",
    # FIP 蓄電池
    "https://news.google.com/rss/search?q=FIP+%E8%93%84%E9%9B%BB%E6%B1%A0&hl=ja&gl=JP&ceid=JP:ja",
    # 出力制御 蓄電池
    "https://news.google.com/rss/search?q=%E5%87%BA%E5%8A%9B%E5%88%B6%E5%BE%A1+%E8%93%84%E9%9B%BB%E6%B1%A0&hl=ja&gl=JP&ceid=JP:ja",
    # 系統安定化 蓄電池
    "https://news.google.com/rss/search?q=%E7%B3%BB%E7%B5%B1%E5%AE%89%E5%AE%9A%E5%8C%96+%E8%93%84%E9%9B%BB%E6%B1%A0&hl=ja&gl=JP&ceid=JP:ja",
    # ── Layer 2: Google News RSS - 英語キーワード ────────────────────────────
    # "battery energy storage" grid
    "https://news.google.com/rss/search?q=%22battery+energy+storage%22+grid&hl=en&gl=US&ceid=US:en",
    # "grid-scale battery"
    "https://news.google.com/rss/search?q=%22grid-scale+battery%22&hl=en&gl=US&ceid=US:en",
    # "ancillary services" battery
    "https://news.google.com/rss/search?q=%22ancillary+services%22+battery&hl=en&gl=US&ceid=US:en",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_BODY_CHARS = 5000


def _parse_feed_date(entry) -> Optional[str]:
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return None


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:MAX_BODY_CHARS]


async def fetch_rss_feeds(urls: list[str] = None) -> list[dict]:
    feed_urls = urls if urls is not None else RSS_FEEDS
    results = await asyncio.gather(
        *[_fetch_single_feed(url) for url in feed_urls],
        return_exceptions=True,
    )
    articles = []
    for batch in results:
        if isinstance(batch, Exception):
            continue
        articles.extend(batch)
    return articles


async def _fetch_single_feed(feed_url: str) -> list[dict]:
    articles = []
    try:
        validate_url(feed_url)
        async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=False) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"[WARN] RSS fetch failed for {feed_url}: {e}")
        return []

    source_host = urlparse(feed_url).hostname or feed_url

    for entry in feed.entries[:20]:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not url or not title:
            continue

        body_html = ""
        if hasattr(entry, "content") and entry.content:
            body_html = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            body_html = entry.summary or ""

        body_text = _extract_text(body_html) if body_html else None

        articles.append({
            "url": url,
            "title": title.strip(),
            "source": source_host,
            "published_at": _parse_feed_date(entry),
            "body_text": body_text,
        })

    return articles


async def scrape_url(url: str) -> dict:
    validate_url(url)
    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, follow_redirects=False) as client:
        resp = await client.get(url)
        # リダイレクト先も検証
        if resp.is_redirect:
            location = resp.headers.get("location", "")
            validate_url(location)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title:
        title = soup.title.get_text(strip=True)
    title = title or url

    # Published date
    published_at = None
    for meta_name in ("article:published_time", "datePublished", "pubdate"):
        tag = (soup.find("meta", property=meta_name)
               or soup.find("meta", attrs={"name": meta_name}))
        if tag and tag.get("content"):
            try:
                published_at = datetime.fromisoformat(tag["content"]).isoformat()
                break
            except ValueError:
                pass

    # Body text
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    article_el = soup.find("article") or soup.find("main") or soup.body
    body_text = None
    if article_el:
        body_text = " ".join(article_el.get_text(separator=" ").split())[:MAX_BODY_CHARS]
        if not body_text:
            body_text = None

    source_host = urlparse(url).hostname or "manual"

    return {
        "url": url,
        "title": title,
        "source": source_host,
        "published_at": published_at,
        "body_text": body_text,
    }
