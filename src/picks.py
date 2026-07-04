"""Two extra picks each day, both driven by fresh web search rather than
the feed pipeline:

  - taste picks: a film/show, a visual-art piece, a song — chosen against
    the reader's interestingness signature, not just topic keywords
  - NYC events: concerts, museum shows, fashion pop-ups in the next ~2 weeks

Kept as its own Anthropic call so a bad day here (e.g. thin event listings)
never blocks the main digest.
"""
from __future__ import annotations

import json

import anthropic

from src.curate import _extract_json, _call  # reuse the robust JSON + pause_turn logic

SYSTEM = """You find specific, well-matched recommendations for one person.
Precision over breadth: a single perfect match beats three generic ones. Every
recommendation needs a real, verifiable, working URL. If you can't find enough
genuinely good matches, return fewer — never pad with filler."""

PROMPT = """## The reader
{persona}

## Interestingness signature (what actually hooks them, beyond topic)
{interestingness}

## Learned taste
{taste}

## Anti-interests — avoid matching the vibe of these
{anti}

## Task A — Taste picks ({n_picks} total)
Recommend specific pieces of art this reader would genuinely love, mixing across
mediums (film/show, visual art/painting/exhibition, music) — not necessarily one
of each; let quality decide the mix. These can be classic or contemporary,
famous or obscure — precision to their taste matters more than novelty. For
visual art, link to the museum, gallery, or artist's own page — never an image
file directly. For film, link to Letterboxd or the film's official page. For
music, link to the artist's page or a YouTube upload.

## Task B — {city} events (next {lookahead_days} days)
Web search for real, currently-listed events in {city}: concerts, museum
exhibitions (openings or must-see current shows), fashion pop-ups or design
events. Recommend up to {n_events} that match this reader's taste — favor
smaller/niche/design-forward over mainstream/touristy. Each needs a real venue,
a real date or date range, and a working link (venue page or ticket page).
Today's date context: search for "this week" / "this month" as needed.

Return ONLY JSON:
{{"art_picks": [{{"medium": "film|art|music", "title": "string",
  "creator": "string", "why": "1-2 sentences, specific, tied to their taste",
  "url": "string"}}],
 "events": [{{"name": "string", "venue": "string", "date": "string (human readable)",
  "category": "concert|museum|popup", "why": "one sentence", "url": "string"}}]}}"""


def get_picks(config: dict, taste: str) -> dict:
    from src.curate import _anti  # local import to avoid a cycle at module load

    tp, ev = config.get("taste_picks") or {}, config.get("events") or {}
    if not tp.get("enabled", True) and not ev.get("enabled", True):
        return {"art_picks": [], "events": []}

    client = anthropic.Anthropic()
    prompt = PROMPT.format(
        persona=config["persona"].strip(),
        interestingness=(config.get("interestingness") or "").strip() or "(none)",
        taste=taste.strip() or "(none yet)",
        anti=_anti(config),
        n_picks=tp.get("count", 3),
        city=ev.get("city", "New York City"),
        lookahead_days=ev.get("lookahead_days", 14),
        n_events=ev.get("count", 5),
    )
    try:
        resp = _call(client, config, prompt, max_tokens=2500)
        data = _extract_json(resp)
    except Exception as e:
        print(f"  ! taste picks / events failed, skipping ({e})")
        return {"art_picks": [], "events": []}

    picks = data.get("art_picks", []) if tp.get("enabled", True) else []
    events = data.get("events", []) if ev.get("enabled", True) else []
    print(f"  {len(picks)} taste picks, {len(events)} events")
    return {"art_picks": picks, "events": events}
