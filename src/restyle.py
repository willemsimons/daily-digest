"""Re-render the most recently saved digest with whatever styling is currently
in render.py — no API calls, no re-curation. For pure visual/CSS iteration.

Run: python -m src.restyle
"""
from __future__ import annotations

from src import render, state


def main() -> None:
    loaded = state.load_last_digest()
    if not loaded:
        print("no saved digest to restyle — run the full pipeline at least once first")
        return
    digest, trial_sources = loaded
    page = render.render_page(digest, trial_sources)
    slug = state.publish(page)
    print(f"restyled -> docs/{slug}.html and docs/index.html")


if __name__ == "__main__":
    main()
