"""Cheap poller for the 'Send me more' button.

Runs every 15 min via its own workflow, checks IMAP for one unread request
email, and only if found does it run the (expensive) full pipeline. Costs
almost nothing when idle -- one IMAP login and search.
"""
from __future__ import annotations

from src import feedback, main

if __name__ == "__main__":
    if feedback.check_more_request():
        print("· 'more' requested — building a supplemental edition")
        main.main(dry_run=False, supplemental=True)
    else:
        print("· no request pending")
