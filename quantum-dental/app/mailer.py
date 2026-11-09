"""Outgoing email. Every message is sent individually (no CC/BCC mixing of patient and clinic
recipients) and every attempt is recorded in email_attempts.

Status values recorded and reported (never claims inbox delivery):
  accepted        SMTP server accepted the message for delivery (not proof of inbox delivery)
  outbox          development mode: written to var/outbox as .eml, not sent
  not_configured  email is not configured on the server; nothing was sent
  failed          the send attempt failed (see last_error, admin only)
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

from . import templates
from .config import Config
from .db import Database

log = logging.getLogger("quantum.mail")


def mask(addr: str) -> str:
    """Mask an email address for logs: an***@do***.com"""
    try:
        local, domain = addr.split("@", 1)
        dname, _, tld = domain.rpartition(".")
        return f"{local[:2]}***@{dname[:2]}***.{tld}"
    except ValueError:
        return "***"


class Mailer:
    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db

    # ---------------- building ----------------
    def build(self, to: str, subject: str, text: str, html: str, reply_to: str | None) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = formataddr((self.cfg.mail_from_name, self.cfg.mail_from or "no-reply@localhost"))
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        domain = (self.cfg.mail_from.split("@", 1)[1] if "@" in self.cfg.mail_from else "localhost")
        msg["Message-ID"] = make_msgid(domain=domain)
        msg["Auto-Submitted"] = "auto-generated"
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        return msg

    # ---------------- transport ----------------
    def _connect(self) -> smtplib.SMTP:
        c = self.cfg
        ctx = ssl.create_default_context()
        if c.smtp_security == "ssl":
            s = smtplib.SMTP_SSL(c.smtp_host, c.smtp_port, timeout=c.smtp_timeout, context=ctx)
        else:
            s = smtplib.SMTP(c.smtp_host, c.smtp_port, timeout=c.smtp_timeout)
            s.ehlo()
            if c.smtp_security == "starttls":
                s.starttls(context=ctx)
                s.ehlo()
        if c.smtp_username:
            s.login(c.smtp_username, c.smtp_password)
        return s

    def _deliver(self, messages: list[EmailMessage]) -> list[tuple[str, str]]:
        """Send messages; returns [(status, error)] in order. One connection per batch."""
        if not messages:
            return []
        backend = self.cfg.email_backend
        if backend == "outbox":
            out = []
            self.cfg.outbox_dir.mkdir(parents=True, exist_ok=True)
            for m in messages:
                p = Path(self.cfg.outbox_dir) / f"{uuid.uuid4().hex}.eml"
                p.write_bytes(bytes(m))
                out.append(("outbox", ""))
            return out
        if backend != "smtp" or not self.cfg.smtp_configured:
            return [("not_configured", "Email is not configured on the server.")] * len(messages)
        try:
            server = self._connect()
        except Exception as exc:  # network, TLS, auth...
            err = f"{type(exc).__name__}: {exc}"
            log.warning("SMTP connection failed: %s", type(exc).__name__)
            return [("failed", err)] * len(messages)
        results = []
        try:
            for m in messages:
                try:
                    refused = server.send_message(m)
                    if refused:
                        results.append(("failed", f"Recipient refused: {list(refused.values())[0]}"))
                    else:
                        results.append(("accepted", ""))
                except Exception as exc:
                    results.append(("failed", f"{type(exc).__name__}: {exc}"))
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return results

    # ---------------- orchestration ----------------
    def _send_tracked(self, jobs: list[tuple[str, str, str, EmailMessage]]) -> None:
        """jobs: (source_ref, kind, recipient, message). Uses claim_email so a message that was
        already accepted (or is being sent) is never sent twice."""
        claimed = []
        for ref, kind, rcpt, msg in jobs:
            row = self.db.claim_email(ref, kind, rcpt)
            if row is not None:
                claimed.append((row, msg))
        results = self._deliver([m for _, m in claimed])
        for (row, msg), (status, err) in zip(claimed, results):
            self.db.finish_email(row["id"], status, err, msg["Message-ID"] or "")
            log.info("email kind=%s ref=%s to=%s status=%s", row["kind"], row["source_ref"],
                     mask(row["recipient"]), status)

    def clinic_recipients(self, specialist_id: str | None = None) -> list[str]:
        from .content import specialist_notify_email
        rcpts = list(dict.fromkeys(a.lower() for a in self.cfg.clinic_notify_emails))
        if specialist_id:
            extra = specialist_notify_email(specialist_id)
            if extra and extra.lower() not in rcpts:
                rcpts.append(extra.lower())
        return rcpts

    def send_appointment_emails(self, appt: dict, specialist_name: str, reason_label: str) -> dict:
        review_url = f"{self.cfg.site_url}/admin/#/appointments/{appt['ref']}"
        jobs = []
        s, t, hm = templates.patient_ack(appt, specialist_name)
        jobs.append((appt["ref"], "patient_ack", appt["patient_email"],
                     self.build(appt["patient_email"], s, t, hm, self.cfg.mail_reply_to or None)))
        s, t, hm = templates.clinic_notify(appt, specialist_name, reason_label, review_url)
        for rcpt in self.clinic_recipients(appt["specialist_id"]):
            # Reply-To = patient so staff can answer directly; the patient is never a recipient here.
            jobs.append((appt["ref"], "clinic_notify", rcpt, self.build(rcpt, s, t, hm, appt["patient_email"])))
        self._send_tracked(jobs)
        return self.summary(appt["ref"])

    def send_contact_email(self, msg: dict) -> dict:
        review_url = f"{self.cfg.site_url}/admin/#/messages/{msg['ref']}"
        s, t, hm = templates.contact_notify(msg, review_url)
        jobs = [(msg["ref"], "contact_notify", r, self.build(r, s, t, hm, msg["email"]))
                for r in self.clinic_recipients()]
        self._send_tracked(jobs)
        return self.summary(msg["ref"])

    def send_test(self, recipient: str) -> dict:
        ref = f"TEST-{uuid.uuid4().hex[:8].upper()}"
        s, t, hm = templates.test_email(f"Test reference: {ref}")
        self._send_tracked([(ref, "test", recipient, self.build(recipient, s, t, hm, None))])
        rows = self.db.email_attempts_for(ref)
        return {"ref": ref, "status": rows[0]["status"] if rows else "failed",
                "error": rows[0]["last_error"] if rows else ""}

    def retry_failed(self, source_ref: str) -> dict:
        """Re-send only attempts that failed / were not configured. Accepted ones are untouched."""
        appt = self.db.get_appointment(source_ref)
        if appt:
            from .content import VISIT_REASONS, specialists
            sp = {s["id"]: s["name"] for s in specialists(self.cfg)}
            reasons = {r["id"]: r["label"] for r in VISIT_REASONS}
            return self.send_appointment_emails(appt, sp.get(appt["specialist_id"], appt["specialist_id"]),
                                                reasons.get(appt["reason"], appt["reason"]))
        contact = self.db.get_contact(source_ref)
        if contact:
            return self.send_contact_email(contact)
        return {}

    def summary(self, source_ref: str) -> dict:
        """Public-safe status summary (no addresses, no error text)."""
        rows = self.db.email_attempts_for(source_ref)
        patient = [r["status"] for r in rows if r["kind"] == "patient_ack"]
        clinic = [r["status"] for r in rows if r["kind"] in ("clinic_notify", "contact_notify")]

        def agg(statuses: list[str]) -> str:
            if not statuses:
                return "not_configured"
            for s in ("failed", "not_configured", "sending"):
                if s in statuses:
                    return s
            return "outbox" if "outbox" in statuses else "accepted"

        return {"patient": agg(patient) if patient else None, "clinic": agg(clinic)}
