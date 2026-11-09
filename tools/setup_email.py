"""Interactive email setup (run by setup-email.bat).

Asks for the sending account, saves it to .env (the password never leaves this computer),
checks the login with the mail server, and can send a test email (no patient data)."""
from __future__ import annotations

import getpass
import re
import smtplib
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ENV = ROOT / ".env"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

PROVIDERS = {
    "1": ("Gmail / Google Workspace", "smtp.gmail.com", 587, "starttls"),
    "2": ("Outlook / Hotmail / Microsoft 365", "smtp.office365.com", 587, "starttls"),
    "3": ("Other (I'll type the server details)", "", 587, "starttls"),
}


def ask(prompt: str, default: str = "") -> str:
    v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return v or default


def update_env(values: dict[str, str]) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else \
        (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


def current(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    print("\n=== Quantum Dental - email setup ===\n")
    print("Which email service will send the appointment emails?")
    for k, (name, *_r) in PROVIDERS.items():
        print(f"  {k}) {name}")
    choice = ask("Choose 1, 2 or 3", "1")
    name, host, port, security = PROVIDERS.get(choice, PROVIDERS["1"])
    if not host:
        host = ask("SMTP server (e.g. smtp.example.com)")
        port = int(ask("Port", "587"))
        security = "ssl" if port == 465 else "starttls"

    while True:
        user = ask("\nSending email address (the account that sends the emails)", current("SMTP_USERNAME"))
        if EMAIL_RE.match(user):
            break
        print("  That doesn't look like an email address - please try again.")

    if choice == "1":
        print("\nGmail needs an APP PASSWORD (not your normal password):")
        print("  1. Turn on 2-Step Verification:   https://myaccount.google.com/signinoptions/two-step-verification")
        print("  2. Create an app password:        https://myaccount.google.com/apppasswords")
        print("     Name it 'Quantum Dental' and copy the 16-letter code.")
    print("\n(Typing is hidden for privacy. Right-click pastes in this window.)")
    pw = getpass.getpass("Password / app password: ").replace(" ", "").strip()
    if not pw:
        print("No password entered - nothing was changed.")
        return 1

    print(f"\nChecking the login with {host} ...")
    try:
        ctx = ssl.create_default_context()
        if security == "ssl":
            s = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx)
        else:
            s = smtplib.SMTP(host, port, timeout=20)
            s.starttls(context=ctx)
        s.login(user, pw)
        s.quit()
        print("  Login OK.")
    except smtplib.SMTPAuthenticationError:
        print("  The mail server rejected the login. Check the address and (for Gmail) use an APP password.")
        print("  Nothing was changed. Run setup-email again to retry.")
        return 1
    except Exception as e:  # network, firewall, wrong server
        print(f"  Could not connect: {type(e).__name__}: {e}")
        print("  Nothing was changed. Check your internet connection or the server name, then retry.")
        return 1

    staff = current("CLINIC_NOTIFY_EMAILS") or "ekelmendi27@kla.education,dramaxhiku27@kla.education,ashatrolli27@kla.education"
    update_env({
        "EMAIL_BACKEND": "smtp",
        "SMTP_HOST": host,
        "SMTP_PORT": str(port),
        "SMTP_SECURITY": security,
        "SMTP_USERNAME": user,
        "SMTP_PASSWORD": pw,
        "MAIL_FROM": user,
        "MAIL_REPLY_TO": user,
        "CLINIC_NOTIFY_EMAILS": staff,
    })
    print("\nSaved. Appointment emails will be sent from", user)
    print("Staff notifications go to:")
    for a in staff.split(","):
        print("  -", a.strip())

    if ask("\nSend a test email (no patient data) to these staff addresses now? (y/n)", "y").lower().startswith("y"):
        from app.config import load_config
        from app.db import Database
        from app.mailer import Mailer
        cfg = load_config(ENV)
        mailer = Mailer(cfg, Database(cfg.db_path))
        for a in staff.split(","):
            r = mailer.send_test(a.strip())
            print(f"  {a.strip()}: {'sent (accepted by the mail server)' if r['status'] == 'accepted' else 'FAILED - ' + r['error']}")
        print("Ask the staff to check their inbox and spam folder.")

    print("\nDone. If the website is running, close its black window and double-click start-website again.")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled - nothing was changed.")
        code = 1
    sys.exit(code)
