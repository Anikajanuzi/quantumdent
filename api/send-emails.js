// Vercel serverless function: sends the appointment / contact emails.
//
// Booking  -> 2 independent emails: (A) acknowledgement to the patient,
//             (B) notification to each clinic address (sent one by one, no CC).
// Contact  -> notification to each clinic address.
//
// Settings (Vercel > Project > Settings > Environment Variables):
//   SMTP_USER      sending Gmail address            (required)
//   SMTP_PASS      Gmail App Password (16 letters)  (required)
//   CLINIC_EMAILS  comma-separated staff addresses  (optional, defaults below)
//   SMTP_HOST / SMTP_PORT                           (optional, default Gmail)
// No database is needed: nothing is stored, the emails are the record.

const nodemailer = require("nodemailer");

const DEFAULT_CLINIC = "ekelmendi27@kla.education,dramaxhiku27@kla.education,ashatrolli27@kla.education";
const CLINIC = "Quantum Dental Clinic & Implant Center";
const PHONE = "+383 49 536 944";
const REASONS = {
  checkup: "Check-up or cleaning", pain: "Tooth pain or discomfort", consultation: "Consultation about a treatment",
  "second-opinion": "Second opinion", "follow-up": "Follow-up visit", other: "Something else",
};
const EMAIL_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
const hits = new Map(); // simple per-instance rate limit

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clean = (v, max, multiline = false) => {
  let s = String(v ?? "").normalize("NFC").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, " ");
  s = multiline ? s.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim() : s.replace(/\s+/g, " ").trim();
  return s.slice(0, max);
};
const validEmail = (v) => EMAIL_RE.test(v) && !v.includes("..") && v.length <= 254;
const validPhone = (v) => /^[+()\-.\s0-9]+$/.test(v) && v.replace(/\D/g, "").length >= 7 && v.replace(/\D/g, "").length <= 15;
const fmtDate = (iso) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
};
const ref = (prefix) => {
  const d = new Date(Date.now() + 3600e3), abc = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
  const p = (n) => String(n).padStart(2, "0");
  let s = ""; for (let i = 0; i < 5; i++) s += abc[Math.floor(Math.random() * abc.length)];
  return `${prefix}-${String(d.getUTCFullYear()).slice(2)}${p(d.getUTCMonth() + 1)}${p(d.getUTCDate())}-${s}`;
};

function wrap(title, body, footer) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title></head>
<body style="margin:0;padding:0;background:#FAF5EE;font-family:Helvetica,Arial,sans-serif;color:#2B2A27;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FAF5EE;padding:32px 12px;"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border:1px solid #D5D0C8;border-radius:14px;">
<tr><td style="padding:28px 32px 8px;border-bottom:1px solid #ECE4DA;"><div style="font-family:Georgia,serif;font-size:20px;">Quantum Dental</div>
<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#777B67;margin:4px 0 16px;">Clinic &amp; Implant Center</div></td></tr>
<tr><td style="padding:28px 32px;font-size:15px;line-height:1.6;">${body}</td></tr>
<tr><td style="padding:18px 32px 26px;border-top:1px solid #ECE4DA;font-size:12px;line-height:1.6;color:#6b675f;">${footer}</td></tr>
</table></td></tr></table></body></html>`;
}
const rows = (pairs) => `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #ECE4DA;border-bottom:1px solid #ECE4DA;margin:18px 0;">${pairs.map(([k, v]) =>
  `<tr><td style="padding:8px 0;color:#777B67;font-size:13px;width:42%;vertical-align:top;">${esc(k)}</td><td style="padding:8px 0;font-size:14px;vertical-align:top;white-space:pre-line;">${esc(v)}</td></tr>`).join("")}</table>`;
const textRows = (pairs) => pairs.map(([k, v]) => `  ${k}: ${v}`).join("\n");

function patientEmail(b) {
  const pairs = [["Request reference", b.ref], ["Dentist", b.dentist], ["Preferred date", fmtDate(b.date)], ["Preferred time", b.time], ["Status", "Pending confirmation"]];
  const first = b.name.split(" ")[0];
  const subject = `We received your appointment request — ${b.ref}`;
  const text = `Dear ${first},\n\nThank you for contacting ${CLINIC}. We have received your appointment request.\n\n${textRows(pairs)}\n\n` +
    `Please note: this is a REQUEST, not a confirmed appointment. The clinic will contact you to confirm a time or suggest an alternative.\n\n` +
    `To change or cancel your request, call ${PHONE} and quote your reference.\n\nKind regards,\n${CLINIC}\n${PHONE}\n`;
  const html = wrap(subject,
    `<p style="margin:0 0 14px;">Dear ${esc(first)},</p><p style="margin:0 0 6px;">Thank you for contacting ${esc(CLINIC)}. We have received your appointment request.</p>${rows(pairs)}` +
    `<p style="margin:0 0 14px;padding:12px 14px;background:#ECE4DA;border-radius:10px;font-size:14px;"><strong>This is a request, not a confirmed appointment.</strong> The clinic will contact you to confirm a time or suggest an alternative.</p>` +
    `<p style="margin:0;">To change or cancel your request, call <a href="tel:+38349536944" style="color:#BD6542;">${PHONE}</a> and quote your reference.</p>`,
    `${esc(CLINIC)} · ${PHONE}<br>You are receiving this email because this address was entered in an appointment request on our website.`);
  return { subject, text, html };
}

function clinicEmail(b) {
  const pairs = [["Reference", b.ref], ["Patient", b.name], ["Email", b.email], ["Phone", b.phone], ["Requested dentist", b.dentist],
    ["Reason", REASONS[b.reason] || b.reason], ["Preferred date", fmtDate(b.date)], ["Preferred time", b.time],
    ["Travelling patient", b.traveling ? "Yes" : "No"], ["Message", b.message || "—"]];
  const subject = `New appointment request ${b.ref} — ${fmtDate(b.date)} ${b.time}`;
  const text = `New appointment request from the website.\n\n${textRows(pairs)}\n\nStatus: pending — the patient has been told the clinic will confirm.\nReply to this email to answer the patient directly.\n`;
  const html = wrap(subject,
    `<p style="margin:0 0 6px;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#BD6542;">New appointment request</p>` +
    `<p style="margin:0;">A patient submitted a request through the website.</p>${rows(pairs)}` +
    `<p style="margin:0;font-size:13px;color:#55524c;">Status: pending. The patient has been told the clinic will confirm. <strong>Reply to this email</strong> to answer the patient directly.</p>`,
    "Internal notification — clinic staff only.");
  return { subject, text, html };
}

function contactEmail(c) {
  const pairs = [["Reference", c.ref], ["Name", c.name], ["Email", c.email], ["Subject", c.subject], ["Message", c.message]];
  const subject = `Website message ${c.ref}: ${c.subject.slice(0, 80)}`;
  return {
    subject,
    text: `New message from the website contact form.\n\n${textRows(pairs)}\n\nReply to this email to answer the sender.\n`,
    html: wrap(subject, `<p style="margin:0 0 6px;font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#BD6542;">Website message</p>${rows(pairs)}` +
      `<p style="margin:0;font-size:13px;color:#55524c;"><strong>Reply to this email</strong> to answer the sender.</p>`, "Internal notification — clinic staff only."),
  };
}

function validateBooking(p) {
  const e = {};
  const b = {
    name: clean(p.name, 120), email: clean(p.email, 254).toLowerCase(), phone: clean(p.phone, 32),
    dentist: clean(p.dentist, 120) || "First available dentist", reason: clean(p.reason, 40),
    date: clean(p.date, 10), time: clean(p.time, 5), message: clean(p.message, 1000, true), traveling: p.traveling === true,
  };
  if (b.name.length < 2) e.name = "Please enter your full name.";
  if (!validEmail(b.email)) e.email = "Please enter a valid email address, e.g. name@example.com.";
  if (!validPhone(b.phone)) e.phone = "Please enter a valid phone number (7–15 digits, + allowed).";
  if (!REASONS[b.reason]) e.reason = "Please choose a reason for your visit.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(b.date) || isNaN(Date.parse(b.date))) e.date = "Please choose a valid date.";
  else if (b.date < new Date(Date.now() - 12 * 3600e3).toISOString().slice(0, 10)) e.date = "The preferred date cannot be in the past.";
  if (!/^\d{2}:\d{2}$/.test(b.time)) e.time = "Please choose a preferred time.";
  if (p.consent !== true) e.consent = "Please confirm that the clinic may use your details to respond to this request.";
  return [b, e];
}

function validateContact(p) {
  const e = {};
  const c = { name: clean(p.name, 120), email: clean(p.email, 254).toLowerCase(), subject: clean(p.subject, 150), message: clean(p.message, 3000, true) };
  if (c.name.length < 2) e.name = "Please enter your name.";
  if (!validEmail(c.email)) e.email = "Please enter a valid email address, e.g. name@example.com.";
  if (c.subject.length < 2) e.subject = "Please add a subject.";
  if (c.message.length < 10) e.message = "Please write a message of at least 10 characters.";
  return [c, e];
}

async function sendEach(transport, from, jobs) {
  const out = [];
  for (const j of jobs) {
    try {
      const info = await transport.sendMail({ from, to: j.to, replyTo: j.replyTo, subject: j.subject, text: j.text, html: j.html,
        headers: { "Auto-Submitted": "auto-generated" } });
      out.push(info.rejected && info.rejected.length ? "failed" : "accepted");
    } catch (err) {
      console.error("send failed", j.kind, err && err.code);
      out.push("failed");
    }
  }
  return out;
}
const agg = (list) => (!list.length ? null : list.every((s) => s === "accepted") ? "accepted" : list.some((s) => s === "accepted") ? "partial" : "failed");

function createHandler({ transportFactory } = {}) {
  return async function handler(req, res) {
    res.setHeader("Cache-Control", "no-store");
    if (req.method !== "POST") return res.status(405).json({ ok: false, error: "Method not allowed." });

    const user = process.env.SMTP_USER, pass = process.env.SMTP_PASS;
    if (!user || !pass) return res.status(503).json({ ok: false, configured: false, error: "Email is not set up on the server yet." });

    const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0] || "unknown";
    const now = Date.now(), list = (hits.get(ip) || []).filter((t) => now - t < 600e3);
    if (list.length >= 8) return res.status(429).json({ ok: false, error: "Too many requests. Please wait a few minutes or call +383 49 536 944." });
    list.push(now); hits.set(ip, list);

    let p = req.body;
    if (typeof p === "string") { try { p = JSON.parse(p); } catch { p = null; } }
    if (!p || typeof p !== "object") return res.status(400).json({ ok: false, error: "Malformed request." });
    if (clean(p.website, 200) || (typeof p.elapsedMs === "number" && p.elapsedMs < 2500)) {
      return res.status(400).json({ ok: false, error: "Your request could not be submitted. Please try again or call +383 49 536 944." });
    }

    const clinic = (process.env.CLINIC_EMAILS || DEFAULT_CLINIC).split(",").map((s) => s.trim().toLowerCase()).filter(validEmail);
    const transport = (transportFactory || ((o) => nodemailer.createTransport(o)))({
      host: process.env.SMTP_HOST || "smtp.gmail.com", port: Number(process.env.SMTP_PORT || 587),
      secure: Number(process.env.SMTP_PORT || 587) === 465, auth: { user, pass },
    });
    const from = `"${process.env.MAIL_FROM_NAME || CLINIC}" <${process.env.MAIL_FROM || user}>`;

    if (p.type === "contact") {
      const [c, e] = validateContact(p);
      if (Object.keys(e).length) return res.status(422).json({ ok: false, error: "Please check the highlighted fields.", fields: e });
      c.ref = ref("QM");
      const m = contactEmail(c);
      const st = await sendEach(transport, from, clinic.map((to) => ({ kind: "contact_notify", to, replyTo: c.email, ...m })));
      return res.status(200).json({ ok: true, ref: c.ref, email: { clinic: agg(st) } });
    }

    const [b, e] = validateBooking(p);
    if (Object.keys(e).length) return res.status(422).json({ ok: false, error: "Please check the highlighted fields.", fields: e });
    b.ref = ref("QD");
    const pm = patientEmail(b), cm = clinicEmail(b);
    // Email A: patient only (reply goes to the clinic sender). Email B: each clinic address separately (reply goes to the patient).
    const [patient] = await sendEach(transport, from, [{ kind: "patient_ack", to: b.email, replyTo: process.env.MAIL_FROM || user, ...pm }]);
    const clinicSt = await sendEach(transport, from, clinic.map((to) => ({ kind: "clinic_notify", to, replyTo: b.email, ...cm })));
    console.log("booking", b.ref, "patient:", patient, "clinic:", clinicSt.join(","));
    return res.status(200).json({ ok: true, ref: b.ref, status: "pending", date: b.date, time: b.time, email: { patient, clinic: agg(clinicSt) } });
  };
}

module.exports = createHandler();
module.exports.createHandler = createHandler;
