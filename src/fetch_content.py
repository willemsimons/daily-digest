"""Fetch shortlisted articles and extract readable text, so the final
curation judges actual content instead of titles. Fails soft per-URL."""
from __future__ import annotations

import re

import requests

try:
    import trafilatura
except ImportError:  # extraction still works, just cruder
    trafilatura = None

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _strip_tags(html: str) -> str:
    html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ",
                  html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def fetch_excerpt(url: str, max_chars: int) -> str:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=12)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        return f"(could not fetch: {e})"
    text = ""
    if trafilatura:
        try:
            text = trafilatura.extract(html, include_comments=False) or ""
        except Exception:
            text = ""
    if not text:
        text = _strip_tags(html)
    return text[:max_chars]


def add_excerpts(items: list[dict], max_chars: int) -> list[dict]:
    for it in items:
        if it.get("is_video"):
            it["excerpt"] = "(video — judge by title/channel)"
            continue
        it["excerpt"] = fetch_excerpt(it.get("url", ""), max_chars)
    ok = sum(1 for i in items if not str(i.get("excerpt", "")).startswith("(could not"))
    print(f"  fetched {ok}/{len(items)} article excerpts")
    return items
