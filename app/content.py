"""Server-side content shared with the frontend: specialists, visit reasons, time options,
and per-route SEO metadata. Keeping these here means the server validates against the same
list the browser displays."""
from __future__ import annotations

import json
from pathlib import Path

from .config import BASE_DIR, Config

FIRST_AVAILABLE = {
    "id": "first-available",
    "name": "First available dentist",
    "title": "Clinic assigns",
    "specialty": "The clinic matches your request to a suitable dentist",
    "qualifications": [],
    "bio": "",
    "appointment_types": [],
    "photo": None,
    "demo": False,
    "generic": True,
}

# Reasons describe the patient's need, not a claim about services offered.
VISIT_REASONS = [
    {"id": "checkup", "label": "Check-up or cleaning"},
    {"id": "pain", "label": "Tooth pain or discomfort"},
    {"id": "consultation", "label": "Consultation about a treatment"},
    {"id": "second-opinion", "label": "Second opinion"},
    {"id": "follow-up", "label": "Follow-up visit"},
    {"id": "other", "label": "Something else"},
]

# Preferred-time options. These are REQUEST windows, not confirmed availability.
# Adjust once the clinic's real opening hours are verified.
PREFERRED_TIMES = [f"{h:02d}:{m:02d}" for h in range(9, 18) for m in (0, 30)]

# Per-route metadata used both by the server (initial HTML for direct links / crawlers)
# and by the frontend router (title updates on navigation).
ROUTES = {
    "/": ("Quantum Dental Clinic & Implant Center",
          "Quantum Dental Clinic & Implant Center — a contemporary dental clinic. Request an appointment online or call +383 49 536 944."),
    "/treatments": ("Treatments — Quantum Dental",
                    "An overview of dental treatment areas and what to expect at a consultation with Quantum Dental."),
    "/results": ("Results — Quantum Dental",
                 "Treatment results published with patient consent."),
    "/doctors": ("Our Dentists — Quantum Dental",
                 "Meet the dental team at Quantum Dental Clinic & Implant Center."),
    "/pricing": ("Pricing — Quantum Dental",
                 "How pricing works at Quantum Dental and how to request a current quote."),
    "/travel": ("Travelling Patients — Quantum Dental",
                "Guidance for patients travelling from another city or country to Quantum Dental."),
    "/booking": ("Request an Appointment — Quantum Dental",
                 "Request an appointment with Quantum Dental. Choose a dentist, a preferred date and time, and the clinic will confirm."),
    "/contact": ("Contact — Quantum Dental",
                 "Call Quantum Dental on +383 49 536 944 or send a message."),
    "/privacy": ("Privacy — Quantum Dental",
                 "How Quantum Dental handles the personal information you submit through this website."),
}

TREATMENT_SLUGS = ["general-dentistry", "dental-implants", "orthodontics", "cosmetic-dentistry",
                   "endodontics", "periodontal-care", "pediatric-dentistry", "prosthodontics"]


def _load(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [s for s in data.get("specialists", []) if isinstance(s, dict) and s.get("id")]
    except (OSError, ValueError):
        return []


def specialists(cfg: Config) -> list[dict]:
    """Public specialist list: verified entries, plus demo entries only in DEMO_DATA mode,
    plus the always-available 'first available dentist' option. Never includes emails."""
    out = [dict(FIRST_AVAILABLE)]
    for s in _load(BASE_DIR / "data" / "specialists.json"):
        s = {k: v for k, v in s.items() if k not in ("email", "notify_email")}
        s["demo"] = False
        out.append(s)
    if cfg.demo_data:
        for s in _load(BASE_DIR / "data" / "demo_specialists.json"):
            s = {k: v for k, v in s.items() if k not in ("email", "notify_email")}
            s["demo"] = True
            out.append(s)
    return out


def specialist_notify_email(specialist_id: str) -> str | None:
    """Optional per-specialist notification address (verified specialists only)."""
    for s in _load(BASE_DIR / "data" / "specialists.json"):
        if s.get("id") == specialist_id and s.get("notify_email"):
            return str(s["notify_email"]).strip()
    return None


def public_site_config(cfg: Config) -> dict:
    return {
        "clinic": {
            "name": "Quantum Dental Clinic & Implant Center",
            "phone": "+383 49 536 944",
            "phoneLocal": "049-536-944",
            "phoneHref": "tel:+38349536944",
            "address": None,        # not yet verified
            "hours": None,          # not yet verified
            "publicEmail": None,    # not yet verified (staff addresses are never published)
            "mapUrl": None,
        },
        "specialists": specialists(cfg),
        "reasons": VISIT_REASONS,
        "times": PREFERRED_TIMES,
        "timezone": cfg.clinic_timezone,
        "formsubmit": ({"to": cfg.clinic_notify_emails[0], "cc": ",".join(cfg.clinic_notify_emails[1:])}
                       if cfg.email_backend == "formsubmit" and cfg.clinic_notify_emails else None),
        "demo": cfg.demo_data,
        "draftBanner": cfg.draft_banner,
        "routes": {k: {"title": t, "description": d} for k, (t, d) in ROUTES.items()},
    }
