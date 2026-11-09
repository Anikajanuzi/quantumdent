"""Configuration loaded from environment variables (and an optional .env file).

Secrets (SMTP credentials, admin token, session secret) are only ever read here
on the server; nothing in this module is exposed to the browser.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, # comments, optional quotes.
    Existing environment variables always win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


@dataclass
class Config:
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    site_url: str = "http://127.0.0.1:8000"
    allowed_origins: list[str] = field(default_factory=list)
    trust_proxy: bool = False
    clinic_timezone: str = "Europe/Belgrade"  # Kosovo observes CET/CEST

    # Storage
    db_path: Path = BASE_DIR / "var" / "quantum.sqlite3"

    # Content flags
    demo_data: bool = False          # show clearly-labelled demo specialists
    draft_banner: bool = True        # show "content awaiting verification" notice

    # Email
    email_backend: str = "smtp"      # smtp | outbox (dev: writes .eml files) | disabled
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_security: str = "starttls"  # starttls | ssl | none
    smtp_timeout: float = 15.0
    mail_from: str = ""
    mail_from_name: str = "Quantum Dental Clinic & Implant Center"
    mail_reply_to: str = ""          # Reply-To on patient emails (clinic inbox)
    clinic_notify_emails: list[str] = field(default_factory=list)
    outbox_dir: Path = BASE_DIR / "var" / "outbox"

    # Admin
    admin_token: str = ""
    session_secret: str = ""

    # Abuse protection
    booking_rate_limit: int = 5      # requests per window per IP
    contact_rate_limit: int = 5
    rate_window_seconds: int = 600

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.mail_from)

    @property
    def email_ready(self) -> bool:
        if self.email_backend in ("outbox", "formsubmit"):
            return True
        if self.email_backend == "smtp":
            return self.smtp_configured
        return False


def load_config(env_file: Path | None = None) -> Config:
    load_dotenv(env_file or BASE_DIR / ".env")
    e = os.environ.get
    port = int(e("PORT", "8000"))
    host = e("HOST", "127.0.0.1")
    site_url = e("SITE_URL", f"http://{host}:{port}").rstrip("/")
    cfg = Config(
        host=host,
        port=port,
        site_url=site_url,
        allowed_origins=_list("ALLOWED_ORIGINS") or [site_url],
        trust_proxy=_bool("TRUST_PROXY"),
        clinic_timezone=e("CLINIC_TIMEZONE", "Europe/Belgrade"),
        db_path=Path(e("DB_PATH", str(BASE_DIR / "var" / "quantum.sqlite3"))),
        demo_data=_bool("DEMO_DATA"),
        draft_banner=_bool("DRAFT_BANNER", True),
        email_backend=e("EMAIL_BACKEND", "smtp").strip().lower(),
        smtp_host=e("SMTP_HOST", ""),
        smtp_port=int(e("SMTP_PORT", "587")),
        smtp_username=e("SMTP_USERNAME", ""),
        smtp_password=e("SMTP_PASSWORD", ""),
        smtp_security=e("SMTP_SECURITY", "starttls").strip().lower(),
        smtp_timeout=float(e("SMTP_TIMEOUT", "15")),
        mail_from=e("MAIL_FROM", ""),
        mail_from_name=e("MAIL_FROM_NAME", "Quantum Dental Clinic & Implant Center"),
        mail_reply_to=e("MAIL_REPLY_TO", ""),
        clinic_notify_emails=_list("CLINIC_NOTIFY_EMAILS"),
        outbox_dir=Path(e("OUTBOX_DIR", str(BASE_DIR / "var" / "outbox"))),
        admin_token=e("ADMIN_TOKEN", ""),
        session_secret=e("SESSION_SECRET", "") or secrets.token_hex(32),
        booking_rate_limit=int(e("BOOKING_RATE_LIMIT", "5")),
        contact_rate_limit=int(e("CONTACT_RATE_LIMIT", "5")),
        rate_window_seconds=int(e("RATE_WINDOW_SECONDS", "600")),
    )
    return cfg
