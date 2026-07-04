"""Send the digest via Gmail SMTP (app password)."""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone


def send(html: str) -> None:
    gmail = os.environ["GMAIL_ADDRESS"]
    app_pw = os.environ["GMAIL_APP_PASSWORD"]
    to_addr = os.environ.get("DIGEST_TO", gmail)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "The Daily — " + datetime.now(timezone.utc).strftime("%b %-d")
    msg["From"] = f"The Daily <{gmail}>"
    msg["To"] = to_addr
    msg.attach(MIMEText("Open in an HTML-capable client.", "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail, app_pw)
        server.sendmail(gmail, [to_addr], msg.as_string())
    print(f"  sent to {to_addr}")
