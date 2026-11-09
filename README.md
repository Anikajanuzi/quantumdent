# Quantum Dental Clinic & Implant Center — website

Single-page website (vanilla HTML/CSS/JS, no build step) served by a standard-library Python server with SQLite storage and SMTP email.

```
server.py              Web server + JSON API (Python 3.11+, no dependencies)
app/                   config, database, validation, email, templates, security
data/specialists.json  VERIFIED dentists only (published on the site)
data/demo_specialists.json  Development-only demo profiles (DEMO_DATA=1)
static/                Public site (index.html, css/, js/) and staff dashboard (admin/)
static/js/content.js   Photos, treatments, results, prices, FAQs
tests/                 API tests (unittest) and browser tests (Playwright)
var/                   Database and dev outbox (created automatically, git-ignored)
```

## Run locally

```bash
cp .env.example .env        # then edit .env
python3 server.py           # http://127.0.0.1:8000   staff dashboard: /admin/
```

For local work set `EMAIL_BACKEND=outbox`: emails are written to `var/outbox/*.eml` instead of being sent.

## Email setup

Set in `.env` (never commit it):

| Variable | Purpose |
|---|---|
| `EMAIL_BACKEND` | `smtp` to send, `outbox` for development, `disabled` to store requests only |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` | e.g. `smtp.gmail.com`, `587`, `starttls` (or `465` + `ssl`) |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Provider credentials. **Gmail / Google Workspace:** use an App Password (requires 2-Step Verification) |
| `MAIL_FROM` | Sender address — must be allowed by the provider (SPF/DKIM set up for its domain) |
| `MAIL_REPLY_TO` | Clinic inbox that receives patient replies (defaults to `MAIL_FROM`) |
| `CLINIC_NOTIFY_EMAILS` | Staff who receive notifications, comma-separated. Each gets a **separate** message |

On every valid appointment request the server sends:

* **Patient acknowledgement** → only the patient. Says the request is *pending confirmation*, with reference, dentist, preferred date/time and the clinic phone. Reply-To = clinic inbox.
* **Clinic notification** → each address in `CLINIC_NOTIFY_EMAILS` (plus a specialist's `notify_email`, if set in `specialists.json`). Contains patient contact details and a link to the staff dashboard. The patient's free-text note is *not* emailed; staff read it in the dashboard. Reply-To = patient.

No CC/BCC mixing. Each attempt is logged per recipient with status `accepted` (SMTP server accepted it — not proof of inbox delivery), `failed`, `not_configured` or `outbox`. Resubmitting the same request (same idempotency key) never creates a second booking and never re-sends a message that was already accepted; staff can retry failed messages from the dashboard.

After configuring SMTP, open `/admin/` → **Email** → *Send test email* to each staff address and confirm it arrives (check spam).

## Staff dashboard (`/admin/`)

Sign in with `ADMIN_TOKEN` (min. 16 characters). Shows appointment requests (with status: pending / contacted / confirmed / declined / cancelled), contact messages, email configuration (secrets hidden), a test-email button, template previews and the delivery log. Sessions are signed HttpOnly, SameSite=Strict cookies (8 hours).

Changing a status does **not** email the patient — staff confirm with the patient directly.

## Adding real clinic content

Everything unverified is shown as clearly labelled placeholders. To publish real information:

* **Photos:** the six interior images in `static/img/clinic/` (`reception`, `hallway`, `walnut`, `doors`, `curves`, `limewash`.jpg) are interim **illustrations** made by `tools/make_illustrations.py`, and the site labels them "Illustration". To use real photos, overwrite each file with a photo of the same name (about 1200×1500, portrait, ≤ 300 KB), update `width`/`height`, and set `illustration: false` for that slot in `PHOTOS` in `static/js/content.js`. Dentist portraits are deliberately *not* generated.
* **Dentists:** add entries to `data/specialists.json`:
  ```json
  { "id": "dr-firstname-lastname", "name": "Dr. Full Name", "title": "Dentist",
    "specialty": "Implantology", "qualifications": ["DMD, University …"],
    "bio": "Short verified biography.", "appointment_types": ["Consultation"],
    "photo": "/static/img/staff/firstname.jpg", "treatments": ["dental-implants"],
    "notify_email": "optional-private@clinic.example" }
  ```
  `notify_email` is never sent to the browser.
* **Treatments:** set `verified: true` on treatments the clinic confirms in `content.js` (removes the "to be confirmed" notices once all are verified); delete any not offered.
* **Address / hours / map:** in `app/content.py` → `public_site_config()` (`address`, `hours`, `mapUrl`), and the footer in `static/index.html`. Adjust `PREFERRED_TIMES` to the real opening hours.
* **Prices / results:** fill `PRICES` / `RESULTS` in `content.js` (results only with written patient consent).
* When everything is verified, set `DRAFT_BANNER=0`. Keep `DEMO_DATA=0` in production.
* The privacy notice (`/privacy`) is a draft for the clinic to review.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_api.py" -v     # 16 API tests
pip install playwright && python3 -m playwright install chromium
python3 tests/test_e2e.py                                      # 13 browser checks, screenshots in tests/artifacts/
```

Tests use temporary databases, `example.test` addresses and a local SMTP sink — no real email is sent.

## Deploying

1. A small Linux server (or any host that runs Python 3.11+). Copy the project, create `.env` with real values, `SITE_URL=https://your-domain`, `HOST=127.0.0.1`, `TRUST_PROXY=1`.
2. Run `python3 server.py` under systemd (or similar) so it restarts automatically.
3. Put a reverse proxy (Caddy or nginx) in front for HTTPS and compression; it forwards to `127.0.0.1:8000`.
4. Back up `var/quantum.sqlite3` regularly — it contains patient contact details. For several app servers, move to PostgreSQL.
5. Rate limits are in-memory per process; behind a proxy, `TRUST_PROXY=1` makes them per client IP.

## Security notes

Server-side validation and sanitisation; honeypot + minimum fill-time spam checks; per-IP rate limits; same-origin checks on every POST (no CORS); strict Content-Security-Policy and security headers; 16 KB request limit; logs contain request references and masked addresses only; SMTP credentials and staff addresses never reach the browser; admin endpoints require a signed session.
