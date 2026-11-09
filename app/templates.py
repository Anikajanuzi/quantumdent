"""Email templates — each returns (subject, plain_text, html). All dynamic values are escaped."""
from __future__ import annotations

from datetime import date
from html import escape as h

CLINIC = "Quantum Dental Clinic & Implant Center"
PHONE = "+383 49 536 944"

_WRAP = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#FAF5EE;font-family:Helvetica,Arial,sans-serif;color:#2B2A27;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF5EE;padding:32px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border:1px solid #D5D0C8;border-radius:14px;">
<tr><td style="padding:28px 32px 8px 32px;border-bottom:1px solid #ECE4DA;">
<div style="font-family:Georgia,'Times New Roman',serif;font-size:20px;letter-spacing:.2px;">Quantum Dental</div>
<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#777B67;margin:4px 0 16px;">Clinic &amp; Implant Center</div>
</td></tr>
<tr><td style="padding:28px 32px;font-size:15px;line-height:1.6;">{body}</td></tr>
<tr><td style="padding:18px 32px 26px;border-top:1px solid #ECE4DA;font-size:12px;line-height:1.6;color:#6b675f;">{footer}</td></tr>
</table></td></tr></table></body></html>"""


def _rows(pairs: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:8px 0;color:#777B67;font-size:13px;width:42%;vertical-align:top;">{h(k)}</td>'
        f'<td style="padding:8px 0;font-size:14px;vertical-align:top;">{h(v)}</td></tr>' for k, v in pairs)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-top:1px solid #ECE4DA;border-bottom:1px solid #ECE4DA;margin:18px 0;">{cells}</table>')


def _text_rows(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"  {k}: {v}" for k, v in pairs)


def fmt_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%A, %d %B %Y")
    except ValueError:
        return iso


def patient_ack(appt: dict, specialist_name: str) -> tuple[str, str, str]:
    first = appt["patient_name"].split(" ")[0]
    pairs = [("Request reference", appt["ref"]), ("Dentist", specialist_name),
             ("Preferred date", fmt_date(appt["preferred_date"])), ("Preferred time", appt["preferred_time"]),
             ("Status", "Pending confirmation")]
    subject = f"We received your appointment request — {appt['ref']}"
    text = (f"Dear {first},\n\n"
            f"Thank you for contacting {CLINIC}. We have received your appointment request.\n\n"
            f"{_text_rows(pairs)}\n\n"
            "Please note: this is a REQUEST, not a confirmed appointment. The clinic will contact you to "
            "confirm a time or suggest an alternative.\n\n"
            f"If you need to change or cancel your request, please call us on {PHONE} and quote your reference.\n\n"
            f"Kind regards,\n{CLINIC}\n{PHONE}\n")
    body = (f'<p style="margin:0 0 14px;">Dear {h(first)},</p>'
            f'<p style="margin:0 0 6px;">Thank you for contacting {h(CLINIC)}. We have received your appointment request.</p>'
            f'{_rows(pairs)}'
            '<p style="margin:0 0 14px;padding:12px 14px;background:#ECE4DA;border-radius:10px;font-size:14px;">'
            '<strong>This is a request, not a confirmed appointment.</strong> The clinic will contact you to confirm '
            'a time or suggest an alternative.</p>'
            f'<p style="margin:0;">To change or cancel your request, call <a href="tel:+38349536944" '
            f'style="color:#BD6542;">{PHONE}</a> and quote your reference.</p>')
    footer = (f"{h(CLINIC)} · {PHONE}<br>You are receiving this email because this address was entered in "
              "an appointment request on our website. If this wasn't you, please ignore this message.")
    return subject, text, _WRAP.format(title=h(subject), body=body, footer=footer)


def clinic_notify(appt: dict, specialist_name: str, reason_label: str, review_url: str) -> tuple[str, str, str]:
    pairs = [("Reference", appt["ref"]), ("Patient", appt["patient_name"]), ("Email", appt["patient_email"]),
             ("Phone", appt["patient_phone"]), ("Requested dentist", specialist_name),
             ("Reason category", reason_label), ("Preferred date", fmt_date(appt["preferred_date"])),
             ("Preferred time", appt["preferred_time"]),
             ("Travelling patient", "Yes" if appt["traveling"] else "No")]
    note = ("The patient added a note. For privacy it is not included in this email — open the staff dashboard to read it."
            if appt.get("message") else "No additional note was added.")
    subject = f"New appointment request {appt['ref']} — {fmt_date(appt['preferred_date'])} {appt['preferred_time']}"
    text = (f"New appointment request received via the website.\n\n{_text_rows(pairs)}\n\n{note}\n\n"
            f"Review in the staff dashboard (login required):\n{review_url}\n\n"
            "Status: pending — the patient has been told the clinic will confirm. Reply to this email to "
            "respond to the patient directly.\n")
    body = ('<p style="margin:0 0 6px;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#BD6542;">'
            'New appointment request</p>'
            f'<p style="margin:0;">A patient submitted a request through the website.</p>{_rows(pairs)}'
            f'<p style="margin:0 0 18px;font-size:14px;color:#55524c;">{h(note)}</p>'
            f'<p style="margin:0 0 18px;"><a href="{h(review_url)}" style="display:inline-block;background:#BD6542;'
            'color:#FFFFFF;text-decoration:none;padding:12px 20px;border-radius:999px;font-size:14px;">'
            'Review in staff dashboard</a></p>'
            '<p style="margin:0;font-size:13px;color:#55524c;">Status: pending. The patient has been told the clinic '
            'will confirm. Reply to this email to respond to the patient directly.</p>')
    footer = "Internal notification — staff only. Login required to view full request details."
    return subject, text, _WRAP.format(title=h(subject), body=body, footer=footer)


def contact_notify(msg: dict, review_url: str) -> tuple[str, str, str]:
    pairs = [("Reference", msg["ref"]), ("Name", msg["name"]), ("Email", msg["email"]), ("Subject", msg["subject"])]
    subject = f"Website message {msg['ref']}: {msg['subject'][:80]}"
    text = (f"New message from the website contact form.\n\n{_text_rows(pairs)}\n\nMessage:\n{msg['message']}\n\n"
            f"Staff dashboard: {review_url}\nReply to this email to respond to the sender.\n")
    msg_html = h(msg["message"]).replace("\n", "<br>")
    body = ('<p style="margin:0 0 6px;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#BD6542;">'
            f'Website message</p>{_rows(pairs)}'
            f'<div style="padding:14px 16px;background:#FAF5EE;border-radius:10px;font-size:14px;">{msg_html}</div>'
            '<p style="margin:16px 0 0;font-size:13px;color:#55524c;">Reply to this email to respond to the sender.</p>')
    return subject, text, _WRAP.format(title=h(subject), body=body, footer="Internal notification — staff only.")


def test_email(recipient_note: str) -> tuple[str, str, str]:
    subject = "Quantum Dental — email configuration test"
    text = ("This is a test message from the Quantum Dental website.\n\n"
            "If you received it, outgoing email is working for this address. No patient data is included.\n"
            f"{recipient_note}\n")
    body = ('<p style="margin:0 0 12px;">This is a test message from the Quantum Dental website.</p>'
            '<p style="margin:0;">If you received it, outgoing email is working for this address. '
            f'No patient data is included.</p><p style="margin:12px 0 0;color:#777B67;font-size:13px;">{h(recipient_note)}</p>')
    return subject, text, _WRAP.format(title=h(subject), body=body, footer="Administrative test message.")
