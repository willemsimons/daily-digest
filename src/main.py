"""Daily Digest — orchestration entrypoint.

Run: python -m src.main            (send it)
     python -m src.main --dry-run  (build + write archive, don't email)
"""
from __future__ import annotations

import os
import sys

import yaml

from src import fetch_feeds, curate, render, send, state, feedback, taste


def load_config() -> dict:
    here = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(here, "config.yaml")) as f:
        return yaml.safe_load(f)


def collect_urls(digest: dict) -> list[str]:
    return [
        it.get("url")
        for sec in digest.get("sections", [])
        for it in sec.get("items", [])
        if it.get("url")
    ]


def main(dry_run: bool = False) -> None:
    cfg = load_config()

    print("· reading feedback")
    notes = feedback.fetch_feedback()
    taste_profile = taste.update_taste(cfg, notes)

    print("· fetching feeds")
    candidates = fetch_feeds.fetch_feeds(cfg["feeds"], cfg.get("lookback_hours", 48))

    seen = state.load_seen()
    candidates = state.drop_seen(candidates, seen)
    print(f"· {len(candidates)} candidates after dedup")

    print("· curating")
    digest = curate.curate(cfg, candidates, taste_profile)

    n = sum(len(s.get("items", [])) for s in digest.get("sections", []))
    print(f"· curated {n} items, {len(digest.get('facts', []))} facts")

    page = render.render_page(digest)
    slug = state.publish(page)
    base = os.environ.get("SITE_BASE_URL", "").rstrip("/")
    page_url = f"{base}/{slug}.html" if base else f"{slug}.html"
    print(f"· published -> docs/{slug}.html")

    if dry_run:
        print("· dry run — not sending")
    else:
        send.send(render.render_email(digest, page_url))

    seen.update(collect_urls(digest))
    state.save_seen(seen)
    print("· done")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
