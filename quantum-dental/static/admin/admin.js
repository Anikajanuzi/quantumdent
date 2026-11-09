/* Staff dashboard. All data comes from authenticated /api/admin/* endpoints. */
import { esc, icon, $, $$, api, validEmail } from "/static/js/ui.js";

const main = $("#admin-main");
const tabs = $("[data-tabs]");
const logoutBtn = $("[data-logout]");
const STATUSES = ["pending", "contacted", "confirmed", "declined", "cancelled"];
const pill = (s) => {
  const cls = { accepted: "ok", outbox: "warn", not_configured: "warn", failed: "error", sending: "warn",
    pending: "pending", contacted: "warn", confirmed: "ok", declined: "error", cancelled: "error" }[s] || "warn";
  return `<span class="status-pill status-pill--${cls}">${esc(s.replace("_", " "))}</span>`;
};
const when = (isoStr) => isoStr ? new Date(isoStr).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "";

async function authed(path, opts) {
  try { return await api(path, opts); }
  catch (e) { if (e.status === 401) { showLogin(); throw Object.assign(e, { handled: true }); } throw e; }
}

function showLogin(msg = "") {
  tabs.hidden = true; logoutBtn.hidden = true;
  main.innerHTML = `<div class="card login stack">
    <h1 class="h2">Staff sign in</h1>
    <p class="muted small">Enter the dashboard access token configured on the server (<code>ADMIN_TOKEN</code>).</p>
    <form class="form" data-login novalidate>
      <div class="field"><label class="field__label" for="token">Access token</label>
        <input class="input" id="token" name="token" type="password" autocomplete="current-password" required></div>
      <div data-alert aria-live="assertive">${msg ? `<div class="notice notice--error" role="alert">${icon("alert")}<p>${esc(msg)}</p></div>` : ""}</div>
      <button class="btn btn--primary" type="submit">Sign in</button>
    </form></div>`;
  const form = $("[data-login]", main);
  form.elements.token.focus();
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("button", form); btn.classList.add("is-loading"); btn.disabled = true;
    try {
      await api("/api/admin/login", { method: "POST", body: { token: form.elements.token.value } });
      route();
    } catch (err) {
      $("[data-alert]", form).innerHTML = `<div class="notice notice--error" role="alert">${icon("alert")}<p>${esc(err.message)}</p></div>`;
      btn.classList.remove("is-loading"); btn.disabled = false;
    }
  });
}

function setTab(name) {
  tabs.hidden = false; logoutBtn.hidden = false;
  $$("[data-tab]", tabs).forEach((a) => a.dataset.tab === name ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
}

/* ---------- Appointments ---------- */
async function appointments() {
  setTab("appointments");
  main.innerHTML = `<div class="skeleton" style-skel></div>`;
  const { items } = await authed("/api/admin/appointments");
  main.innerHTML = `<div class="toolbar"><h1 class="h2">Appointment requests</h1>
    <div class="chips" role="group" aria-label="Filter by status">${["all", ...STATUSES].map((s, i) => `<button class="chip" data-f="${s}" aria-pressed="${i === 0}">${s}</button>`).join("")}</div></div>
    <div class="table-wrap"><table class="data"><thead><tr><th>Reference</th><th>Patient</th><th>Preferred</th><th>Dentist</th><th>Status</th><th>Received</th></tr></thead>
    <tbody data-rows></tbody></table></div>`;
  const draw = (f) => {
    const list = items.filter((a) => f === "all" || a.status === f);
    $("[data-rows]", main).innerHTML = list.length ? list.map((a) => `<tr data-ref="${esc(a.ref)}" tabindex="0">
      <td class="mono">${esc(a.ref)}</td><td>${esc(a.patient_name)}<br><span class="small muted">${esc(a.patient_phone)}</span></td>
      <td>${esc(a.preferred_date)} ${esc(a.preferred_time)}</td><td>${esc(a.specialist_id)}</td><td>${pill(a.status)}</td><td class="small">${when(a.created_at)}</td></tr>`).join("")
      : `<tr class="empty-row"><td colspan="6">No requests${f === "all" ? " yet" : ` with status “${f}”`}.</td></tr>`;
  };
  draw("all");
  $$("[data-f]", main).forEach((b) => b.addEventListener("click", () => { $$("[data-f]", main).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(b.dataset.f); }));
  $("[data-rows]", main).addEventListener("click", (e) => { const r = e.target.closest("[data-ref]"); if (r) location.hash = `#/appointments/${r.dataset.ref}`; });
  $("[data-rows]", main).addEventListener("keydown", (e) => { const r = e.target.closest("[data-ref]"); if (r && e.key === "Enter") location.hash = `#/appointments/${r.dataset.ref}`; });
}

async function appointmentDetail(ref) {
  setTab("appointments");
  const { item: a, emails } = await authed(`/api/admin/appointments/${encodeURIComponent(ref)}`);
  const canRetry = emails.some((e) => ["failed", "not_configured"].includes(e.status)) || !emails.length;
  main.innerHTML = `<a class="link-arrow" href="#/appointments">${icon("arrowLeft")} All requests</a>
    <div class="toolbar"><h1 class="h2 mono">${esc(a.ref)}</h1>${pill(a.status)}</div>
    <div class="admin-grid">
      <section class="card stack"><h2 class="h3">Request</h2>
        <dl class="kv">
          <dt>Patient</dt><dd>${esc(a.patient_name)}</dd>
          <dt>Email</dt><dd><a class="text-link" href="mailto:${esc(a.patient_email)}">${esc(a.patient_email)}</a></dd>
          <dt>Phone</dt><dd><a class="text-link" href="tel:${esc(a.patient_phone.replace(/[^+\d]/g, ""))}">${esc(a.patient_phone)}</a></dd>
          <dt>Dentist</dt><dd>${esc(a.specialist_id)}</dd><dt>Reason</dt><dd>${esc(a.reason)}</dd>
          <dt>Preferred</dt><dd>${esc(a.preferred_date)} at ${esc(a.preferred_time)}</dd>
          <dt>Travelling</dt><dd>${a.traveling ? "Yes" : "No"}</dd>
          <dt>Message</dt><dd>${a.message ? esc(a.message) : '<span class="muted">—</span>'}</dd>
          <dt>Received</dt><dd>${when(a.created_at)}</dd><dt>Updated</dt><dd>${when(a.updated_at)}</dd>
        </dl>
        <div class="field"><label class="field__label" for="st">Status</label>
          <div class="btn-row"><select class="select status-select" id="st">${STATUSES.map((s) => `<option ${s === a.status ? "selected" : ""}>${s}</option>`).join("")}</select>
          <button class="btn btn--dark btn--sm" data-save>Update status</button></div>
          <p class="small muted">Changing the status here does not email the patient. Contact them directly to confirm.</p>
          <div data-status-msg aria-live="polite"></div></div>
      </section>
      <section class="card stack"><h2 class="h3">Email notifications</h2>
        <p class="small muted">“accepted” means the mail server accepted the message — not that it reached the inbox.</p>
        <div class="table-wrap"><table class="data"><thead><tr><th>Type</th><th>Recipient</th><th>Status</th><th>Tries</th></tr></thead><tbody>
        ${emails.length ? emails.map((e) => `<tr><td>${esc(e.kind)}</td><td class="small">${esc(e.recipient)}</td><td>${pill(e.status)}${e.last_error ? `<br><span class="small muted">${esc(e.last_error)}</span>` : ""}</td><td>${e.attempts}</td></tr>`).join("")
          : `<tr class="empty-row"><td colspan="4">No email attempts recorded.</td></tr>`}</tbody></table></div>
        <div><button class="btn btn--ghost btn--sm" data-retry ${canRetry ? "" : "disabled"}>Retry unsent emails</button>
          <p class="small muted" style-mt-sm>Only failed or unsent messages are retried; accepted ones are never sent twice.</p></div>
        <div data-retry-msg aria-live="polite"></div>
      </section>
    </div>`;
  $("[data-save]", main).addEventListener("click", async (ev) => {
    const btn = ev.currentTarget; btn.classList.add("is-loading");
    try { await authed(`/api/admin/appointments/${a.ref}/status`, { method: "POST", body: { status: $("#st").value } });
      appointmentDetail(ref);
    } catch (e) { if (!e.handled) $("[data-status-msg]", main).innerHTML = `<p class="field__error">${esc(e.message)}</p>`; btn.classList.remove("is-loading"); }
  });
  $("[data-retry]", main).addEventListener("click", async (ev) => {
    const btn = ev.currentTarget; btn.classList.add("is-loading"); btn.disabled = true;
    try { await authed(`/api/admin/appointments/${a.ref}/retry-email`, { method: "POST", body: {} }); appointmentDetail(ref); }
    catch (e) { if (!e.handled) $("[data-retry-msg]", main).innerHTML = `<p class="field__error">${esc(e.message)}</p>`; btn.classList.remove("is-loading"); btn.disabled = false; }
  });
}

/* ---------- Messages ---------- */
async function messages() {
  setTab("messages");
  const { items } = await authed("/api/admin/messages");
  main.innerHTML = `<div class="toolbar"><h1 class="h2">Contact messages</h1></div>
    <div class="table-wrap"><table class="data"><thead><tr><th>Reference</th><th>From</th><th>Subject</th><th>Message</th><th>Received</th></tr></thead><tbody>
    ${items.length ? items.map((m) => `<tr><td class="mono">${esc(m.ref)}</td><td>${esc(m.name)}<br><a class="small text-link" href="mailto:${esc(m.email)}">${esc(m.email)}</a></td>
      <td class="wrap">${esc(m.subject)}</td><td class="wrap">${esc(m.message)}</td><td class="small">${when(m.created_at)}</td></tr>`).join("")
      : `<tr class="empty-row"><td colspan="5">No messages yet.</td></tr>`}</tbody></table></div>`;
}

/* ---------- Email settings ---------- */
async function email() {
  setTab("email");
  const [s, log] = await Promise.all([authed("/api/admin/email-status"), authed("/api/admin/email-log")]);
  const backendNote = { smtp: s.ready ? "SMTP configured" : "SMTP selected but host or sender is missing", outbox: "Development outbox — emails are written to var/outbox and NOT sent", disabled: "Email sending is disabled" }[s.backend] || s.backend;
  main.innerHTML = `<div class="toolbar"><h1 class="h2">Email</h1>${s.ready ? pill(s.backend === "smtp" ? "accepted" : "outbox").replace(/accepted|outbox/, s.backend === "smtp" ? "ready" : "dev outbox") : pill("not_configured")}</div>
    <div class="admin-grid">
      <section class="card stack"><h2 class="h3">Configuration</h2>
        <dl class="kv">
          <dt>Mode</dt><dd>${esc(backendNote)}</dd>
          <dt>SMTP host</dt><dd>${esc(s.smtp.host || "—")}:${esc(s.smtp.port)} (${esc(s.smtp.security)})</dd>
          <dt>Username</dt><dd>${esc(s.smtp.username || "—")}</dd>
          <dt>Password</dt><dd>${s.smtp.passwordSet ? "Set (hidden)" : "Not set"}</dd>
          <dt>Sender</dt><dd>${esc(s.from || "—")}</dd>
          <dt>Reply-To (patients)</dt><dd>${esc(s.replyTo || s.from || "—")}</dd>
          <dt>Clinic recipients</dt><dd>${s.clinicRecipients.length ? s.clinicRecipients.map(esc).join("\n") : "None configured"}</dd>
          <dt>Sender verification</dt><dd>${esc(s.senderVerification)}</dd>
          <dt>Last attempt</dt><dd>${s.lastAttempt ? `${esc(s.lastAttempt.kind)} → ${pill(s.lastAttempt.status)} <span class="small muted">${when(s.lastAttempt.updated_at)}</span>` : "—"}</dd>
        </dl>
        <p class="small muted">Settings are changed in the server's <code>.env</code> file and require a restart. Secrets are never shown here.</p>
      </section>
      <section class="card stack"><h2 class="h3">Send a test email</h2>
        <p class="small muted">Sends a message with no patient data.</p>
        <form class="form" data-test novalidate>
          <div class="field"><label class="field__label" for="to">Recipient</label>
            <input class="input" id="to" name="to" type="email" value="${esc(s.clinicRecipients[0] || "")}" required></div>
          <button class="btn btn--primary" type="submit">Send test email</button>
          <div data-test-result aria-live="polite"></div>
        </form>
      </section>
    </div>
    <section class="stack" style-mt-lg><h2 class="h3">Template previews</h2>
      <div class="chips" role="group" aria-label="Choose template">${[["patient_ack", "Patient acknowledgement"], ["clinic_notify", "Clinic notification"], ["contact_notify", "Contact message"], ["test", "Test email"]]
        .map(([k, l], i) => `<button class="chip" data-tpl="${k}" aria-pressed="${i === 0}">${l}</button>`).join("")}</div>
      <iframe class="preview-frame" title="Email template preview" src="/api/admin/preview/patient_ack" sandbox></iframe>
    </section>
    <section class="stack" style-mt-lg><h2 class="h3">Recent delivery attempts</h2>
      <div class="table-wrap"><table class="data"><thead><tr><th>Source</th><th>Type</th><th>Recipient</th><th>Status</th><th>Tries</th><th>Updated</th></tr></thead><tbody>
      ${log.items.length ? log.items.map((e) => `<tr><td class="mono">${esc(e.source_ref)}</td><td>${esc(e.kind)}</td><td class="small">${esc(e.recipient)}</td><td>${pill(e.status)}${e.last_error ? `<br><span class="small muted">${esc(e.last_error.slice(0, 120))}</span>` : ""}</td><td>${e.attempts}</td><td class="small">${when(e.updated_at)}</td></tr>`).join("")
        : `<tr class="empty-row"><td colspan="6">No attempts yet.</td></tr>`}</tbody></table></div>
    </section>`;
  $$("[data-tpl]", main).forEach((b) => b.addEventListener("click", () => {
    $$("[data-tpl]", main).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $(".preview-frame", main).src = `/api/admin/preview/${b.dataset.tpl}`;
  }));
  const form = $("[data-test]", main);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const out = $("[data-test-result]", form);
    const to = form.elements.to.value.trim();
    if (!validEmail(to)) { out.innerHTML = `<p class="field__error">Enter a valid email address.</p>`; return; }
    const btn = $("button", form); btn.classList.add("is-loading"); btn.disabled = true;
    try {
      const r = await authed("/api/admin/test-email", { method: "POST", body: { to } });
      const msg = { accepted: "Accepted by the mail server. Check the inbox (and spam) to confirm delivery.", outbox: "Written to the development outbox — not actually sent.",
        not_configured: "Not sent: email is not configured.", failed: `Failed: ${r.error}` }[r.status] || r.status;
      out.innerHTML = `<div class="notice ${r.ok ? "notice--success" : "notice--error"}">${icon(r.ok ? "check" : "alert")}<p>${pill(r.status)} ${esc(msg)} <span class="mono small">${esc(r.ref)}</span></p></div>`;
    } catch (err) { if (!err.handled) out.innerHTML = `<p class="field__error">${esc(err.message)}</p>`; }
    finally { btn.classList.remove("is-loading"); btn.disabled = false; }
  });
}

/* ---------- Router ---------- */
async function route() {
  const h = location.hash.replace(/^#\/?/, "");
  const [section, ref] = h.split("/");
  try {
    await authed("/api/admin/session");
    if (section === "messages") await messages();
    else if (section === "email") await email();
    else if (section === "appointments" && ref) await appointmentDetail(decodeURIComponent(ref));
    else await appointments();
    main.focus({ preventScroll: true });
  } catch (e) {
    if (!e.handled) main.innerHTML = `<div class="notice notice--error" role="alert">${icon("alert")}<p>${esc(e.message)}</p></div>`;
  }
}
window.addEventListener("hashchange", route);
logoutBtn.addEventListener("click", async () => { try { await api("/api/admin/logout", { method: "POST", body: {} }); } finally { showLogin(); } });
route();
