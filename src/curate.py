"""The brain: one Anthropic call that searches, selects, and writes the digest.

Given the day's feed candidates + your persona, the model:
  - runs the configured web searches for timely / research topics
  - merges those with the feed candidates
  - picks the best ~N, adapting the structure to what the day actually offered
  - writes a short, non-hypey blurb for each
  - occasionally appends a "make something" prompt
Returns a structured dict that render.py turns into an email.
"""
from __future__ import annotations

import json
import random

import anthropic

SYSTEM = """You are the editor of a private daily briefing for one person.
Your job is taste: surface the few things genuinely worth their attention today
and skip everything else. You are ruthless about signal. No listicles, no hype,
no engagement-bait, no "you won't believe." If a day is thin, send fewer items —
never pad. Write like a sharp friend who read everything so they didn't have to.

For health topics (peptides, stem cells, diabetes, longevity): prefer primary
research and credible reporting, present findings as information rather than
protocols or dosing advice, and note when something is early or preliminary."""

PROMPT = """Here is today's raw material and who it's for.

## The reader
{persona}

## Their interests
{interests}

## Learned preferences (from their own feedback — weight these heavily)
{taste}

## Feed candidates (already pulled from RSS/Reddit today)
{candidates}

## Also search the web for these, then merge the best in
{queries}

## Your task
Build today's briefing.
- Select the ~{n} most worthwhile items overall (fewer if the day is thin).
- Let the DAY decide the shape. Some days lead with one big current event;
  some days are a quiet rabbit-hole of essays. Group items under short,
  natural section headings that fit what you actually chose. 1-4 sections.
- For each item write a 2-3 sentence blurb that does two jobs: educate (the
  actual substance — what happened, what was found, why it matters) AND make it
  retellable — the reader should be able to bring it up at dinner tonight and
  sound interesting. Concrete and specific; give the detail that makes it stick.
- Also write "facts": 3-5 genuinely surprising, verifiable facts of the day —
  drawn from today's items or your searches. Each one sentence, each the kind of
  thing that makes someone say "wait, really?". Include a source URL for each.
- Write one short intro line (<= 18 words) framing the day.
- Candidates marked [VIDEO] are YouTube videos: include at most 1-2, and only
  when genuinely worth the watch time; copy their thumbnail URL through.
- Candidates marked as "citations" were LINKED BY commenters in smart communities
  — these are often the deepest sources. When you pick one, give it a real title
  (fetch/infer from the URL and context) instead of the placeholder.
- Every item and fact MUST have a real, working URL (from the candidates or your search).
{make_clause}

## Output
Return ONLY valid JSON, no prose, no markdown fences:
{{
  "intro": "string",
  "sections": [
    {{"heading": "string",
      "items": [
        {{"title": "string", "source": "string", "url": "string", "blurb": "string",
          "tags": ["1-3 short lowercase topic tags, e.g. surrealism, geopolitics"],
          "thumbnail": "url string, ONLY for video items, else omit"}}
      ]}}
  ],
  "facts": [
    {{"fact": "one surprising, verifiable sentence", "url": "string"}}
  ],
  "make_something": null OR {{"prompt": "string (2-4 sentences, tied to today's themes)"}}
}}"""


def _make_clause(allow: bool) -> str:
    if allow:
        return (
            "- Today you MAY (not must) end with a 'make something' prompt: a small, "
            "concrete creative or physical build tied to a theme that came up today. "
            "Only include it if it's actually good. Otherwise set make_something to null."
        )
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


def curate(config: dict, candidates: list[dict], taste: str = "") -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    allow_make = random.random() < float(config.get("make_something_chance", 0.35))
    cand_lines = "\n".join(
        f"- {'[VIDEO] ' if c.get('is_video') else ''}[{c['source']}] {c['title']} — {c['url']}"
        + (f"\n    thumbnail: {c['thumbnail']}" if c.get('thumbnail') else "")
        + f"\n    {c.get('summary', '')[:200]}"
        for c in candidates[:150]
    ) or "(no feed candidates today — rely on search)"

    prompt = PROMPT.format(
        persona=config["persona"].strip(),
        interests="\n".join(f"- {i}" for i in config["interests"]),
        taste=taste.strip() or "(none yet — no feedback received so far)",
        candidates=cand_lines,
        queries="\n".join(f"- {q}" for q in config.get("search_queries", [])),
        n=config.get("target_item_count", 7),
        make_clause=_make_clause(allow_make),
    )

    model = config.get("model", "claude-sonnet-4-6")
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
    messages = [{"role": "user", "content": prompt}]

    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=SYSTEM,
        messages=messages,
        tools=tools,
    )
    # Server-side web search can pause mid-turn; re-send to let it continue.
    for _ in range(5):
        if resp.stop_reason != "pause_turn":
            break
        messages = messages + [{"role": "assistant", "content": resp.content}]
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            system=SYSTEM,
            messages=messages,
            tools=tools,
        )
    return _extract_json(resp)
