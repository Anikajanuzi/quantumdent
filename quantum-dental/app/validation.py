"""Server-side validation and sanitisation. The browser validates too, but these checks are
authoritative: the server never trusts client input."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                      r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
PHONE_ALLOWED_RE = re.compile(r"^[+()\-.\s0-9]+$")
KEY_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MAX_DAYS_AHEAD = 365


class ValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        super().__init__("validation failed")
        self.errors = errors


def clean_text(value, max_len: int, *, multiline: bool = False) -> str:
    """Normalise unicode, strip control characters, collapse whitespace, cap length.
    HTML escaping happens at output time (email templates / admin UI), not here."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize("NFC", value)
    keep = []
    for ch in value:
        cat = unicodedata.category(ch)
        if ch in "\n\t" and multiline:
            keep.append(ch)
        elif cat.startswith("C"):
            keep.append(" ")
        else:
            keep.append(ch)
    value = "".join(keep)
    if multiline:
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in value.split("\n")]
        value = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    else:
        value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len]


def valid_email(v: str) -> bool:
    return bool(v) and len(v) <= 254 and EMAIL_RE.match(v) is not None and ".." not in v


def valid_phone(v: str) -> bool:
    if not v or not PHONE_ALLOWED_RE.match(v):
        return False
    digits = re.sub(r"\D", "", v)
    return 7 <= len(digits) <= 15


def check_spam(payload: dict) -> bool:
    """True if the submission looks automated: honeypot filled, or form completed implausibly fast."""
    if clean_text(payload.get("website"), 200):
        return True
    elapsed = payload.get("elapsedMs")
    if isinstance(elapsed, (int, float)) and elapsed < 2500:
        return True
    return False


def validate_booking(payload: dict, *, specialist_ids: set[str], reason_ids: set[str],
                     times: list[str], tz: str, now: datetime | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Invalid request."})
    errors: dict[str, str] = {}

    key = str(payload.get("idempotencyKey") or "")
    if not KEY_RE.match(key):
        errors["idempotencyKey"] = "Missing request key. Please reload the page and try again."

    name = clean_text(payload.get("name"), 120)
    if len(name) < 2:
        errors["name"] = "Please enter your full name."

    email = clean_text(payload.get("email"), 254).lower()
    if not email:
        errors["email"] = "Please enter your email address."
    elif not valid_email(email):
        errors["email"] = "Please enter a valid email address, e.g. name@example.com."

    phone = clean_text(payload.get("phone"), 32)
    if not phone:
        errors["phone"] = "Please enter a phone number."
    elif not valid_phone(phone):
        errors["phone"] = "Please enter a valid phone number (7–15 digits, + allowed)."

    specialist = clean_text(payload.get("specialistId"), 64)
    if not specialist:
        errors["specialistId"] = "Please choose a dentist."
    elif specialist not in specialist_ids:
        errors["specialistId"] = "The selected dentist is not available. Please choose again."

    reason = clean_text(payload.get("reason"), 40)
    if not reason:
        errors["reason"] = "Please choose a reason for your visit."
    elif reason not in reason_ids:
        errors["reason"] = "Please choose a reason from the list."

    zone = ZoneInfo(tz)
    now = now or datetime.now(zone)
    today = now.date()
    raw_date = clean_text(payload.get("date"), 10)
    raw_time = clean_text(payload.get("time"), 5)
    pref_date: date | None = None
    if not raw_date:
        errors["date"] = "Please choose a preferred date."
    else:
        try:
            pref_date = date.fromisoformat(raw_date)
        except ValueError:
            errors["date"] = "Please choose a valid date."
        else:
            if pref_date < today:
                errors["date"] = "The preferred date cannot be in the past."
            elif pref_date > today + timedelta(days=MAX_DAYS_AHEAD):
                errors["date"] = "Please choose a date within the next 12 months."
    if not raw_time:
        errors["time"] = "Please choose a preferred time."
    elif raw_time not in times:
        errors["time"] = "Please choose a time from the list."
    elif pref_date is not None and "date" not in errors:
        h, m = map(int, raw_time.split(":"))
        when = datetime(pref_date.year, pref_date.month, pref_date.day, h, m, tzinfo=zone)
        if when <= now:
            errors["time"] = "That time has already passed today. Please choose a later time."

    message = clean_text(payload.get("message"), 1000, multiline=True)
    traveling = bool(payload.get("traveling") is True)
    consent = payload.get("consent") is True
    if not consent:
        errors["consent"] = "Please confirm that the clinic may use your details to respond to this request."

    if errors:
        raise ValidationError(errors)
    return {
        "idempotency_key": key, "patient_name": name, "patient_email": email, "patient_phone": phone,
        "specialist_id": specialist, "reason": reason, "preferred_date": raw_date,
        "preferred_time": raw_time, "message": message, "traveling": traveling,
    }


def validate_contact(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError({"_": "Invalid request."})
    errors: dict[str, str] = {}
    key = str(payload.get("idempotencyKey") or "")
    if not KEY_RE.match(key):
        errors["idempotencyKey"] = "Missing request key. Please reload the page and try again."
    name = clean_text(payload.get("name"), 120)
    if len(name) < 2:
        errors["name"] = "Please enter your name."
    email = clean_text(payload.get("email"), 254).lower()
    if not email:
        errors["email"] = "Please enter your email address."
    elif not valid_email(email):
        errors["email"] = "Please enter a valid email address, e.g. name@example.com."
    subject = clean_text(payload.get("subject"), 150)
    if len(subject) < 2:
        errors["subject"] = "Please add a subject."
    message = clean_text(payload.get("message"), 3000, multiline=True)
    if len(message) < 10:
        errors["message"] = "Please write a message of at least 10 characters."
    if errors:
        raise ValidationError(errors)
    return {"idempotency_key": key, "name": name, "email": email, "subject": subject, "message": message}
