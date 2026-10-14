"""設定は環境変数（または .env）から読む。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    db_path: str
    request_delay: float
    use_browser: bool
    auto_browser: bool
    interval_minutes: int
    host: str
    port: int
    slack_webhook: str | None
    discord_webhook: str | None
    line_token: str | None
    line_to: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    mail_from: str | None
    mail_to: list[str]


def load_settings() -> Settings:
    _load_dotenv()
    env = os.environ.get
    return Settings(
        db_path=env("PRICEWATCH_DB", "data/pricewatch.db"),
        request_delay=float(env("PRICEWATCH_DELAY", "3")),
        use_browser=_bool("PRICEWATCH_BROWSER"),
        auto_browser=_bool("PRICEWATCH_AUTO_BROWSER"),
        interval_minutes=int(env("PRICEWATCH_INTERVAL", "60")),
        host=env("PRICEWATCH_HOST", "127.0.0.1"),
        port=int(env("PRICEWATCH_PORT", "8000")),
        slack_webhook=env("SLACK_WEBHOOK_URL"),
        discord_webhook=env("DISCORD_WEBHOOK_URL"),
        line_token=env("LINE_CHANNEL_ACCESS_TOKEN"),
        line_to=env("LINE_TO"),
        smtp_host=env("SMTP_HOST"),
        smtp_port=int(env("SMTP_PORT", "587")),
        smtp_user=env("SMTP_USER"),
        smtp_password=env("SMTP_PASSWORD"),
        mail_from=env("MAIL_FROM"),
        mail_to=[a.strip() for a in env("MAIL_TO", "").split(",") if a.strip()],
    )
