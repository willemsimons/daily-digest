"""Render the curated digest two ways:
  render_page(digest)  -> the full daily web page (hosted on GitHub Pages)
  render_email(digest, page_url) -> a short teaser email linking to it
"""
from __future__ import annotations

import html
import os
import urllib.parse
from datetime import datetime, timezone

INK = "#1c1c1e"
MUTE = "#8a8a8e"
LINE = "#e4e4e6"
BG = "#f4f4f5"
CARD = "#ffffff"
ACCENT = "#1c1c1e"   # minimal: accent is just strong ink, not a color pop


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
    thumb = ""
    if it.get("thumbnail"):
        thumb = (f'<a href="{u}" target="_blank" rel="noopener">'
                 f'<img src="{_esc(it["thumbnail"])}" alt="" loading="lazy" '
                 f'style="width:100%;border-radius:10px;margin:10px 0 4px;display:block;"></a>')
    return f"""
    <article>
      <a class="t" href="{u}" target="_blank" rel="noopener">{t}</a>
      <div class="src">{src}</div>
      {thumb}
      <p class="b">{blurb}</p>
      <div class="fb">
        <a href="{_esc(_mailto('up', raw, tags))}">👍 more</a> ·
        <a href="{_esc(_mailto('down', raw, tags))}">👎 less</a>
      </div>
    </article>"""


def _art_pick(p: dict) -> str:
    medium = _esc((p.get("medium") or "").upper())
    title, creator = _esc(p.get("title", "")), _esc(p.get("creator", ""))
    why, url = _esc(p.get("why", "")), _esc(p.get("url", "#"))
    return f"""
    <article>
      <div class="src">{medium}</div>
      <a class="t" href="{url}" target="_blank" rel="noopener">{title}</a>
      <div class="src" style="margin-top:2px;text-transform:none;letter-spacing:0;">{creator}</div>
      <p class="b" style="margin-top:8px;">{why}</p>
    </article>"""


def _event(e: dict) -> str:
    name, venue = _esc(e.get("name", "")), _esc(e.get("venue", ""))
    date, why, url = _esc(e.get("date", "")), _esc(e.get("why", "")), _esc(e.get("url", "#"))
    return f"""
    <article>
      <a class="t" href="{url}" target="_blank" rel="noopener">{name}</a>
      <div class="src">{venue} &middot; {date}</div>
      <p class="b" style="margin-top:8px;">{why}</p>
    </article>"""


def render_page(digest: dict, trial_sources: list | None = None) -> str:
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

    art_picks = digest.get("art_picks") or []
    art_html = ""
    if art_picks:
        art_html = (f'<section><h2>For you</h2>'
                    f'{"".join(_art_pick(p) for p in art_picks)}</section>')

    events = digest.get("events") or []
    events_html = ""
    if events:
        events_html = (f'<section><h2>Happening in New York</h2>'
                       f'{"".join(_event(e) for e in events)}</section>')

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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:{BG}; color:{INK};
         font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         -webkit-font-smoothing: antialiased; }}
  .wrap {{ max-width: 600px; margin: 0 auto; padding: 48px 20px 72px; }}
  header {{ margin-bottom: 36px; }}
  h1 {{ font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.01em; }}
  .date {{ color:{MUTE}; font-size: 13px; margin-top: 4px; font-weight: 500; }}
  .intro {{ font-size: 16px; line-height: 1.55; color:#4a4a4e; margin-top: 16px; font-weight: 400; }}
  h2 {{ color:{MUTE}; font-size: 12px; font-weight: 600; letter-spacing: .08em;
        text-transform: uppercase; margin: 0 0 14px; }}
  section {{ margin-bottom: 36px; }}
  article {{ background:{CARD}; border-radius: 14px; padding: 18px 20px; margin-bottom: 10px;
             border: 1px solid {LINE}; }}
  .t {{ color:{INK}; text-decoration: none; font-size: 16.5px; font-weight: 600; line-height: 1.35;
        display: block; }}
  .t:hover {{ opacity: 0.7; }}
  .src {{ color:{MUTE}; font-size: 11.5px; font-weight: 500; letter-spacing: .02em; margin: 5px 0 8px; }}
  .b {{ font-size: 14.5px; line-height: 1.55; margin: 0 0 10px; color:#3a3a3e; font-weight: 400; }}
  .fb, .fb a {{ font-size: 12px; color:{MUTE}; text-decoration: none; font-weight: 500; }}
  .fb a:hover {{ color:{INK}; }}
  .facts ul {{ list-style: none; padding: 0; margin: 0; }}
  .facts li {{ background:{CARD}; border: 1px solid {LINE}; border-radius: 14px;
               padding: 14px 18px; margin-bottom: 10px; font-size: 14.5px; line-height: 1.55; }}
  .facts a {{ color:{MUTE}; text-decoration: none; font-weight: 600; }}
  .make {{ background:{CARD}; border: 1px solid {LINE}; border-radius: 14px; padding: 20px 22px; margin-top: 40px; }}
  .make h2 {{ margin-top: 0; }}
  .make p {{ font-size: 14.5px; line-height: 1.55; margin: 0; color:#3a3a3e; }}
  footer {{ margin-top: 44px; padding-top: 16px; border-top: 1px solid {LINE};
            color:{MUTE}; font-size: 12px; line-height: 1.6; }}
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
  {art_html}
  {events_html}
  {make_html}
  {_trial_note(trial_sources)}
  <footer>Tap 👍/👎 on anything, or reply to the email — “go deeper on surrealism”,
  “drop crypto”, “shorter” — and tomorrow adjusts. <a href="index.html">Latest</a></footer>
</div></body></html>"""


def _trial_note(trial: list | None) -> str:
    if not trial:
        return ""
    rows = "".join(
        f'<li><b>{_esc(s.get("name",""))}</b> — {_esc(s.get("why",""))}</li>'
        for s in trial
    )
    return (f'<section class="make" style="margin-top:32px;"><h2>New sources on trial</h2>'
            f'<p style="margin:0 0 10px;">The scout added these this week — thumbs on their '
            f'items decide if they stay:</p><ul style="margin:0;padding-left:20px;'
            f'font-size:15px;line-height:1.6;">{rows}</ul></section>')


def _more_mailto() -> str:
    to = os.environ.get("GMAIL_ADDRESS") or os.environ.get("DIGEST_TO", "")
    q = urllib.parse.urlencode(
        {"subject": "[more]", "body": "Send me another edition."}
    )
    return f"mailto:{to}?{q}"


# ── the teaser email ─────────────────────────────────────────────────
def render_email(digest: dict, page_url: str, supplemental: bool = False) -> str:
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

    extras = []
    if digest.get("art_picks"):
        extras.append(f"{len(digest['art_picks'])} things to watch/see/hear")
    if digest.get("events"):
        extras.append(f"{len(digest['events'])} NYC picks")
    extras_html = (
        f'<div style="margin-top:12px;color:{MUTE};font-size:13px;">Also on the page: '
        + " &middot; ".join(extras) + "</div>"
        if extras else ""
    )

    heading = "More for today" if supplemental else "The Daily"
    more_url = _esc(_more_mailto())

    return f"""<!doctype html><html><body style="margin:0;padding:0;background:{BG};">
  <div style="max-width:560px;margin:0 auto;padding:36px 24px 48px;
     font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="font-size:24px;font-weight:700;color:{INK};">{heading}</div>
    <div style="color:{MUTE};font-size:13px;margin:3px 0 16px;">{_day()}</div>
    <div style="font-style:italic;font-size:16px;line-height:1.5;color:#3a3a3a;
       margin-bottom:22px;">{intro}</div>
    {''.join(rows)}
    {hook}
    {extras_html}
    <div style="margin:28px 0 0;">
      <a href="{url}" style="display:inline-block;background:{INK};color:{BG};
         text-decoration:none;font-size:15px;font-weight:600;padding:13px 26px;
         border-radius:8px;margin-right:10px;">Read today’s page &rarr;</a>
      <a href="{more_url}" style="display:inline-block;background:transparent;
         color:{INK};text-decoration:none;font-size:15px;font-weight:600;
         padding:12px 24px;border-radius:8px;border:1px solid {LINE};">
         Send me more</a>
    </div>
    <div style="border-top:1px solid {LINE};margin-top:32px;padding-top:14px;
       color:{MUTE};font-size:12px;line-height:1.5;">
       Reply to steer tomorrow’s picks. “Send me more” builds a fresh
       supplemental edition within ~15 minutes.</div>
  </div>
</body></html>"""
