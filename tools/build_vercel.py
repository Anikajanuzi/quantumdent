"""Create index.html at the project root for static hosting (Vercel). Run after editing static/index.html."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
for k, v in {"{{TITLE}}": "Quantum Dental Clinic &amp; Implant Center",
             "{{DESCRIPTION}}": "Quantum Dental Clinic &amp; Implant Center. Request an appointment online or call +383 49 536 944.",
             "{{CANONICAL}}": "https://quantumdent.vercel.app/", "{{SITE_URL}}": "https://quantumdent.vercel.app"}.items():
    html = html.replace(k, v)
(ROOT / "index.html").write_text(html, encoding="utf-8")
print("index.html written")
