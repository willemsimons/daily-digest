"""The learned taste profile — a short, human-readable file the curator reads
every morning, and that your feedback keeps rewriting.

It's just prose (state/taste.md) so you can also hand-edit it anytime.
"""
from __future__ import annotations

import os

import anthropic

TASTE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "state", "taste.md"
)

_UPDATE_SYSTEM = """You maintain a short "taste profile" for a private daily briefing.
It records what this reader wants more of, less of, and how they like it framed
(topics, tone, length, cadence of the 'make something' prompt). Fold in the new
feedback: strengthen recurring signals, resolve contradictions in favor of the
newest note, and drop anything stale. Keep it tight — bullet points, at most ~35
lines, no preamble. Output ONLY the revised profile as markdown."""


def load_taste() -> str:
    try:
        with open(TASTE_PATH) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def save_taste(text: str) -> None:
    os.makedirs(os.path.dirname(TASTE_PATH), exist_ok=True)
    with open(TASTE_PATH, "w") as f:
        f.write(text.strip() + "\n")


def update_taste(config: dict, feedback: list[str]) -> str:
    """Fold new feedback into the profile. No feedback -> unchanged."""
    current = load_taste()
    if not feedback:
        return current

    client = anthropic.Anthropic()
    joined = "\n".join(f"- {f}" for f in feedback)
    user = (
        f"## Current taste profile\n{current or '(empty — first feedback)'}\n\n"
        f"## New feedback from the reader\n{joined}\n\n"
        "Return the revised profile."
    )
    resp = client.messages.create(
        model=config.get("model", "claude-sonnet-4-6"),
        max_tokens=1200,
        system=_UPDATE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    revised = "".join(b.text for b in resp.content if b.type == "text").strip()
    if revised:
        save_taste(revised)
        print("  taste profile updated")
    return revised or current
