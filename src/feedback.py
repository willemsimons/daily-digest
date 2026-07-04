"""Read feedback back out of the inbox.

Two things land here:
  - one-tap thumbs: emails with subject "[taste] ..." (from the mailto links)
  - freeform replies: "Re: The Daily ..." where you just wrote notes
Both are returned as raw text for taste.py to fold into your profile.
Uses the same Gmail address + app password as sending (app pw works for IMAP).
"""
from __future__ import annotations

import email
import imaplib
import os
from email.header import decode_header


def _decode(s) -> str:
    if not s:
        return ""
    parts = decode_header(s)
    return "".join(
        (p.decode(enc or "utf-8", "ignore") if isinstance(p, bytes) else p)
        for p, enc in parts
    )


def _body_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "ignore")
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(msg.get_content_charset() or "utf-8", "ignore") if payload else ""


def _strip_quoted(text: str) -> str:
    """Drop the quoted digest that mail clients append to replies."""
    out = []
    for line in text.splitlines():
        if line.startswith(">") or line.strip().startswith("On ") and "wrote:" in line:
            break
        out.append(line)
    return "\n".join(out).strip()


def fetch_feedback() -> list[str]:
    gmail = os.environ.get("GMAIL_ADDRESS")
    app_pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail or not app_pw:
        print("  (no email creds — skipping feedback)")
        return []
    allowed = {gmail.lower(), os.environ.get("DIGEST_TO", gmail).lower()}

    try:
        M = imaplib.IMAP4_SSL("imap.gmail.com")
        M.login(gmail, app_pw)
    except Exception as e:
        print(f"  ! imap login failed, skipping feedback ({e})")
        return []

    M.select("INBOX")
    ids: set[bytes] = set()
    for crit in ('(UNSEEN SUBJECT "[taste]")', '(UNSEEN SUBJECT "The Daily")'):
        typ, data = M.search(None, crit)
        if typ == "OK" and data and data[0]:
            ids.update(data[0].split())

    notes: list[str] = []
    for mid in ids:
        typ, data = M.fetch(mid, "(RFC822)")
        if typ != "OK":
            continue
        msg = email.message_from_bytes(data[0][1])
        sender = email.utils.parseaddr(msg.get("From", ""))[1].lower()
        if sender not in allowed:  # only trust feedback from you
            continue
        subject = _decode(msg.get("Subject", ""))
        body = _strip_quoted(_body_text(msg))
        note = f"[{subject}] {body}".strip()
        if note:
            notes.append(note)
        M.store(mid, "+FLAGS", "\\Seen")  # process once

    try:
        M.logout()
    except Exception:
        pass
    print(f"  {len(notes)} new feedback message(s)")
    return notes
