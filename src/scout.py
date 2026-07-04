"""Source scout — the system learns WHERE to look, not just what to pick.

Weekly, Claude reviews your interests + learned taste, then web-searches for
new sources (niche communities, individual experts' blogs/Substacks, YouTube
channels) you aren't tapping yet. The best few get appended to a 'trial'
feed list in config.yaml — the workflow's commit step persists it — and the
digest notes what's on trial so your thumbs can keep or kill them.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import anthropic
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

_SYSTEM = """You are a source scout for a private daily briefing. Your job is to
find NEW information streams — not articles, but ongoing sources: niche blogs,
individual experts' Substacks, community forums with RSS, YouTube channels.
Prefer individual humans with taste over institutions. Every source must have a
working RSS/Atom feed URL (Substack = /feed, YouTube = channel RSS, subreddit =
/.rss). Never propose a source already in use. Quality over quantity — if you
can't find genuinely great new sources, return fewer."""

_PROMPT = """## Reader's interests
{interests}

## Learned taste
{taste}

## Sources ALREADY in use (do not repeat)
{existing}

Search the web to find up to {n} NEW high-quality sources this reader isn't
tapping yet. Look for: writers other good writers cite, niche communities with
strong norms, channel recommendations in enthusiast threads.

Return ONLY JSON: {{"sources": [{{"name": "string", "feed_url": "string",
"why": "one sentence on why this matches their taste"}}]}}"""


def _should_run(cfg: dict) -> bool:
    sc = cfg.get("scout") or {}
    if not sc.get("enabled"):
        return False
    if os.environ.get("FORCE_SCOUT"):
        return True
    today = datetime.now(timezone.utc).strftime("%A")
    return today == sc.get("day", "Sunday")


def _existing_urls(cfg: dict) -> list[str]:
    urls = [u for g in (cfg.get("feeds") or {}).values() for u in g]
    urls += cfg.get("experts") or []
    urls += list((cfg.get("youtube_channels") or {}).values())
    return urls


def run_scout(cfg: dict, taste: str) -> list[dict]:
    """Returns list of newly added trial sources (possibly empty)."""
    if not _should_run(cfg):
        return []
    print("· scouting for new sources")
    client = anthropic.Anthropic()
    n = int((cfg.get("scout") or {}).get("max_new_sources", 3))
    prompt = _PROMPT.format(
        interests="\n".join(f"- {i}" for i in cfg["interests"]),
        taste=taste.strip() or "(none yet)",
        existing="\n".join(f"- {u}" for u in _existing_urls(cfg)),
        n=n,
    )
    try:
        resp = client.messages.create(
            model=cfg.get("model", "claude-sonnet-4-6"),
            max_tokens=1500,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        )
        texts = [b.text for b in resp.content if b.type == "text" and b.text.strip()]
        raw = texts[-1].strip() if texts else "{}"
        start, end = raw.find("{"), raw.rfind("}")
        found = json.loads(raw[start : end + 1]).get("sources", [])[:n]
    except Exception as e:
        print(f"  ! scout failed, skipping ({e})")
        return []

    if not found:
        print("  scout found nothing worth adding")
        return []

    # append to a 'trial' group in config.yaml; workflow commit persists it
    with open(CONFIG_PATH) as f:
        live = yaml.safe_load(f)
    trial = live.setdefault("feeds", {}).setdefault("trial", [])
    added = []
    for s in found:
        u = s.get("feed_url")
        if u and u not in trial and u not in _existing_urls(live):
            trial.append(u)
            added.append(s)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(live, f, sort_keys=False, allow_unicode=True, width=100)
    for s in added:
        print(f"  + trial source: {s['name']} — {s['feed_url']}")
    return added
