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
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://www.reddit.com/r/artificial/.rss",
    "https://www.reddit.com/r/LocalLLaMA/.rss",
    "https://hnrss.org/newest?q=AI+OR+LLM+OR+Claude+OR+ChatGPT&count=20",
    "https://openai.com/blog/rss.xml",
    "https://blog.research.google/feeds/posts/default",
    "https://www.anthropic.com/rss.xml",
    "https://the-decoder.com/feed/",
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
