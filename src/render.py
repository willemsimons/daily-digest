"""Render the curated digest two ways:
  render_page(digest)  -> the full daily web page (hosted on GitHub Pages)
  render_email(digest, page_url) -> a short teaser email linking to it
"""
from __future__ import annotations

import html
import os
import urllib.parse
from datetime import datetime, timezone

INK = "#1a1a1a"
MUTE = "#6b6b6b"
LINE = "#e6e3dd"
BG = "#faf8f4"
ACCENT = "#b3541e"


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%A, %B %-d, %Y")


# ── feedback links (mailto, reused on page and email) ────────────────
def _mailto(signal: str, title: str, tags: list) -> str:
    to = os.environ.get("GMAIL_ADDRESS") or os.environ.get("DIGEST_TO", "")
    tagstr = " ".join(f"#{t}" for t in (tags or []))
    verb = "More like this" if signal == "up" else "Less like this"
    q = urllib.parse.urlencode(
        {"subject": "[taste] " + ("👍" if signal == "up" else "👎"),
         "body": f'{verb}: "{title}" {tagstr}'.strip()}
    )
    return f"mailto:{to}?{q}"


# ── the daily page ────────────────────────────────────────────────────
def _page_item(it: dict) -> str:
    t, u = _esc(it.get("title", "")), _esc(it.get("url", "#"))
    src, blurb = _esc(it.get("source", "")), _esc(it.get("blurb", ""))
    raw, tags = it.get("title", ""), it.get("tags", [])
    return f"""
    <article>
      <a class="t" href="{u}" target="_blank" rel="noopener">{t}</a>
      <div class="src">{src}</div>
      <p class="b">{blurb}</p>
      <div class="fb">
        <a href="{_esc(_mailto('up', raw, tags))}">👍 more</a> ·
        <a href="{_esc(_mailto('down', raw, tags))}">👎 less</a>
      </div>
    </article>"""


def render_page(digest: dict) -> str:
    intro = _esc(digest.get("intro", ""))
    sections = "".join(
        f"""<section>
        <h2>{_esc(s.get('heading',''))}</h2>
        {''.join(_page_item(it) for it in s.get('items', []))}
        </section>"""
        for s in digest.get("sections", [])
    )

    facts = digest.get("facts") or []
    facts_html = ""
    if facts:
        lis = "".join(
            f'<li>{_esc(f.get("fact",""))} '
            f'<a href="{_esc(f.get("url","#"))}" target="_blank" rel="noopener">→</a></li>'
            for f in facts
        )
        facts_html = f'<section class="facts"><h2>Facts of the day</h2><ul>{lis}</ul></section>'

    make = digest.get("make_something")
    make_html = (
        f'<section class="make"><h2>Make something</h2>'
        f'<p>{_esc(make["prompt"])}</p></section>'
        if make and make.get("prompt")
        else ""
    )

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>The Daily — {_day()}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:{BG}; color:{INK};
         font-family: Georgia, 'Iowan Old Style', 'Times New Roman', serif; }}
  .wrap {{ max-width: 640px; margin: 0 auto; padding: 56px 24px 80px; }}
  header {{ border-bottom: 1px solid {LINE}; padding-bottom: 22px; margin-bottom: 40px; }}
  h1 {{ font-size: 30px; margin: 0; letter-spacing: -0.01em; }}
  .date {{ color:{MUTE}; font-size: 14px; margin-top: 6px; }}
  .intro {{ font-style: italic; font-size: 18px; line-height: 1.55; color:#3a3a3a; margin-top: 18px; }}
  h2 {{ color:{ACCENT}; font-size: 13px; font-weight: 700; letter-spacing: .1em;
        text-transform: uppercase; margin: 44px 0 20px; }}
  article {{ margin-bottom: 34px; }}
  .t {{ color:{INK}; text-decoration: none; font-size: 21px; font-weight: 600; line-height: 1.3; }}
  .t:hover {{ color:{ACCENT}; }}
  .src {{ color:{MUTE}; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; margin: 6px 0 8px; }}
  .b {{ font-size: 16.5px; line-height: 1.62; margin: 0 0 8px; color:#2c2c2c; }}
  .fb, .fb a {{ font-size: 12.5px; color:{MUTE}; text-decoration: none; }}
  .fb a:hover {{ color:{ACCENT}; }}
  .facts ul {{ padding-left: 20px; margin: 0; }}
  .facts li {{ font-size: 16px; line-height: 1.6; margin-bottom: 12px; }}
  .facts a {{ color:{ACCENT}; text-decoration: none; }}
  .make {{ background:#fff; border: 1px solid {LINE}; border-radius: 12px; padding: 24px 26px; margin-top: 48px; }}
  .make h2 {{ margin-top: 0; }}
  .make p {{ font-size: 16px; line-height: 1.6; margin: 0; }}
  footer {{ border-top: 1px solid {LINE}; margin-top: 56px; padding-top: 18px;
            color:{MUTE}; font-size: 13px; line-height: 1.6; }}
  footer a {{ color:{MUTE}; }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>The Daily</h1>
    <div class="date">{_day()}</div>
    <div class="intro">{intro}</div>
  </header>
  {sections}
  {facts_html}
  {make_html}
  <footer>Tap 👍/👎 on anything, or reply to the email — “go deeper on surrealism”,
  “drop crypto”, “shorter” — and tomorrow adjusts. <a href="index.html">Latest</a></footer>
</div></body></html>"""


# ── the teaser email ─────────────────────────────────────────────────
def render_email(digest: dict, page_url: str) -> str:
    intro = _esc(digest.get("intro", ""))
    url = _esc(page_url)

    # headline list: section heading + its item titles
    rows = []
    for s in digest.get("sections", []):
        head = _esc(s.get("heading", ""))
        titles = "".join(
            f'<div style="font-size:15px;line-height:1.5;color:#2c2c2c;margin:3px 0;">'
            f'&bull;&nbsp;{_esc(it.get("title",""))}</div>'
            for it in s.get("items", [])
        )
        rows.append(
            f'<div style="margin:0 0 16px;">'
            f'<div style="color:{ACCENT};font-size:12px;font-weight:700;letter-spacing:.08em;'
            f'text-transform:uppercase;margin-bottom:6px;">{head}</div>{titles}</div>'
        )

    facts = digest.get("facts") or []
    hook = ""
    if facts:
        hook = (
            f'<div style="margin:20px 0 0;padding:16px 18px;background:#fff;'
            f'border:1px solid {LINE};border-radius:10px;font-size:15px;line-height:1.55;">'
            f'<span style="color:{ACCENT};font-weight:700;">Fact of the day&nbsp;&nbsp;</span>'
            f'{_esc(facts[0].get("fact",""))}</div>'
        )

    return f"""<!doctype html><html><body style="margin:0;padding:0;background:{BG};">
  <div style="max-width:560px;margin:0 auto;padding:36px 24px 48px;
     font-family:Georgia,'Iowan Old Style',serif;">
    <div style="font-size:24px;font-weight:700;color:{INK};">The Daily</div>
    <div style="color:{MUTE};font-size:13px;margin:3px 0 16px;">{_day()}</div>
    <div style="font-style:italic;font-size:16px;line-height:1.5;color:#3a3a3a;
       margin-bottom:22px;">{intro}</div>
    {''.join(rows)}
    {hook}
    <div style="margin:28px 0 0;">
      <a href="{url}" style="display:inline-block;background:{INK};color:{BG};
         text-decoration:none;font-size:15px;font-weight:600;padding:13px 26px;
         border-radius:8px;">Read today’s page &rarr;</a>
    </div>
    <div style="border-top:1px solid {LINE};margin-top:32px;padding-top:14px;
       color:{MUTE};font-size:12px;line-height:1.5;">
       Reply to steer tomorrow’s picks.</div>
  </div>
</body></html>"""
