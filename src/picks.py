"""Two extra picks each day, both driven by fresh web search rather than
the feed pipeline:

  - taste picks: a film/show, a visual-art piece, a song — chosen against
    the reader's interestingness signature, not just topic keywords
  - NYC events: concerts, museum shows, fashion pop-ups in the next ~2 weeks

Kept as its own Anthropic call so a bad day here (e.g. thin event listings)
never blocks the main digest.

Dates are the one place an LLM-with-search will happily hallucinate or return
something stale, so we don't trust prose dates at all: the model must return
a strict YYYY-MM-DD, and we parse + range-check every one in code before it's
allowed anywhere near the page. Anything that fails is dropped, not guessed at.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import anthropic

from src.curate import _extract_json, _call, _anti  # reuse robust JSON + pause_turn logic

SYSTEM = """You find specific, well-matched recommendations for one person.
Precision over breadth: a single perfect match beats three generic ones. Every
recommendation needs a real, verifiable, working URL.

For events specifically: you MUST web search for real, currently-listed events
and report their actual dates. Never estimate, round, or infer a date from
memory — if you cannot find a specific confirmed date for an event, drop it
rather than guess. Dates must be in strict YYYY-MM-DD format. If an event runs
across multiple days (an exhibition, a pop-up), give the start date as
date_start and the last day as date_end. If it's a single-day event, set
date_end equal to date_start. If you can't find enough genuinely good,
date-confirmed matches, return fewer — never pad with filler or stale listings."""

PROMPT = """## Today's date
{today} ({today_readable})

## The reader
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
of each; let quality decide the mix. Classic or contemporary, famous or obscure —
precision to their taste matters more than novelty. For visual art, link to the
museum, gallery, or artist's own page — never an image file directly. For film,
link to Letterboxd or the film's official page. For music, link to the artist's
page or a YouTube upload. (No dates needed here — these are evergreen.)

## Task B — {city} events
Window: {window_start} through {window_end} ONLY. Web search for real,
currently-listed events in {city} happening inside this exact window: concerts,
museum exhibitions (openings or must-see current shows), fashion pop-ups or
design events. Search for "{city} events this week", "{city} events {month_name}",
gallery/venue listing pages, etc. — actually look, don't recall from memory.
Recommend up to {n_events} that match this reader's taste — favor
smaller/niche/design-forward over mainstream/touristy. Every event needs a real
venue, a specific confirmed YYYY-MM-DD date (or start/end pair), and a working
link. Drop anything you can't confirm a real date for.

Return ONLY JSON:
{{"art_picks": [{{"medium": "film|art|music", "title": "string",
  "creator": "string", "why": "1-2 sentences, specific, tied to their taste",
  "url": "string"}}],
 "events": [{{"name": "string", "venue": "string",
  "date_start": "YYYY-MM-DD", "date_end": "YYYY-MM-DD",
  "category": "concert|museum|popup", "why": "one sentence", "url": "string"}}]}}"""


def _parse(d: str) -> date | None:
    try:
        return datetime.strptime((d or "").strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _validate_events(events: list[dict], window_start: date, window_end: date) -> list[dict]:
    """Hard filter: drop anything with an unparseable or out-of-window date.
    Never trust the model's self-report — verify in code."""
    kept, dropped = [], 0
    for e in events:
        start = _parse(e.get("date_start"))
        end = _parse(e.get("date_end")) or start
        if not start or not end or end < start:
            dropped += 1
            continue
        if end < window_start or start > window_end:  # entirely outside window
            dropped += 1
            continue
        e["_start"], e["_end"] = start, end
        kept.append(e)
    if dropped:
        print(f"  ! dropped {dropped} event(s) with missing/invalid/stale dates")
    kept.sort(key=lambda e: e["_start"])
    return kept


def _format_date(e: dict) -> str:
    start, end = e["_start"], e["_end"]
    if start == end:
        return start.strftime("%a, %b ") + str(start.day)
    if start.month == end.month:
        return f"{start.strftime('%b')} {start.day}\u2013{end.day}"
    return f"{start.strftime('%b')} {start.day} \u2013 {end.strftime('%b')} {end.day}"


def get_picks(config: dict, taste: str) -> dict:
    tp, ev = config.get("taste_picks") or {}, config.get("events") or {}
    if not tp.get("enabled", True) and not ev.get("enabled", True):
        return {"art_picks": [], "events": []}

    today = date.today()
    window_end = today + timedelta(days=int(ev.get("lookahead_days", 14)))

    client = anthropic.Anthropic()
    prompt = PROMPT.format(
        today=today.isoformat(),
        today_readable=today.strftime("%A, %B %-d, %Y"),
        persona=config["persona"].strip(),
        interestingness=(config.get("interestingness") or "").strip() or "(none)",
        taste=taste.strip() or "(none yet)",
        anti=_anti(config),
        n_picks=tp.get("count", 3),
        city=ev.get("city", "New York City"),
        window_start=today.isoformat(),
        window_end=window_end.isoformat(),
        month_name=today.strftime("%B"),
        n_events=ev.get("count", 5),
    )
    try:
        resp = _call(client, config, prompt, max_tokens=2500)
        data = _extract_json(resp)
    except Exception as e:
        print(f"  ! taste picks / events failed, skipping ({e})")
        return {"art_picks": [], "events": []}

    picks = data.get("art_picks", []) if tp.get("enabled", True) else []
    events_raw = data.get("events", []) if ev.get("enabled", True) else []
    events = _validate_events(events_raw, today, window_end)
    for e in events:
        e["date"] = _format_date(e)  # human-readable, derived only from validated dates

    print(f"  {len(picks)} taste picks, {len(events)}/{len(events_raw)} events passed date validation")
    return {"art_picks": picks, "events": events}
