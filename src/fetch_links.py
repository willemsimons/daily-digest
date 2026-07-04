"""Citation mining — harvest what smart communities REFERENCE.

The idea: a high-signal comment thread is a curation engine. This module walks
HN front-page threads (Algolia API, free) and top Reddit comment threads, and
extracts the outbound links people cite — often better than the post itself.
Every candidate is annotated with who cited it, so the curator knows why it's here.
"""
from __future__ import annotations

import html
import re
import time

import requests

UA = "Mozilla/5.0 (compatible; DailyDigest/1.0)"
HN_API = "https://hn.algolia.com/api/v1"

# junk we never want from comment links
_SKIP = re.compile(
    r"(imgur|redd\.it|reddit\.com|youtube\.com/redirect|news\.ycombinator|"
    r"twitter\.com|x\.com|t\.co|giphy|tenor|discord|facebook|instagram)",
    re.I,
)
_HREF = re.compile(r'href="([^"]+)"')
_BARE = re.compile(r"https?://[^\s\)\]>\"']+")


def _clean(url: str) -> str | None:
    url = html.unescape(url).rstrip(".,;:!?")
    if not url.startswith("http") or _SKIP.search(url) or len(url) > 300:
        return None
    return url


def _get(url: str, **kw):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15, **kw)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ! mine failed: {url[:60]} ({e})")
        return None


# ── Hacker News ───────────────────────────────────────────────────────
def _mine_hn(min_points: int, n_stories: int) -> list[dict]:
    out: list[dict] = []
    data = _get(f"{HN_API}/search", params={"tags": "front_page", "hitsPerPage": 30})
    if not data:
        return out
    stories = [h for h in data.get("hits", []) if (h.get("points") or 0) >= min_points]

    # the stories themselves are candidates (fetch_feeds may already have some;
    # dedup upstream handles overlap)
    for h in stories:
        if h.get("url"):
            out.append(
                {"title": h["title"], "url": h["url"],
                 "source": f"Hacker News ({h.get('points',0)} pts)",
                 "summary": "", "published": None}
            )

    # now the real move: walk the comment trees of the top threads for citations
    for h in stories[:n_stories]:
        item = _get(f"{HN_API}/items/{h['objectID']}")
        if not item:
            continue
        stack, found = list(item.get("children", [])), 0
        while stack and found < 5:
            c = stack.pop(0)
            stack.extend(c.get("children", []))
            for m in _HREF.finditer(c.get("text") or ""):
                url = _clean(m.group(1))
                if url:
                    out.append(
                        {"title": f"(cited in HN thread: {h['title'][:70]})",
                         "url": url,
                         "source": "HN comment citation",
                         "summary": "Linked by a commenter in a high-signal thread — "
                                    "often the deeper source behind the story.",
                         "published": None}
                    )
                    found += 1
        time.sleep(0.3)
    return out


# ── Reddit comment threads ───────────────────────────────────────────
def _mine_reddit(subs: list[str]) -> list[dict]:
    out: list[dict] = []
    for sub in subs:
        data = _get(f"https://www.reddit.com/r/{sub}/top/.json",
                    params={"t": "day", "limit": 3})
        if not data:
            continue
        posts = [p["data"] for p in data.get("data", {}).get("children", [])]
        for p in posts[:2]:
            cdata = _get(f"https://www.reddit.com{p['permalink']}.json",
                         params={"limit": 40, "depth": 2})
            if not cdata or len(cdata) < 2:
                continue
            found = 0
            comments = cdata[1].get("data", {}).get("children", [])
            for c in comments:
                body = c.get("data", {}).get("body", "") or ""
                score = c.get("data", {}).get("score", 0)
                if score < 5:
                    continue
                for m in _BARE.finditer(body):
                    url = _clean(m.group(0))
                    if url and found < 3:
                        out.append(
                            {"title": f"(cited in r/{sub}: {p.get('title','')[:70]})",
                             "url": url,
                             "source": f"r/{sub} comment citation ({score} pts)",
                             "summary": "Referenced by an upvoted commenter in a niche "
                                        "community discussion.",
                             "published": None}
                        )
                        found += 1
            time.sleep(0.5)
    return out


def mine_links(cfg: dict) -> list[dict]:
    lm = cfg.get("link_mining") or {}
    if not lm.get("enabled"):
        return []
    items = _mine_hn(lm.get("hn_min_points", 80), lm.get("hn_stories_to_mine", 6))
    items += _mine_reddit(lm.get("reddit_comment_subs", []))
    # dedup within this batch
    seen, out = set(), []
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"])
            out.append(it)
    print(f"  mined {len(out)} cited links from communities")
    return out
