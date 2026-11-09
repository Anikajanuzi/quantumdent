"""API tests. Run:  python3 -m unittest discover -s tests -v
Uses a temporary database, the development outbox (no real email is sent) and mock data only."""
from __future__ import annotations

import email
import io
import json
import logging
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from email import policy
from http.cookiejar import CookieJar
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from app.config import Config  # noqa: E402

CLINIC = ["staff.one@example.test", "staff.two@example.test", "staff.three@example.test"]
ADMIN_TOKEN = "test-admin-token-1234567890"
TZ = "Europe/Belgrade"


def tomorrow() -> str:
    return (datetime.now(ZoneInfo(TZ)) + timedelta(days=1)).date().isoformat()


class ServerCase(unittest.TestCase):
    backend = "outbox"
    smtp_port = 587
    rate = 50

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.cfg = Config(host="127.0.0.1", port=0, site_url="http://127.0.0.1", db_path=cls.tmp / "t.sqlite3",
                         email_backend=cls.backend, smtp_host="127.0.0.1" if cls.backend == "smtp" else "",
                         smtp_port=cls.smtp_port, smtp_security="none", smtp_timeout=2,
                         mail_from="appointments@example.test" if cls.backend == "smtp" else "",
                         clinic_notify_emails=list(CLINIC), outbox_dir=cls.tmp / "outbox",
                         admin_token=ADMIN_TOKEN, session_secret="s" * 64,
                         booking_rate_limit=cls.rate, contact_rate_limit=cls.rate)
        cls.httpd = server.make_server(cls.cfg)
        cls.port = cls.httpd.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.log_buf = io.StringIO()
        cls.log_handler = logging.StreamHandler(cls.log_buf)
        logging.getLogger("quantum").addHandler(cls.log_handler)
        logging.getLogger("quantum").setLevel(logging.INFO)

    @classmethod
    def tearDownClass(cls):
        logging.getLogger("quantum").removeHandler(cls.log_handler)
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def req(self, path, body=None, method=None, headers=None, opener=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json"} if data else {}
        h.update(headers or {})
        r = urllib.request.Request(self.base + path, data=data, method=method or ("POST" if data else "GET"), headers=h)
        try:
            resp = (opener or urllib.request.build_opener()).open(r, timeout=10)
            raw = resp.read()
            status = resp.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        try:
            return status, json.loads(raw)
        except ValueError:
            return status, raw

    _n = 0

    def booking(self, **over):
        ServerCase._n += 1
        b = {"idempotencyKey": f"testkey{ServerCase._n:010d}abcdef", "specialistId": "first-available", "date": tomorrow(),
             "time": "10:30", "name": "Test Patient", "email": "patient@example.test", "phone": "+383 44 123 456",
             "reason": "checkup", "message": "Mock data only", "traveling": False, "consent": True,
             "website": "", "elapsedMs": 30000}
        b.update(over)
        return b

    def outbox(self):
        d = self.cfg.outbox_dir
        return [email.message_from_bytes(p.read_bytes(), policy=policy.default) for p in d.glob("*.eml")] if d.exists() else []


class BookingTests(ServerCase):
    def test_health_and_config_have_no_secrets(self):
        s, h = self.req("/api/health")
        self.assertEqual(s, 200)
        self.assertTrue(h["ok"])
        s, c = self.req("/api/site-config")
        blob = json.dumps(c)
        for addr in CLINIC:
            self.assertNotIn(addr, blob)
        self.assertNotIn(ADMIN_TOKEN, blob)
        self.assertEqual(c["specialists"][0]["id"], "first-available")
        self.assertFalse(any(s.get("demo") for s in c["specialists"]))

    def test_valid_booking_sends_two_independent_email_flows(self):
        before = len(self.outbox())
        body = self.booking(email="flow@example.test")
        s, r = self.req("/api/book-appointment", body)
        self.assertEqual(s, 201, r)
        self.assertTrue(r["ok"] and r["created"])
        self.assertRegex(r["ref"], r"^QD-\d{6}-[A-Z0-9]{5}$")
        self.assertEqual(r["status"], "pending")
        self.assertEqual(r["email"], {"patient": "outbox", "clinic": "outbox"})
        msgs = self.outbox()[before:]
        mine = [m for m in self.outbox() if r["ref"] in str(m["Subject"])]
        self.assertEqual(len(mine), 4, "1 patient + 3 clinic messages")
        patient = [m for m in mine if m["To"] == "flow@example.test"]
        clinic = [m for m in mine if m["To"] in CLINIC]
        self.assertEqual(len(patient), 1)
        self.assertEqual(sorted(m["To"] for m in clinic), sorted(CLINIC))
        p = patient[0]
        self.assertIsNone(p["Cc"]); self.assertIsNone(p["Bcc"])
        ptxt = p.get_body(("plain",)).get_content()
        self.assertIn("pending", ptxt.lower())
        self.assertIn("+383 49 536 944", ptxt)
        for addr in CLINIC:
            self.assertNotIn(addr, p.as_string())
        for m in clinic:
            self.assertIsNone(m["Cc"])
            self.assertEqual(m["Reply-To"], "flow@example.test")
            self.assertNotIn("flow@example.test", str(m["To"]))
            ctxt = m.get_body(("plain",)).get_content()
            self.assertNotIn("Mock data only", ctxt, "free-text note must not be emailed")
            self.assertIn("/admin/#/appointments/" + r["ref"], ctxt)
            self.assertIsNotNone(m.get_body(("html",)))
        self.assertTrue(msgs)

    def test_duplicate_submission_is_idempotent(self):
        body = self.booking()
        s1, r1 = self.req("/api/book-appointment", body)
        n = len(self.outbox())
        s2, r2 = self.req("/api/book-appointment", body)
        self.assertEqual((s1, s2), (201, 200))
        self.assertEqual(r1["ref"], r2["ref"])
        self.assertFalse(r2["created"])
        self.assertEqual(len(self.outbox()), n, "no duplicate emails")
        rows = server.Handler.app.db.query("SELECT COUNT(*) AS c FROM appointments WHERE idempotency_key=?", (body["idempotencyKey"],))
        self.assertEqual(rows[0]["c"], 1)

    def assertField(self, body, field):
        s, r = self.req("/api/book-appointment", body)
        self.assertEqual(s, 422, r)
        self.assertIn(field, r["fields"], r)

    def test_validation(self):
        self.assertField(self.booking(specialistId=""), "specialistId")
        self.assertField(self.booking(specialistId="dr-unknown"), "specialistId")
        self.assertField(self.booking(email="not-an-email"), "email")
        self.assertField(self.booking(email="a@b"), "email")
        self.assertField(self.booking(phone="12"), "phone")
        self.assertField(self.booking(phone="call me maybe"), "phone")
        self.assertField(self.booking(name=""), "name")
        self.assertField(self.booking(reason=""), "reason")
        self.assertField(self.booking(reason="cosmetic-surgery"), "reason")
        self.assertField(self.booking(date="2020-01-01"), "date")
        self.assertField(self.booking(date="2026-02-30"), "date")
        self.assertField(self.booking(time="03:00"), "time")
        self.assertField(self.booking(consent=False), "consent")
        self.assertField(self.booking(idempotencyKey="x"), "idempotencyKey")

    def test_today_past_time_rejected(self):
        now = datetime.now(ZoneInfo(TZ))
        if now.hour < 9 or (now.hour == 9 and now.minute < 1):
            self.skipTest("no past slot today yet")
        self.assertField(self.booking(date=now.date().isoformat(), time="09:00"), "time")

    def test_input_is_sanitised(self):
        s, r = self.req("/api/book-appointment", self.booking(name="  <b>Ann</b>\x00\x07  Smith  ", message="hi\x1b[31m"))
        self.assertEqual(s, 201, r)
        row = server.Handler.app.db.get_appointment(r["ref"])
        self.assertEqual(row["patient_name"], "<b>Ann</b> Smith")  # stored raw-but-clean; escaped on output
        self.assertNotIn("\x1b", row["message"])
        clinic = [m for m in self.outbox() if r["ref"] in str(m["Subject"]) and m["To"] in CLINIC][0]
        self.assertIn("&lt;b&gt;Ann&lt;/b&gt;", clinic.get_body(("html",)).get_content())

    def test_spam_protection(self):
        s, _ = self.req("/api/book-appointment", self.booking(website="http://spam"))
        self.assertEqual(s, 400)
        s, _ = self.req("/api/book-appointment", self.booking(elapsedMs=300))
        self.assertEqual(s, 400)

    def test_cross_origin_rejected_and_bad_requests(self):
        s, _ = self.req("/api/book-appointment", self.booking(), headers={"Origin": "https://evil.example"})
        self.assertEqual(s, 403)
        s, _ = self.req("/api/book-appointment", None, method="POST", headers={"Content-Type": "text/plain"})
        self.assertEqual(s, 415)
        r = urllib.request.Request(self.base + "/api/book-appointment", data=b"{not json", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r)
        self.assertEqual(cm.exception.code, 400)

    def test_logs_do_not_contain_patient_data(self):
        self.req("/api/book-appointment", self.booking(email="secret.person@example.test", phone="+383 44 999 888", name="Zyxwv Private"))
        logs = self.log_buf.getvalue()
        self.assertNotIn("secret.person@example.test", logs)
        self.assertNotIn("Zyxwv", logs)
        self.assertNotIn("999 888", logs)

    def test_contact_form(self):
        s, r = self.req("/api/contact", {"idempotencyKey": "contactkey000000000001", "name": "Mock Sender", "email": "sender@example.test",
                                         "subject": "Question", "message": "This is a mock message.", "website": "", "elapsedMs": 9000})
        self.assertEqual(s, 201, r)
        self.assertEqual(r["email"]["clinic"], "outbox")
        s, r = self.req("/api/contact", {"idempotencyKey": "contactkey000000000002", "name": "M", "email": "bad", "subject": "", "message": "short"})
        self.assertEqual(s, 422)
        self.assertEqual(set(r["fields"]), {"name", "email", "subject", "message"})


class AdminTests(ServerCase):
    def opener(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def test_admin_requires_auth(self):
        for p in ("/api/admin/appointments", "/api/admin/email-status", "/api/admin/email-log", "/api/admin/preview/patient_ack"):
            self.assertEqual(self.req(p)[0], 401, p)
        self.assertEqual(self.req("/api/admin/test-email", {"to": "x@example.test"})[0], 401)
        self.assertEqual(self.req("/api/admin/login", {"token": "wrong-token-wrong-token"})[0], 401)
        forged = {"Cookie": "qd_admin=9999999999.abcd.deadbeef"}
        self.assertEqual(self.req("/api/admin/appointments", headers=forged)[0], 401)

    def test_admin_flow(self):
        o = self.opener()
        s, _ = self.req("/api/admin/login", {"token": ADMIN_TOKEN}, opener=o)
        self.assertEqual(s, 200)
        s, st = self.req("/api/admin/email-status", opener=o)
        self.assertEqual(s, 200)
        self.assertNotIn("password", json.dumps(st).lower().replace("passwordset", ""))
        self.assertEqual(st["clinicRecipients"], CLINIC)
        s, r = self.req("/api/book-appointment", self.booking())
        ref = r["ref"]
        s, d = self.req(f"/api/admin/appointments/{ref}", opener=o)
        self.assertEqual(s, 200)
        self.assertEqual(len(d["emails"]), 4)
        s, _ = self.req(f"/api/admin/appointments/{ref}/status", {"status": "confirmed"}, opener=o)
        self.assertEqual(s, 200)
        self.assertEqual(server.Handler.app.db.get_appointment(ref)["status"], "confirmed")
        self.assertEqual(self.req(f"/api/admin/appointments/{ref}/status", {"status": "hacked"}, opener=o)[0], 422)
        s, t = self.req("/api/admin/test-email", {"to": "admin-test@example.test"}, opener=o)
        self.assertEqual((s, t["status"]), (200, "outbox"))
        s, html = self.req("/api/admin/preview/clinic_notify", opener=o)
        self.assertEqual(s, 200)
        self.assertIn(b"New appointment request", html)
        s, _ = self.req("/api/admin/logout", {}, opener=o)
        self.assertEqual(self.req("/api/admin/appointments", opener=o)[0], 401)


class SmtpFailureTests(ServerCase):
    """SMTP configured but unreachable: the request is still saved, and statuses say 'failed'."""
    backend = "smtp"
    smtp_port = 1  # nothing listens here

    def test_provider_failure_is_reported_honestly_and_retry_is_safe(self):
        body = self.booking()
        s, r = self.req("/api/book-appointment", body)
        self.assertEqual(s, 201)
        self.assertEqual(r["email"], {"patient": "failed", "clinic": "failed"})
        db = server.Handler.app.db
        self.assertIsNotNone(db.get_appointment(r["ref"]))
        # Resubmitting the same request re-attempts unsent mail but does not duplicate the booking.
        s2, r2 = self.req("/api/book-appointment", body)
        self.assertEqual((s2, r2["ref"], r2["created"]), (200, r["ref"], False))
        attempts = db.email_attempts_for(r["ref"])
        self.assertEqual(len(attempts), 4)
        self.assertTrue(all(a["attempts"] == 2 and a["status"] == "failed" for a in attempts))


class NotConfiguredTests(ServerCase):
    backend = "disabled"

    def test_not_configured_status(self):
        s, r = self.req("/api/book-appointment", self.booking())
        self.assertEqual(s, 201)
        self.assertEqual(r["email"], {"patient": "not_configured", "clinic": "not_configured"})


class RateLimitTests(ServerCase):
    rate = 3

    def test_rate_limit(self):
        codes = [self.req("/api/book-appointment", self.booking())[0] for _ in range(4)]
        self.assertEqual(codes, [201, 201, 201, 429])


class SmtpAcceptTests(ServerCase):
    """Real SMTP conversation against a local in-process SMTP sink (no external delivery)."""
    backend = "smtp"

    @classmethod
    def setUpClass(cls):
        import socket
        import socketserver
        cls.received = []

        class SMTPSink(socketserver.StreamRequestHandler):
            def handle(self):
                w = lambda s: self.wfile.write((s + "\r\n").encode())
                w("220 sink ready")
                rcpt, data_mode, buf = [], False, []
                for raw in self.rfile:
                    line = raw.decode(errors="replace").rstrip("\r\n")
                    if data_mode:
                        if line == ".":
                            cls.received.append({"rcpt": list(rcpt), "data": "\n".join(buf)})
                            rcpt, buf, data_mode = [], [], False
                            w("250 queued")
                        else:
                            buf.append(line)
                        continue
                    cmd = line.upper()
                    if cmd.startswith("EHLO") or cmd.startswith("HELO"): w("250 sink")
                    elif cmd.startswith("MAIL FROM"): w("250 ok")
                    elif cmd.startswith("RCPT TO"): rcpt.append(line.split(":", 1)[1].strip(" <>")); w("250 ok")
                    elif cmd == "DATA": data_mode = True; w("354 go")
                    elif cmd == "QUIT": w("221 bye"); return
                    else: w("250 ok")

        cls.sink = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SMTPSink)
        cls.sink.daemon_threads = True
        cls.smtp_port = cls.sink.server_address[1]
        threading.Thread(target=cls.sink.serve_forever, daemon=True).start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.sink.shutdown(); cls.sink.server_close()

    def test_accepted_and_envelope_recipients_are_separate(self):
        s, r = self.req("/api/book-appointment", self.booking(email="envelope@example.test"))
        self.assertEqual(s, 201)
        self.assertEqual(r["email"], {"patient": "accepted", "clinic": "accepted"})
        mine = [m for m in self.received if r["ref"] in m["data"]]
        self.assertEqual(len(mine), 4)
        envelopes = sorted(tuple(m["rcpt"]) for m in mine)
        self.assertEqual(envelopes, sorted([("envelope@example.test",)] + [(a,) for a in CLINIC]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
