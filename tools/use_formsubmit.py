"""Switch the website to FormSubmit emails (run by turn-on-emails.bat)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup_email import current, update_env  # noqa: E402

MAIN = "ajanuzi28@kla.education"  # receives FormSubmit's one-time activation email
others = [a.strip() for a in (current("CLINIC_NOTIFY_EMAILS") or
          "ekelmendi27@kla.education,dramaxhiku27@kla.education,ashatrolli27@kla.education").split(",") if a.strip()]
staff = ",".join([MAIN] + [a for a in others if a.lower() != MAIN])
update_env({"EMAIL_BACKEND": "formsubmit", "CLINIC_NOTIFY_EMAILS": staff})
first = staff.split(",")[0].strip()
print("\nEmails are now ON (sent through FormSubmit).\n")
print("Booking and contact messages go to:")
for a in staff.split(","):
    print("  -", a.strip())
print("Patients get an automatic 'we received your request' reply.\n")
print("IMPORTANT - one-time activation:")
print(f"  1. Restart the website (close its black window, double-click start-website).")
print(f"  2. Send one test booking on the website.")
print(f"  3. FormSubmit emails {first} an 'Activate Form' message - open it and click Activate.")
print("     (Check spam.) After that, every booking and message is delivered.\n")
