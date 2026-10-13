"""通知: Slack / Discord / LINE（Messaging API）/ メール。設定されたものすべてに送る。"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

import requests

from .config import Settings
from .monitor import Event, summarize

log = logging.getLogger(__name__)

MAX_LINES = 40  # チャット通知が長くなりすぎないように


def _trim(text: str) -> str:
    lines = text.splitlines()
    if len(lines) <= MAX_LINES:
        return text
    return "\n".join(lines[:MAX_LINES] + [f"…ほか {len(lines) - MAX_LINES} 行（Web画面/Excelで確認）"])


class Notifier:
    def __init__(self, settings: Settings):
        self.s = settings

    @property
    def channels(self) -> list[str]:
        s = self.s
        out = []
        if s.slack_webhook:
            out.append("slack")
        if s.discord_webhook:
            out.append("discord")
        if s.line_token and s.line_to:
            out.append("line")
        if s.smtp_host and s.mail_to:
            out.append("email")
        return out

    def __call__(self, events: list[Event]) -> None:
        if not events:
            return
        text = summarize(events)
        short = _trim(text)
        for ch in self.channels:
            try:
                getattr(self, f"_send_{ch}")(short if ch != "email" else text)
            except Exception:
                log.exception("通知に失敗しました: %s", ch)

    def _send_slack(self, text: str) -> None:
        requests.post(self.s.slack_webhook, json={"text": text}, timeout=15).raise_for_status()

    def _send_discord(self, text: str) -> None:
        requests.post(self.s.discord_webhook, json={"content": text[:1990]}, timeout=15).raise_for_status()

    def _send_line(self, text: str) -> None:
        # LINE Notify は 2025/3 で終了したため Messaging API の push を使う
        requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {self.s.line_token}"},
            json={"to": self.s.line_to, "messages": [{"type": "text", "text": text[:4900]}]},
            timeout=15,
        ).raise_for_status()

    def _send_email(self, text: str) -> None:
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = text.splitlines()[0]
        msg["From"] = self.s.mail_from or self.s.smtp_user or "pricewatch@localhost"
        msg["To"] = ", ".join(self.s.mail_to)
        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if self.s.smtp_user:
                smtp.login(self.s.smtp_user, self.s.smtp_password or "")
            smtp.send_message(msg)
