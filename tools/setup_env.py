"""Create .env from .env.example for local use (run by start-website.bat). Never overwrites an existing .env."""
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env, example = ROOT / ".env", ROOT / ".env.example"
if env.exists():
    print(".env already exists - leaving it unchanged.")
    raise SystemExit
token = secrets.token_urlsafe(18)
values = {
    "EMAIL_BACKEND": "formsubmit",
    "SMTP_HOST": "",
    "MAIL_FROM": "",
    "CLINIC_NOTIFY_EMAILS": "ajanuzi28@kla.education,ekelmendi27@kla.education,dramaxhiku27@kla.education,ashatrolli27@kla.education",
    "ADMIN_TOKEN": token,
    "SESSION_SECRET": secrets.token_hex(32),
}
lines = []
for line in example.read_text(encoding="utf-8").splitlines():
    key = line.split("=", 1)[0].strip()
    lines.append(f"{key}={values[key]}" if "=" in line and not line.lstrip().startswith("#") and key in values else line)
env.write_text("\n".join(lines) + "\n", encoding="utf-8")
(ROOT / "admin-password.txt").write_text(
    "Staff dashboard: http://127.0.0.1:8000/admin/\n"
    f"Password (ADMIN_TOKEN): {token}\n\n"
    "You can change it in the .env file (ADMIN_TOKEN=...), then restart the website.\n", encoding="utf-8")
print("Created .env (test-email mode) and admin-password.txt")
