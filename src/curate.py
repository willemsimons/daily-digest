"""Two-stage curation.

Stage 1 (triage): Claude + web search scans ~200 title-level candidates,
runs the day's searches (including a rotating exploration topic), and returns
a shortlist of ~18 URLs — including 2-3 wildcard candidates outside the
reader's stated interests, chosen for their interestingness signature.

Between stages we FETCH the shortlisted articles (fetch_content.py).

Stage 2 (deep judge): Claude reads actual excerpts and builds the final
digest — sections, blurbs written to be retellable, facts of the day, an
occasional make-something, and a wildcard the reader didn't know to ask for.
"""
from __future__ import annotations

import json
import random

import anthropic

from src import fetch_content

SYSTEM = """You are the editor of a private daily briefing for one person.
Your job is taste: surface the few things genuinely worth their attention today
and skip everything else. You are ruthless about signal. No listicles, no hype,
no engagement-bait. If a day is thin, send fewer items — never pad. Write like
a sharp friend who read everything so they didn't have to.

For health topics (peptides, stem cells, diabetes, longevity): prefer primary
research and credible reporting, present findings as information rather than
protocols or dosing advice, and note when something is early or preliminary."""

TRIAGE_PROMPT = """## The reader
{persona}

## Their interests
{interests}

## Their interestingness signature (qualities that hook them, beyond topic)
{interestingness}

## Learned taste (from their feedback — weight heavily)
{taste}

## Today's exploration topic (rotates daily — hunt here too)
{explore}

## Candidates gathered this morning (feeds, community citations, videos)
{candidates}

## Also run web searches for these
{queries}

## Task
Triage. Return the {shortlist} MOST promising URLs for a deep-read pass:
- Mostly from candidates + your searches on their interests.
- Include 1-2 from the exploration topic if you find something great.
- Include 2-3 WILDCARDS: pieces OUTSIDE their stated interests that strongly
  match the interestingness signature. Surprise them well.
- Keep at most 2 [VIDEO] items, only if genuinely worth watch time.
- Prefer primary/deep sources over news-about-news. Citation candidates
  (linked by commenters) are often the gold — favor them when strong.

Return ONLY JSON:
{{"shortlist": [{{"title": "string", "url": "string", "source": "string",
  "is_video": false, "thumbnail": "url or omit",
  "why": "one line on why this made the cut",
  "wildcard": true/false}}]}}"""

DEEP_PROMPT = """## The reader
{persona}

## Learned taste
{taste}

## Shortlisted pieces — with ACTUAL EXCERPTS you fetched and can now judge
{excerpts}

## Task
You've now READ these. Build today's briefing from the genuinely best ~{n}
(fewer if the day is thin — excerpts reveal duds; cut anything that under-delivers
on its title, and say nothing about it).
- Group under 1-4 short natural section headings shaped by what you chose.
- Include the best wildcard as its own item — place it in a fitting section or
  a section of its own (e.g. "Off the map"). Never label it "wildcard" in text;
  let it simply be surprising.
- Each blurb: 2-3 sentences that educate (the actual substance — you read it,
  so cite the specific detail, number, or turn that makes it land) AND make it
  retellable at dinner tonight.
- "facts": 3-5 genuinely surprising, verifiable facts of the day drawn from
  what you read — each one sentence, each a "wait, really?", each with URL.
- One intro line (<= 18 words) framing the day.
- Every item and fact MUST use a URL from the shortlist.
{make_clause}

Return ONLY JSON:
{{"intro": "string",
  "sections": [{{"heading": "string", "items": [
    {{"title": "string", "source": "string", "url": "string", "blurb": "string",
      "tags": ["1-3 short lowercase topic tags"],
      "thumbnail": "url string, ONLY for video items, else omit"}}]}}],
  "facts": [{{"fact": "one surprising, verifiable sentence", "url": "string"}}],
  "make_something": null OR {{"prompt": "string (2-4 sentences, tied to today's themes)"}}}}"""


def _make_clause(allow: bool) -> str:
    if allow:
        return ("- Today you MAY (not must) end with a 'make something' prompt: a small, "
                "concrete creative or physical build tied to a theme that came up today. "
                "Only include it if it's actually good. Otherwise set make_something to null.")
    return "- Do NOT include a 'make something' prompt today. Set make_something to null."


def _extract_json(resp) -> dict:
    # With web search enabled, the response interleaves commentary text blocks
    # with search results; the JSON we want is normally in the LAST text block.
    texts = [b.text for b in resp.content if b.type == "text" and b.text.strip()]
    candidates = [t.strip() for t in reversed(texts)]
    if len(texts) > 1:
        candidates.append("\n".join(texts).strip())
    for text in candidates:
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip("` \n")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
    raise ValueError(
        "model response contained no parseable JSON "
        f"(stop_reason={resp.stop_reason}); text blocks were:\n"
        + "\n---\n".join(texts)[:2000]
    )


def _cand_lines(candidates: list[dict]) -> str:
    return "\n".join(
        f"- {'[VIDEO] ' if c.get('is_video') else ''}[{c['source']}] {c['title']} — {c['url']}"
        + (f"\n    thumbnail: {c['thumbnail']}" if c.get("thumbnail") else "")
        + (f"\n    {c.get('summary', '')[:200]}" if c.get("summary") else "")
        for c in candidates[:200]
    ) or "(no feed candidates today — rely on search)"


def _call(client, config, prompt, max_tokens, use_search=True):
    kwargs = dict(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    if use_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                            "max_uses": 8}]
    resp = client.messages.create(**kwargs)
    # pause_turn: the model paused mid-search; continue the turn
    while getattr(resp, "stop_reason", None) == "pause_turn":
        kwargs["messages"] = kwargs["messages"] + [
            {"role": "assistant", "content": resp.content}]
        resp = client.messages.create(**kwargs)
    return resp


def curate(config: dict, candidates: list[dict], taste: str = "") -> dict:
    client = anthropic.Anthropic()
    dr = config.get("deep_read") or {}
    ser = config.get("serendipity") or {}
    explore = random.choice(ser.get("explore_topics") or ["(none)"])
    print(f"  exploration topic today: {explore}")

    # ── stage 1: triage ──
    triage_prompt = TRIAGE_PROMPT.format(
        persona=config["persona"].strip(),
        interests="\n".join(f"- {i}" for i in config["interests"]),
        interestingness=(config.get("interestingness") or "").strip() or "(none)",
        taste=taste.strip() or "(none yet)",
        explore=explore,
        candidates=_cand_lines(candidates),
        queries="\n".join(f"- {q}" for q in config.get("search_queries", [])),
        shortlist=dr.get("shortlist_size", 18),
    )
    resp = _call(client, config, triage_prompt, max_tokens=4000)
    shortlist = _extract_json(resp).get("shortlist", [])
    print(f"  triage shortlisted {len(shortlist)} "
          f"({sum(1 for s in shortlist if s.get('wildcard'))} wildcards)")

    if not shortlist:
        raise ValueError("triage returned an empty shortlist")

    # ── fetch actual content ──
    if dr.get("enabled", True):
        shortlist = fetch_content.add_excerpts(
            shortlist, dr.get("excerpt_chars", 1600))

    # ── stage 2: deep judge ──
    allow_make = random.random() < float(config.get("make_something_chance", 0.35))
    excerpt_block = "\n\n".join(
        f"### {'[VIDEO] ' if s.get('is_video') else ''}"
        f"{'[WILDCARD] ' if s.get('wildcard') else ''}{s.get('title','')}\n"
        f"URL: {s.get('url','')}\nSource: {s.get('source','')}\n"
        f"Why shortlisted: {s.get('why','')}\n"
        + (f"Thumbnail: {s['thumbnail']}\n" if s.get("thumbnail") else "")
        + f"Excerpt: {s.get('excerpt','')}"
        for s in shortlist
    )
    deep_prompt = DEEP_PROMPT.format(
        persona=config["persona"].strip(),
        taste=taste.strip() or "(none yet)",
        excerpts=excerpt_block,
        n=config.get("target_item_count", 7),
        make_clause=_make_clause(allow_make),
    )
    resp = _call(client, config, deep_prompt, max_tokens=5000, use_search=False)
    return _extract_json(resp)
