#!/usr/bin/env python3
"""Quantum Dental Clinic & Implant Center — web server.

Standard library only (Python 3.11+). Serves the single-page website from ./static,
the staff dashboard at /admin/, and the JSON API under /api/.

    python3 server.py            # uses .env if present
"""
from __future__ import annotations

import json
import logging
import mimetypes
import re
import secrets
import string
import sys
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from app import content, templates
from app.config import BASE_DIR, Config, load_config
from app.db import Database
from app.mailer import Mailer
from app.security import AdminSessions, RateLimiter
from app.validation import ValidationError, check_spam, validate_booking, validate_contact

STATIC = BASE_DIR / "static"
MAX_BODY = 16 * 1024
REF_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1L")
APPT_STATUSES = {"pending", "contacted", "confirmed", "declined", "cancelled"}

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
       "frame-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
PREVIEW_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'"

log = logging.getLogger("quantum")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/manifest+json", ".webmanifest")


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.db = Database(cfg.db_path)
        self.mailer = Mailer(cfg, self.db)
        self.limiter = RateLimiter()
        self.sessions = AdminSessions(cfg.session_secret, cfg.admin_token)
        self.index_template = (STATIC / "index.html").read_text(encoding="utf-8")

    def new_ref(self, prefix: str) -> str:
        day = datetime.now(ZoneInfo(self.cfg.clinic_timezone)).strftime("%y%m%d")
        return f"{prefix}-{day}-{''.join(secrets.choice(REF_ALPHABET) for _ in range(5))}"

    def route_meta(self, path: str) -> tuple[str, str, int]:
        if path in content.ROUTES:
            t, d = content.ROUTES[path]
            return t, d, 200
        m = re.fullmatch(r"/treatments/([a-z-]+)", path)
        if m and m.group(1) in content.TREATMENT_SLUGS:
            name = m.group(1).replace("-", " ").title()
            return f"{name} — Quantum Dental", f"About {name.lower()}: overview, what a consultation involves, and how to request an appointment.", 200
        m = re.fullmatch(r"/doctors/([a-z0-9-]+)", path)
        if m and any(s["id"] == m.group(1) and not s.get("generic") for s in content.specialists(self.cfg)):
            return "Dentist Profile — Quantum Dental", "Dentist profile at Quantum Dental Clinic & Implant Center.", 200
        return "Page not found — Quantum Dental", "The page you were looking for could not be found.", 404


class Handler(BaseHTTPRequestHandler):
    server_version = "QuantumDental"
    sys_version = ""
    app: App  # set at startup

    # ---------- utilities ----------
    def log_message(self, fmt, *args):  # no query strings / bodies in logs
        log.info("%s %s %s", self.command, urlsplit(self.path).path, args[1] if len(args) > 1 else "")

    def client_ip(self) -> str:
        if self.app.cfg.trust_proxy:
            fwd = self.headers.get("X-Forwarded-For", "")
            if fwd:
                return fwd.split(",")[0].strip()
        return self.client_address[0]

    def common_headers(self, csp: str = CSP):
        self.send_header("Content-Security-Policy", csp)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.app.cfg.site_url.startswith("https://"):
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    def send_json(self, status: int, payload: dict, extra_headers: dict | None = None):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.common_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, status: int, body: bytes, ctype: str, cache: str = "no-cache", csp: str = CSP,
                   head_only: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.common_headers(csp)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def read_json(self) -> dict | None:
        ctype = self.headers.get("Content-Type", "")
        if "application/json" not in ctype:
            self.send_json(415, {"ok": False, "error": "Content-Type must be application/json."})
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.send_json(413, {"ok": False, "error": "Request too large."})
            return None
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"ok": False, "error": "Malformed request."})
            return None

    def same_origin(self) -> bool:
        """CSRF / CORS guard for state-changing requests: browsers always send Origin on
        cross-site POSTs; reject any origin not explicitly allowed."""
        origin = self.headers.get("Origin")
        if origin is None:
            ref = self.headers.get("Referer")
            if ref is None:
                return True  # non-browser client (curl, tests); still rate limited + validated
            parts = urlsplit(ref)
            origin = f"{parts.scheme}://{parts.netloc}"
        allowed = set(self.app.cfg.allowed_origins)
        host = self.headers.get("Host")
        if host:  # the page's own origin is always same-origin
            allowed |= {f"http://{host}", f"https://{host}"}
        return origin in allowed

    def is_admin(self) -> bool:
        c = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = c.get(AdminSessions.COOKIE)
        return self.app.sessions.verify(morsel.value if morsel else None)

    # ---------- dispatch ----------
    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False):
        path = urlsplit(self.path).path
        try:
            if path.startswith("/api/"):
                return self.api_get(path)
            return self.serve_site(path, head_only)
        except Exception:
            log.exception("GET failed")
            self.send_json(500, {"ok": False, "error": "Something went wrong on our side."})

    def do_POST(self):
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            return self.send_json(405, {"ok": False, "error": "Method not allowed."})
        if not self.same_origin():
            return self.send_json(403, {"ok": False, "error": "Cross-origin requests are not allowed."})
        try:
            self.api_post(path)
        except Exception:
            log.exception("POST failed")
            self.send_json(500, {"ok": False, "error": "Something went wrong on our side. Please try again or call +383 49 536 944."})

    def do_OPTIONS(self):
        # No cross-origin access is offered; preflights are refused.
        self.send_response(204)
        self.send_header("Allow", "GET, HEAD, POST")
        self.common_headers()
        self.end_headers()

    # ---------- static site ----------
    def serve_site(self, path: str, head_only: bool):
        cfg = self.app.cfg
        if path == "/robots.txt":
            body = f"User-agent: *\nDisallow: /admin/\nDisallow: /api/\nSitemap: {cfg.site_url}/sitemap.xml\n"
            return self.send_bytes(200, body.encode(), "text/plain; charset=utf-8", "public, max-age=3600",
                                   head_only=head_only)
        if path == "/sitemap.xml":
            urls = list(content.ROUTES) + [f"/treatments/{s}" for s in content.TREATMENT_SLUGS]
            urls = [u for u in urls if u != "/privacy"] + ["/privacy"]
            items = "".join(f"<url><loc>{cfg.site_url}{u}</loc></url>" for u in urls)
            body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>'
            return self.send_bytes(200, body.encode(), "application/xml", "public, max-age=3600", head_only=head_only)
        if path in ("/admin", "/admin/"):
            if path == "/admin":
                self.send_response(301)
                self.send_header("Location", "/admin/")
                self.end_headers()
                return
            body = (STATIC / "admin" / "index.html").read_bytes()
            return self.send_bytes(200, body, "text/html; charset=utf-8", "no-store", head_only=head_only)

        if path.startswith("/static/") or path in ("/favicon.svg", "/site.webmanifest"):
            rel = path[len("/static/"):] if path.startswith("/static/") else path.lstrip("/")
            target = (STATIC / rel).resolve()
            if STATIC.resolve() not in target.parents or not target.is_file() or target.name.startswith("."):
                return self.send_bytes(404, b"Not found", "text/plain; charset=utf-8", head_only=head_only)
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml", "application/json"):
                ctype += "; charset=utf-8"
            cache = "public, max-age=86400" if target.suffix in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".woff2") else "no-cache"
            return self.send_bytes(200, target.read_bytes(), ctype, cache, head_only=head_only)

        if "." in path.rsplit("/", 1)[-1]:
            return self.send_bytes(404, b"Not found", "text/plain; charset=utf-8", head_only=head_only)

        norm = path.rstrip("/") or "/"
        title, desc, status = self.app.route_meta(norm)
        from html import escape
        page = (self.app.index_template
                .replace("{{TITLE}}", escape(title))
                .replace("{{DESCRIPTION}}", escape(desc))
                .replace("{{CANONICAL}}", escape(cfg.site_url + norm))
                .replace("{{SITE_URL}}", escape(cfg.site_url)))
        self.send_bytes(status, page.encode(), "text/html; charset=utf-8", "no-cache", head_only=head_only)

    # ---------- API: GET ----------
    def api_get(self, path: str):
        app = self.app
        if path == "/api/health":
            try:
                app.db.one("SELECT 1 AS ok")
                db_ok = True
            except Exception:
                db_ok = False
            return self.send_json(200 if db_ok else 503, {"ok": db_ok, "database": db_ok,
                                                           "email": "ready" if app.cfg.email_ready else "not_configured"})
        if path == "/api/site-config":
            return self.send_json(200, content.public_site_config(app.cfg))

        if path.startswith("/api/admin/"):
            if not self.is_admin():
                return self.send_json(401, {"ok": False, "error": "Login required."})
            return self.admin_get(path)
        self.send_json(404, {"ok": False, "error": "Not found."})

    def admin_get(self, path: str):
        app, cfg = self.app, self.app.cfg
        if path == "/api/admin/session":
            return self.send_json(200, {"ok": True})
        if path == "/api/admin/email-status":
            recent = app.db.recent_email_attempts(1)
            return self.send_json(200, {
                "backend": cfg.email_backend,
                "ready": cfg.email_ready,
                "smtp": {"host": cfg.smtp_host or None, "port": cfg.smtp_port, "security": cfg.smtp_security,
                         "username": cfg.smtp_username or None, "passwordSet": bool(cfg.smtp_password)},
                "from": cfg.mail_from or None, "replyTo": cfg.mail_reply_to or None,
                "clinicRecipients": app.mailer.clinic_recipients(),
                "senderVerification": "unknown — confirm SPF/DKIM for the sender domain with your email provider",
                "lastAttempt": recent[0] if recent else None,
            })
        if path == "/api/admin/appointments":
            return self.send_json(200, {"items": app.db.list_appointments()})
        m = re.fullmatch(r"/api/admin/appointments/([A-Z0-9-]{6,32})", path)
        if m:
            appt = app.db.get_appointment(m.group(1))
            if not appt:
                return self.send_json(404, {"ok": False, "error": "Not found."})
            return self.send_json(200, {"item": appt, "emails": app.db.email_attempts_for(appt["ref"])})
        if path == "/api/admin/messages":
            return self.send_json(200, {"items": app.db.list_contacts()})
        if path == "/api/admin/email-log":
            return self.send_json(200, {"items": app.db.recent_email_attempts(200)})
        m = re.fullmatch(r"/api/admin/preview/(patient_ack|clinic_notify|contact_notify|test)", path)
        if m:
            sample = {"ref": "QD-SAMPLE-0000", "patient_name": "Sample Patient", "patient_email": "patient@example.com",
                      "patient_phone": "+383 44 000 000", "specialist_id": "first-available", "reason": "checkup",
                      "preferred_date": datetime.now().date().isoformat(), "preferred_time": "10:30",
                      "message": "Sample note", "traveling": 1}
            kind = m.group(1)
            if kind == "patient_ack":
                _, _, html = templates.patient_ack(sample, "First available dentist")
            elif kind == "clinic_notify":
                _, _, html = templates.clinic_notify(sample, "First available dentist", "Check-up or cleaning",
                                                     f"{cfg.site_url}/admin/#/appointments/QD-SAMPLE-0000")
            elif kind == "contact_notify":
                _, _, html = templates.contact_notify({"ref": "QM-SAMPLE-0000", "name": "Sample Sender",
                                                       "email": "sender@example.com", "subject": "Sample subject",
                                                       "message": "This is a sample message.\nSecond line."},
                                                      f"{cfg.site_url}/admin/")
            else:
                _, _, html = templates.test_email("Test reference: TEST-SAMPLE")
            return self.send_bytes(200, html.encode(), "text/html; charset=utf-8", "no-store", csp=PREVIEW_CSP)
        self.send_json(404, {"ok": False, "error": "Not found."})

    # ---------- API: POST ----------
    def api_post(self, path: str):
        app, cfg = self.app, self.app.cfg
        ip = self.client_ip()

        if path == "/api/book-appointment":
            ok, retry = app.limiter.allow("booking", ip, cfg.booking_rate_limit, cfg.rate_window_seconds)
            if not ok:
                return self.send_json(429, {"ok": False, "error": "Too many requests. Please wait a few minutes or call +383 49 536 944."},
                                      {"Retry-After": str(retry)})
            data = self.read_json()
            if data is None:
                return
            if check_spam(data):
                return self.send_json(400, {"ok": False, "error": "Your request could not be submitted. Please try again or call +383 49 536 944."})
            sps = content.specialists(cfg)
            try:
                rec = validate_booking(data, specialist_ids={s["id"] for s in sps},
                                       reason_ids={r["id"] for r in content.VISIT_REASONS},
                                       times=content.PREFERRED_TIMES, tz=cfg.clinic_timezone)
            except ValidationError as ve:
                return self.send_json(422, {"ok": False, "error": "Please check the highlighted fields.", "fields": ve.errors})
            rec["ref"] = app.new_ref("QD")
            row, created = app.db.insert_appointment(rec)
            sp = next((s for s in sps if s["id"] == row["specialist_id"]), {"name": row["specialist_id"]})
            reason = next((r["label"] for r in content.VISIT_REASONS if r["id"] == row["reason"]), row["reason"])
            # Send (or, on a duplicate submission, only re-attempt messages that never went out).
            email = app.mailer.send_appointment_emails(row, sp["name"], reason)
            log.info("booking ref=%s created=%s", row["ref"], created)
            return self.send_json(201 if created else 200, {
                "ok": True, "created": created, "ref": row["ref"], "status": row["status"],
                "specialist": {"id": row["specialist_id"], "name": sp["name"]},
                "date": row["preferred_date"], "time": row["preferred_time"], "email": email,
            })

        if path == "/api/contact":
            ok, retry = app.limiter.allow("contact", ip, cfg.contact_rate_limit, cfg.rate_window_seconds)
            if not ok:
                return self.send_json(429, {"ok": False, "error": "Too many messages. Please wait a few minutes or call +383 49 536 944."},
                                      {"Retry-After": str(retry)})
            data = self.read_json()
            if data is None:
                return
            if check_spam(data):
                return self.send_json(400, {"ok": False, "error": "Your message could not be sent. Please try again or call +383 49 536 944."})
            try:
                rec = validate_contact(data)
            except ValidationError as ve:
                return self.send_json(422, {"ok": False, "error": "Please check the highlighted fields.", "fields": ve.errors})
            rec["ref"] = app.new_ref("QM")
            row, created = app.db.insert_contact(rec)
            email = app.mailer.send_contact_email(row)
            return self.send_json(201 if created else 200, {"ok": True, "created": created, "ref": row["ref"],
                                                            "email": {"clinic": email["clinic"]}})

        if path == "/api/admin/login":
            data = self.read_json()
            if data is None:
                return
            if not app.sessions.enabled:
                return self.send_json(503, {"ok": False, "error": "Admin access is not configured (set ADMIN_TOKEN, min. 16 characters)."})
            if not app.sessions.check_token(str(data.get("token", "")), ip):
                return self.send_json(401, {"ok": False, "error": "Invalid access token."})
            secure = "; Secure" if cfg.site_url.startswith("https://") else ""
            cookie = f"{AdminSessions.COOKIE}={app.sessions.issue()}; Path=/; HttpOnly; SameSite=Strict; Max-Age={AdminSessions.TTL}{secure}"
            return self.send_json(200, {"ok": True}, {"Set-Cookie": cookie})
        if path == "/api/admin/logout":
            return self.send_json(200, {"ok": True}, {"Set-Cookie": f"{AdminSessions.COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

        if path.startswith("/api/admin/"):
            if not self.is_admin():
                return self.send_json(401, {"ok": False, "error": "Login required."})
            return self.admin_post(path)
        self.send_json(404, {"ok": False, "error": "Not found."})

    def admin_post(self, path: str):
        app = self.app
        if path == "/api/admin/test-email":
            data = self.read_json()
            if data is None:
                return
            to = str(data.get("to", "")).strip().lower()
            from app.validation import valid_email
            if not valid_email(to):
                return self.send_json(422, {"ok": False, "error": "Enter a valid recipient address."})
            res = app.mailer.send_test(to)
            return self.send_json(200, {"ok": res["status"] in ("accepted", "outbox"), **res})
        m = re.fullmatch(r"/api/admin/appointments/([A-Z0-9-]{6,32})/status", path)
        if m:
            data = self.read_json()
            if data is None:
                return
            status = str(data.get("status", ""))
            if status not in APPT_STATUSES:
                return self.send_json(422, {"ok": False, "error": "Unknown status."})
            if not app.db.set_appointment_status(m.group(1), status):
                return self.send_json(404, {"ok": False, "error": "Not found."})
            return self.send_json(200, {"ok": True, "status": status})
        m = re.fullmatch(r"/api/admin/(?:appointments|messages)/([A-Z0-9-]{6,32})/retry-email", path)
        if m:
            res = app.mailer.retry_failed(m.group(1))
            if not res:
                return self.send_json(404, {"ok": False, "error": "Not found."})
            return self.send_json(200, {"ok": True, "email": res, "attempts": app.db.email_attempts_for(m.group(1))})
        self.send_json(404, {"ok": False, "error": "Not found."})


def make_server(cfg: Config) -> ThreadingHTTPServer:
    Handler.app = App(cfg)
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), Handler)
    httpd.daemon_threads = True
    return httpd


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config()
    httpd = make_server(cfg)
    log.info("Quantum Dental running on http://%s:%s  (email backend: %s, ready: %s, demo data: %s)",
             cfg.host, cfg.port, cfg.email_backend, cfg.email_ready, cfg.demo_data)
    if not Handler.app.sessions.enabled:
        log.warning("ADMIN_TOKEN not set (or shorter than 16 chars): staff dashboard login is disabled.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    sys.exit(main())
