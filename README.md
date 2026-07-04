# The Daily

A private morning briefing. Every day it pulls from RSS, Reddit, and live web
search across your interests, has Claude curate the few things actually worth your
attention, writes it up, and emails it to you. Occasionally it ends with a small
"make something" prompt.

Each day is published as its own web page (free, via GitHub Pages) and the email
is a short teaser — headlines, one fact as a hook, and a button to the day's page.
The site doubles as a permanent, browsable archive of everything you've read.

No server to babysit — it runs on a free GitHub Actions cron.

## How it works

```
feeds (RSS + Reddit)  ─┐                      ┌─► docs/YYYY-MM-DD.html  (GitHub Pages)
                       ├─►  curate.py  ──────┤
live web search  ──────┘   (Claude picks,     └─► teaser email w/ link  (Gmail SMTP)
                            ranks, writes,
                            + facts of the day)
```

**How it finds things** — three layers, no brittle crawling:
1. *Structured feeds*: RSS/Atom from publications, any Substack (`/feed`), any
   subreddit (append `.rss`). Stable and free.
2. *Live web search at run-time*: Claude searches your fast-moving topics fresh each
   morning (news, geopolitics, health research) — this surfaces what no feed would.
3. *Curation*: hundreds of candidates in, ~7 out — ranked by Claude against your
   persona and your accumulated taste file. Blurbs are written to educate AND be
   retellable in conversation, plus 3-5 "facts of the day".

- `config.yaml` — the whole brain lives here: your persona, interests, feeds,
  search queries, model, and how often the "make something" prompt shows up.
- Each run commits an updated `state/seen.json` (so nothing repeats) and drops the
  day's email into `archive/YYYY-MM-DD.html` — a free running archive.

## Setup (~10 min)

1. **New GitHub repo** — push this folder to it.
2. **Anthropic API key** — from console.anthropic.com.
3. **Gmail App Password** — turn on 2-step verification, then create an App
   Password (Google Account → Security → App passwords). This is *not* your normal
   password; SMTP needs the 16-char app password.
4. **Add 4 repo secrets** (Settings → Secrets and variables → Actions):
   | secret | value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your key |
   | `GMAIL_ADDRESS` | the sending Gmail |
   | `GMAIL_APP_PASSWORD` | the 16-char app password |
   | `DIGEST_TO` | where it lands (e.g. willem@daze.nyc) |
5. **Turn on GitHub Pages** — repo Settings → Pages → Source: *Deploy from a branch* →
   Branch `main`, folder `/docs`. Your site lives at
   `https://USERNAME.github.io/REPO/`.
6. **Add a 5th secret** — `SITE_BASE_URL` = that Pages URL (no trailing slash), so
   the email button links to the right place.
7. **Test it now** — Actions tab → *daily-digest* → *Run workflow*. Check your inbox.

> Privacy note: GitHub Pages on a free plan means a public repo, so the daily pages
> are technically public at an obscure URL (they're marked `noindex` so search
> engines skip them — it's a link digest, nothing sensitive). If you want it fully
> private later: GitHub Pro allows Pages on private repos, or serve `docs/` from the
> Mac mini instead.

It then sends automatically every morning (11:30 UTC ≈ 7:30am ET — edit the cron in
`.github/workflows/digest.yml` to taste).

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...  GMAIL_ADDRESS=...  GMAIL_APP_PASSWORD=...  DIGEST_TO=...
python -m src.main --dry-run   # builds + archives, doesn't email
python -m src.main             # the real thing
```

## Teaching it your taste

Two ways to steer it, both flowing back through the same inbox — no server needed:

- **One-tap** — every item has 👍 more / 👎 less links. Tapping opens a pre-filled
  email (subject `[taste] …`); just hit send.
- **Freeform reply** — reply to any digest with plain notes: *"go deeper on
  surrealism", "drop crypto", "make-something less often", "shorter"*.

Before each morning's run it reads new feedback via IMAP and folds it into
`state/taste.md` — a short, human-readable profile the curator weights heavily.
You can also open `taste.md` and edit it by hand; it's just prose. Items are tagged
by topic so a 👎 on one surrealism piece nudges the whole subject, not just that URL.

## Tuning

- **`persona`** in `config.yaml` is the single biggest lever on taste — rewrite it
  in your own voice and the curation shifts noticeably.
- Add/remove **feeds** and **search_queries** freely. Reddit RSS works unauthenticated;
  just append `.rss` to any subreddit URL.
- `make_something_chance` (0–1) controls how often the build prompt appears.
- `model`: `claude-sonnet-4-6` is the cheap daily default; bump to `claude-opus-4-8`
  for richer writing. A daily sonnet run costs pennies.

## Later

- **X / deeper Reddit**: both need paid/authed APIs now — deliberately left out so v1
  stays free and reliable. Easy to bolt on as a new fetcher.
- Move the cron to the Mac mini (launchd) if you'd rather own the schedule.
