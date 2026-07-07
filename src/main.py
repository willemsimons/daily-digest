"""Daily Digest — orchestration entrypoint.

Run: python -m src.main            (send it)
     python -m src.main --dry-run  (build + write archive, don't email)
"""
from __future__ import annotations

import os
import sys

import yaml

from src import fetch_feeds, fetch_links, fetch_youtube, scout, curate, picks, render, send, state, feedback, taste


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
    ] + [f.get("url") for f in digest.get("facts", []) if f.get("url")]


def drop_repeats(digest: dict, seen: set) -> dict:
    """Hard backstop: the model is told not to repeat already-covered URLs,
    but web search can surface the same link days apart regardless — never
    trust that instruction alone. Strip anything already in `seen` here,
    in code, after the fact."""
    dropped = 0
    new_sections = []
    for sec in digest.get("sections", []):
        items = [it for it in sec.get("items", []) if it.get("url") not in seen]
        dropped += len(sec.get("items", [])) - len(items)
        if items:  # drop the section entirely if everything in it was a repeat
            new_sections.append({**sec, "items": items})
    digest["sections"] = new_sections

    facts = [f for f in digest.get("facts", []) if f.get("url") not in seen]
    dropped += len(digest.get("facts", [])) - len(facts)
    digest["facts"] = facts

    if dropped:
        print(f"  ! dropped {dropped} repeat item(s) already covered in a past edition")
    return digest


def main(dry_run: bool = False, supplemental: bool = False) -> None:
    cfg = load_config()

    print("· reading feedback")
    notes = feedback.fetch_feedback()
    taste_profile = taste.update_taste(cfg, notes)

    trial_sources = []
    if not supplemental:  # scout only runs on the normal daily cadence
        trial_sources = scout.run_scout(cfg, taste_profile)
        if trial_sources:
            cfg = load_config()  # reload: scout may have added trial feeds

    print("· fetching feeds")
    feeds = dict(cfg["feeds"])
    if cfg.get("experts"):
        feeds["experts"] = cfg["experts"]
    feed_items = fetch_feeds.fetch_feeds(feeds, cfg.get("lookback_hours", 48))
    mined = fetch_links.mine_links(cfg)
    videos = fetch_youtube.fetch_youtube(cfg.get("youtube_channels") or {},
                                         cfg.get("lookback_hours", 48))
    candidates = feed_items + mined + videos
    diag = {"feeds": len(feed_items), "mined": len(mined), "videos": len(videos),
            "video_titles": [v["title"] for v in videos], "supplemental": supplemental}

    seen = state.load_seen()
    candidates = state.drop_seen(candidates, seen)
    print(f"· {len(candidates)} candidates after dedup")

    print("· curating")
    digest = curate.curate(cfg, candidates, taste_profile, already_covered=list(seen))
    digest = drop_repeats(digest, seen)

    if not supplemental:  # taste picks + events run once a day, not on supplements
        extra = picks.get_picks(cfg, taste_profile)
        digest["art_picks"] = extra.get("art_picks", [])
        digest["events"] = extra.get("events", [])
    n = sum(len(s.get("items", [])) for s in digest.get("sections", []))
    print(f"· curated {n} items, {len(digest.get('facts', []))} facts")
    diag["final_items"] = n
    diag["final_sources"] = sorted({it.get("source","") for s in digest.get("sections", [])
                                    for it in s.get("items", [])})
    diag["had_video"] = any(it.get("thumbnail") for s in digest.get("sections", [])
                            for it in s.get("items", []))
    state.write_diagnostics(diag)
    if not supplemental:
        state.save_last_digest(digest, trial_sources)

    page = render.render_page(digest, trial_sources)
    slug = state.publish(page, suffix="-more" if supplemental else None)
    if not supplemental:
        state.update_manifest(slug)
    base = os.environ.get("SITE_BASE_URL", "").rstrip("/")
    page_url = f"{base}/{slug}.html" if base else f"{slug}.html"
    print(f"· published -> docs/{slug}.html")

    if dry_run:
        print("· dry run — not sending")
    else:
        send.send(render.render_email(digest, page_url, supplemental=supplemental))

    seen.update(collect_urls(digest))
    state.save_seen(seen)
    print("· done")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv, supplemental="--more" in sys.argv)
