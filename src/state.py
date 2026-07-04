"""Persistence: remember what we've already sent, and archive each day."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state")
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
SEEN_PATH = os.path.join(STATE_DIR, "seen.json")

# keep the seen-list bounded so it never balloons
MAX_SEEN = 4000


def load_seen() -> set[str]:
    try:
        with open(SEEN_PATH) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen: set[str]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    trimmed = list(seen)[-MAX_SEEN:]
    with open(SEEN_PATH, "w") as f:
        json.dump(trimmed, f, indent=0)


def drop_seen(items: list[dict], seen: set[str]) -> list[dict]:
    return [it for it in items if it.get("url") not in seen]


def publish(html: str, suffix: str | None = None) -> str:
    """Write today's page into docs/ (served by GitHub Pages).
    docs/YYYY-MM-DD.html is the permanent URL; docs/index.html is always latest.
    A suffix (e.g. '-more') publishes a distinct dated page without touching
    index.html, so a supplemental edition doesn't overwrite the day's main one.
    Returns the day slug, e.g. '2026-07-01' or '2026-07-01-more'."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = f"{day}{suffix}" if suffix else day
    names = [f"{slug}.html"] if suffix else [f"{slug}.html", "index.html"]
    for name in names:
        with open(os.path.join(DOCS_DIR, name), "w") as f:
            f.write(html)
    return slug


def save_last_digest(digest: dict, trial_sources: list | None = None) -> None:
    """Persist the raw curated digest so a pure styling change can be
    re-rendered later without paying for a full re-curation."""
    import json
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "last_digest.json"), "w") as f:
        json.dump({"digest": digest, "trial_sources": trial_sources or []}, f, indent=2)


def load_last_digest() -> tuple[dict, list] | None:
    import json
    try:
        with open(os.path.join(STATE_DIR, "last_digest.json")) as f:
            d = json.load(f)
        return d["digest"], d.get("trial_sources", [])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def write_diagnostics(diag: dict) -> None:
    """Write a per-run diagnostics file into docs/ so we can inspect source
    counts without needing the GitHub Actions logs."""
    import json
    from datetime import datetime, timezone
    diag["run_at"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "diagnostics.json"), "w") as f:
        json.dump(diag, f, indent=2)
