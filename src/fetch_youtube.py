"""YouTube via channel RSS — free, no API key.
Every channel exposes https://www.youtube.com/feeds/videos.xml?channel_id=...
Entries include a thumbnail we pass through so the daily page can show it.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta

import feedparser
import requests

UA = "Mozilla/5.0 (compatible; DailyDigest/1.0)"


def fetch_youtube(channels: dict, lookback_hours: int) -> list[dict]:
    if not channels:
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(lookback_hours, 96))
    out: list[dict] = []
    for name, cid in channels.items():
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"  ! youtube failed: {name} ({e})")
            continue
        for e in parsed.entries[:3]:
            t = e.get("published_parsed")
            ts = datetime.fromtimestamp(time.mktime(t), tz=timezone.utc) if t else None
            if ts and ts < cutoff:
                continue
            thumb = ""
            media = e.get("media_thumbnail") or []
            if media:
                thumb = media[0].get("url", "")
            desc = ""
            if e.get("media_statistics"):
                desc = f"{e['media_statistics'].get('views','')} views"
            out.append(
                {"title": e.get("title", ""), "url": e.get("link", ""),
                 "source": f"YouTube — {name}",
                 "summary": (e.get("summary", "") or desc)[:300],
                 "published": ts.isoformat() if ts else None,
                 "thumbnail": thumb, "is_video": True}
            )
    print(f"  fetched {len(out)} recent videos from {len(channels)} channels")
    return out
