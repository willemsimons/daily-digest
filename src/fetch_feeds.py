"""Fetch and normalize RSS/Atom/Reddit feeds into candidate items."""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

import feedparser
import requests

# Reddit and some hosts reject the default urllib UA; use a real one.
UA = "Mozilla/5.0 (compatible; DailyDigest/1.0; +https://github.com/)"


def _fetch_one(url: str, timeout: int = 20):
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except Exception as e:  # a dead feed should never kill the run
        print(f"  ! feed failed: {url} ({e})")
        return None


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None


def _clean_summary(entry) -> str:
    raw = entry.get("summary", "") or ""
    # strip crude HTML without pulling in a parser dependency
    out, depth = [], 0
    for ch in raw:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    text = "".join(out).strip()
    return text[:600]


def fetch_feeds(feeds_by_group: dict, lookback_hours: int) -> list[dict]:
    """Return a flat, de-duplicated list of recent candidate items."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    urls = [u for group in feeds_by_group.values() for u in group]
    seen_urls: set[str] = set()
    items: list[dict] = []

    for url in urls:
        parsed = _fetch_one(url)
        if not parsed:
            continue
        source = parsed.feed.get("title", url)
        for entry in parsed.entries[:15]:
            link = entry.get("link")
            if not link or link in seen_urls:
                continue
            ts = _entry_time(entry)
            if ts and ts < cutoff:
                continue
            seen_urls.add(link)
            items.append(
                {
                    "title": entry.get("title", "(untitled)").strip(),
                    "url": link,
                    "source": source,
                    "summary": _clean_summary(entry),
                    "published": ts.isoformat() if ts else None,
                }
            )
    print(f"  fetched {len(items)} feed candidates from {len(urls)} feeds")
    return items
