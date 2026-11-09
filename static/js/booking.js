/* Multi-step appointment request. Preferred date/time only — never a confirmed reservation. */
import { TREATMENTS } from "./content.js";
import { esc, icon, photo, $, $$, api, newKey, fieldError, validEmail, validPhone, fmtDate, clinicNow, toast, sendFormSubmit, localRef } from "./ui.js";

const STEPS = ["Dentist", "Date & time", "Your details", "Review", "Submitted"];
const pad = (n) => String(n).padStart(2, "0");
const iso = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`;

export function booking(ctx) {
  const cfg = ctx.config;
  const q = ctx.query;
  const st = {
    step: 1, specialistId: "", date: "", time: "", name: "", email: "", phone: "", reason: "", message: "",
    traveling: q.get("traveling") === "1", consent: false, key: newKey(), submitting: false, result: null,
    started: performance.now(), cal: null, errors: {},
  };
  const pre = q.get("specialist");
  if (pre && cfg.specialists.some((s) => s.id === pre)) { st.specialistId = pre; st.step = 2; }
  const topic = TREATMENTS.find((t) => t.slug === q.get("topic"));
  if (topic) { st.reason = "consultation"; st.message = `Consultation about: ${topic.name}`; }

  const named = cfg.specialists.filter((s) => !s.generic);
  const spName = (id) => cfg.specialists.find((s) => s.id === id)?.name || "";
  const reasonLabel = (id) => cfg.reasons.find((r) => r.id === id)?.label || "";

  return {
    html: `
    <section class="page-hero"><div class="container"><div class="page-hero__inner">
      <span class="eyebrow reveal">Booking</span>
      <h1 class="h1 reveal">Request an appointment</h1>
      <p class="lead reveal">Choose a dentist and your preferred time. The clinic will contact you to confirm — your appointment isn't booked until they do.</p>
    </div></div></section>
    <section class="section section--tight"><div class="container booking">
      <div class="card" data-booking>
        <ol class="stepper" data-stepper aria-label="Booking progress"></ol>
        <div data-step-body></div>
      </div>
      <aside class="summary no-print" aria-label="Your request">
        ${photo("reception", { ratio: "16-10", reveal: false })}
        <div class="card">
          <p class="info-list__label">Your request</p>
          <dl class="summary__list" data-summary></dl>
        </div>
        <div class="notice">${icon("info")}<p>This is a <strong>request</strong>, not a confirmed booking. Prefer to talk? Call <a class="text-link" href="tel:+38349536944">049-536-944</a>.</p></div>
      </aside>
    </div></section>`,

    mount(root) {
      const body = $("[data-step-body]", root);
      const stepper = $("[data-stepper]", root);
      const summary = $("[data-summary]", root);

      /* ---------------- shared ---------------- */
      const validStep = (n) => {
        if (n === 1) return !!st.specialistId;
        if (n === 2) return !!(st.date && st.time);
        if (n === 3) return !Object.keys(detailErrors()).length;
        return true;
      };
      const maxReachable = () => { let n = 1; while (n < 4 && validStep(n)) n++; return n; };

      function renderStepper() {
        const done = st.result ? 5 : 0;
        stepper.innerHTML = STEPS.map((label, i) => {
          const n = i + 1;
          const current = st.result ? n === 5 : n === st.step;
          const reachable = !st.result && n <= maxReachable() && n <= 4;
          const isDone = done ? n < 5 : n < st.step;
          return `<li><button type="button" class="stepper__btn ${isDone ? "is-done" : ""}" data-goto="${n}" ${current ? 'aria-current="step"' : ""} ${reachable && !current ? "" : "disabled"}
            aria-label="Step ${n} of 5: ${label}${isDone ? " (completed)" : ""}"><span class="stepper__label"><span class="stepper__num">${pad(n)}</span> · ${label}</span></button></li>`;
        }).join("");
      }

      function renderSummary() {
        const row = (k, v) => `<div class="summary__row"><dt>${k}</dt><dd class="${v ? "" : "is-empty"}">${v ? esc(v) : "—"}</dd></div>`;
        summary.innerHTML = row("Dentist", spName(st.specialistId)) + row("Date", st.date ? fmtDate(st.date, { weekday: "short", day: "numeric", month: "short", year: "numeric" }) : "")
          + row("Time", st.time) + row("Reason", reasonLabel(st.reason))
          + `<div class="summary__row"><dt>Status</dt><dd>${st.result ? '<span class="status-pill status-pill--pending">Pending confirmation</span>' : '<span class="muted">Not sent yet</span>'}</dd></div>`;
      }

      function go(n, { focus = true } = {}) {
        st.step = n;
        render();
        if (focus) {
          const h = $(".step__head h2", body);
          h?.setAttribute("tabindex", "-1");
          h?.focus({ preventScroll: true });
          const top = root.querySelector("[data-booking]").getBoundingClientRect().top + window.scrollY - 100;
          if (window.scrollY > top) window.scrollTo({ top, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
        }
      }

      function render() {
        renderStepper();
        renderSummary();
        if (st.result) return renderConfirmation();
        ({ 1: renderSpecialist, 2: renderWhen, 3: renderDetails, 4: renderReview })[st.step]();
      }

      const foot = (back, next, nextLabel = "Continue") => `<div class="step__foot">
        ${back ? `<button type="button" class="btn btn--ghost" data-back>${icon("arrowLeft")} Back</button>` : ""}
        ${next ? `<button type="button" class="btn btn--primary" data-next>${nextLabel} ${icon("arrow", "icon-arrow")}</button>` : ""}</div>`;

      const groupError = (msg) => `<p class="field__error" role="alert" data-group-error>${icon("alert")}<span>${esc(msg)}</span></p>`;

      /* ---------------- step 1 ---------------- */
      function renderSpecialist() {
        body.innerHTML = `<div class="step">
          <div class="step__head"><span class="eyebrow">Step 1 of 5</span><h2 class="h2">Choose a dentist</h2>
            <p class="muted" id="sp-desc">Select who you would like to see. Not sure? Choose “First available dentist”.</p></div>
          <fieldset class="choice-grid" aria-describedby="sp-desc" data-group>
            <legend class="sr-only">Dentist</legend>
            ${cfg.specialists.map((s) => `<label class="choice ${s.generic ? "choice--wide" : ""}">
              <input type="radio" name="specialist" value="${esc(s.id)}" ${st.specialistId === s.id ? "checked" : ""}>
              <span class="choice__avatar">${s.photo ? `<img src="${esc(s.photo)}" alt="">` : icon(s.generic ? "users" : "user")}</span>
              <span class="choice__text"><span class="choice__title">${esc(s.name)} ${s.demo ? '<span class="tag tag--demo">Demo</span>' : ""}</span>
                <span class="choice__sub">${esc(s.specialty || "")}</span></span>
              <span class="choice__check" aria-hidden="true">${icon("check")}</span></label>`).join("")}
          </fieldset>
          ${!named.length ? `<p class="small muted" style-mt>Named dentist profiles will be added once confirmed by the clinic.</p>` : ""}
          ${st.errors.specialistId ? groupError(st.errors.specialistId) : ""}
          ${foot(false, true)}
        </div>`;
        $$("input[name=specialist]", body).forEach((r) => r.addEventListener("change", () => {
          st.specialistId = r.value; delete st.errors.specialistId; $("[data-group-error]", body)?.remove(); renderSummary(); renderStepper();
        }));
        $("[data-next]", body).addEventListener("click", () => {
          if (!st.specialistId) {
            st.errors.specialistId = "Please choose a dentist to continue.";
            renderSpecialist(); $("input[name=specialist]", body).focus(); return;
          }
          go(2);
        });
      }

      /* ---------------- step 2 ---------------- */
      function renderWhen() {
        const now = clinicNow(cfg.timezone);
        const [ty, tm] = now.date.split("-").map(Number);
        if (!st.cal) {
          const base = st.date || now.date;
          const [y, m] = base.split("-").map(Number);
          st.cal = { y, m: m - 1 };
        }
        const max = new Date(ty, tm - 1, Number(now.date.slice(8)) + 365);
        const maxIso = iso(max.getFullYear(), max.getMonth(), max.getDate());
        body.innerHTML = `<div class="step">
          <div class="step__head"><span class="eyebrow">Step 2 of 5</span><h2 class="h2">Preferred date &amp; time</h2>
            <p class="muted">Pick when you'd ideally like to come in. This is a preference — the clinic will confirm availability.</p></div>
          <div class="when">
            <div class="calendar" data-calendar></div>
            <div class="times">
              <p class="field__label" id="times-label">Preferred time ${st.date ? `<span class="opt">· ${esc(fmtDate(st.date, { weekday: "short", day: "numeric", month: "short" }))}</span>` : ""}</p>
              <div data-times></div>
              <p class="small muted">${icon("info")} Times are shown in clinic local time. Not a confirmed slot.</p>
            </div>
          </div>
          ${st.errors.date ? groupError(st.errors.date) : ""}${st.errors.time ? groupError(st.errors.time) : ""}
          ${foot(true, true)}
        </div>`;

        const calEl = $("[data-calendar]", body);
        const timesEl = $("[data-times]", body);

        const drawTimes = () => {
          if (!st.date) { timesEl.innerHTML = `<p class="times__empty">Select a date to see time options.</p>`; return; }
          const isToday = st.date === now.date;
          timesEl.innerHTML = `<div class="times__grid" role="group" aria-labelledby="times-label">${cfg.times.map((t) => {
            const past = isToday && t <= now.time;
            return `<button type="button" class="time-chip" data-time="${t}" aria-pressed="${st.time === t}" ${past ? "disabled" : ""} aria-label="${t}${past ? " (passed)" : ""}">${t}</button>`;
          }).join("")}</div>${isToday && cfg.times.every((t) => t <= now.time) ? `<p class="times__empty">No more times today — please choose another date.</p>` : ""}`;
          $$("[data-time]", timesEl).forEach((b) => b.addEventListener("click", () => {
            st.time = b.dataset.time; delete st.errors.time;
            $$("[data-time]", timesEl).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
            $$("[data-group-error]", body).forEach((e) => e.remove());
            renderSummary(); renderStepper();
          }));
        };

        const drawCal = (focusIso) => {
          const { y, m } = st.cal;
          const first = new Date(y, m, 1);
          const offset = (first.getDay() + 6) % 7; // Monday first
          const days = new Date(y, m + 1, 0).getDate();
          const label = first.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
          const prevDisabled = y < ty || (y === ty && m <= tm - 1);
          const nextDisabled = iso(y, m + 1, 1) > maxIso;
          const tabTarget = (st.date && st.date.startsWith(iso(y, m, 1).slice(0, 7))) ? st.date
            : (now.date.startsWith(iso(y, m, 1).slice(0, 7)) ? now.date : iso(y, m, 1));
          let cells = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => `<span class="calendar__dow" aria-hidden="true">${d}</span>`).join("");
          cells += `<span></span>`.repeat(offset);
          for (let d = 1; d <= days; d++) {
            const v = iso(y, m, d);
            const dis = v < now.date || v > maxIso;
            const full = new Date(y, m, d).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
            cells += `<button type="button" class="calendar__day ${v === now.date ? "is-today" : ""}" data-date="${v}" aria-pressed="${st.date === v}"
              aria-label="${full}${v === now.date ? ", today" : ""}${dis ? ", unavailable" : ""}" ${dis ? "disabled" : ""} tabindex="${v === tabTarget && !dis ? 0 : -1}">${d}</button>`;
          }
          calEl.innerHTML = `<div class="calendar__head"><h3 class="calendar__month" aria-live="polite">${label}</h3>
            <div class="calendar__nav"><button type="button" class="icon-btn" data-cal="-1" aria-label="Previous month" ${prevDisabled ? "disabled" : ""}>${icon("chevronLeft")}</button>
            <button type="button" class="icon-btn" data-cal="1" aria-label="Next month" ${nextDisabled ? "disabled" : ""}>${icon("chevronRight")}</button></div></div>
            <div class="calendar__grid" role="group" aria-label="Choose a date, ${label}">${cells}</div>`;
          // ensure some enabled day is tabbable
          if (!$('.calendar__day[tabindex="0"]', calEl)) $(".calendar__day:not(:disabled)", calEl)?.setAttribute("tabindex", "0");
          $$("[data-cal]", calEl).forEach((b) => b.addEventListener("click", () => {
            const nm = new Date(st.cal.y, st.cal.m + Number(b.dataset.cal), 1);
            st.cal = { y: nm.getFullYear(), m: nm.getMonth() };
            drawCal();
            $(`[data-cal="${b.dataset.cal}"]`, calEl)?.focus();
            if ($(`[data-cal="${b.dataset.cal}"]`, calEl)?.disabled) $(`[data-cal]:not(:disabled)`, calEl)?.focus();
          }));
          $$(".calendar__day", calEl).forEach((b) => {
            b.addEventListener("click", () => {
              st.date = b.dataset.date; delete st.errors.date;
              if (st.time && st.date === now.date && st.time <= now.time) st.time = "";
              $$(".calendar__day", calEl).forEach((x) => { x.setAttribute("aria-pressed", String(x === b)); x.tabIndex = x === b ? 0 : -1; });
              $("#times-label", body).innerHTML = `Preferred time <span class="opt">· ${esc(fmtDate(st.date, { weekday: "short", day: "numeric", month: "short" }))}</span>`;
              $$("[data-group-error]", body).forEach((e) => e.remove());
              drawTimes(); renderSummary(); renderStepper();
            });
            b.addEventListener("keydown", (e) => {
              const delta = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
              if (!delta) return;
              e.preventDefault();
              const [yy, mm, dd] = b.dataset.date.split("-").map(Number);
              const t = new Date(yy, mm - 1, dd + delta);
              const v = iso(t.getFullYear(), t.getMonth(), t.getDate());
              if (v < now.date || v > maxIso) return;
              if (t.getMonth() !== st.cal.m || t.getFullYear() !== st.cal.y) { st.cal = { y: t.getFullYear(), m: t.getMonth() }; drawCal(); }
              const target = $(`[data-date="${v}"]`, calEl);
              $$(".calendar__day", calEl).forEach((x) => (x.tabIndex = -1));
              target.tabIndex = 0; target.focus();
            });
          });
          if (focusIso) $(`[data-date="${focusIso}"]`, calEl)?.focus();
        };
        drawCal(); drawTimes();
        $("[data-back]", body).addEventListener("click", () => go(1));
        $("[data-next]", body).addEventListener("click", () => {
          st.errors = {};
          if (!st.date) st.errors.date = "Please choose a preferred date.";
          if (!st.time) st.errors.time = "Please choose a preferred time.";
          if (st.errors.date || st.errors.time) { renderWhen(); ($('.calendar__day[tabindex="0"]', body) || $(".time-chip:not(:disabled)", body))?.focus(); return; }
          go(3);
        });
      }

      /* ---------------- step 3 ---------------- */
      function detailErrors() {
        const e = {};
        if (st.name.trim().length < 2) e.name = "Please enter your full name.";
        if (!st.email.trim()) e.email = "Please enter your email address.";
        else if (!validEmail(st.email.trim())) e.email = "Please enter a valid email address, e.g. name@example.com.";
        if (!st.phone.trim()) e.phone = "Please enter a phone number.";
        else if (!validPhone(st.phone.trim())) e.phone = "Please enter a valid phone number (7–15 digits, + allowed).";
        if (!st.reason) e.reason = "Please choose a reason for your visit.";
        if (!st.consent) e.consent = "Please confirm that the clinic may use your details to respond to this request.";
        return e;
      }
      function renderDetails() {
        body.innerHTML = `<div class="step">
          <div class="step__head"><span class="eyebrow">Step 3 of 5</span><h2 class="h2">Your details</h2>
            <p class="muted">So the clinic can contact you to confirm. Fields marked <span class="req">*</span> are required.</p></div>
          <form class="form" novalidate data-details>
            <div class="hp" aria-hidden="true"><label>Website <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
            <div class="field"><label class="field__label" for="b-name">Full name <span class="req" aria-hidden="true">*</span></label>
              <input class="input" id="b-name" name="name" autocomplete="name" maxlength="120" required value="${esc(st.name)}"></div>
            <div class="form-row form-row--2">
              <div class="field"><label class="field__label" for="b-email">Email <span class="req" aria-hidden="true">*</span></label>
                <input class="input" id="b-email" name="email" type="email" inputmode="email" autocomplete="email" maxlength="254" required value="${esc(st.email)}"></div>
              <div class="field"><label class="field__label" for="b-phone">Phone <span class="req" aria-hidden="true">*</span></label>
                <input class="input" id="b-phone" name="phone" type="tel" inputmode="tel" autocomplete="tel" maxlength="32" required placeholder="+383 4X XXX XXX" value="${esc(st.phone)}"></div>
            </div>
            <div class="field"><label class="field__label" for="b-reason">Reason for visit <span class="req" aria-hidden="true">*</span></label>
              <select class="select" id="b-reason" name="reason" required>
                <option value="">Select a reason…</option>
                ${cfg.reasons.map((r) => `<option value="${esc(r.id)}" ${st.reason === r.id ? "selected" : ""}>${esc(r.label)}</option>`).join("")}
              </select></div>
            <div class="field"><label class="field__label" for="b-message">Additional message <span class="opt">optional</span></label>
              <textarea class="textarea" id="b-message" name="message" maxlength="1000" rows="4" aria-describedby="b-message-hint">${esc(st.message)}</textarea>
              <p class="field__hint" id="b-message-hint">Travel dates or practical notes. Please don't include detailed medical information. <span data-count>${st.message.length}</span>/1000</p></div>
            <div class="field"><label class="check"><input type="checkbox" name="traveling" ${st.traveling ? "checked" : ""}><span class="check__box">${icon("check")}</span>
              <span>I'm travelling from another city or country</span></label></div>
            <div class="field"><label class="check"><input type="checkbox" name="consent" id="b-consent" ${st.consent ? "checked" : ""}><span class="check__box">${icon("check")}</span>
              <span>I agree that the clinic may use these details to respond to my request. <a class="text-link" href="/privacy" data-link target="_blank" rel="noopener">Privacy notice</a> <span class="req" aria-hidden="true">*</span></span></label></div>
          </form>
          ${foot(true, true, "Review request")}
        </div>`;
        const form = $("[data-details]", body);
        const sync = () => {
          st.name = form.elements.name.value; st.email = form.elements.email.value; st.phone = form.elements.phone.value;
          st.reason = form.elements.reason.value; st.message = form.elements.message.value;
          st.traveling = form.elements.traveling.checked; st.consent = form.elements.consent.checked;
        };
        form.addEventListener("input", (e) => {
          sync();
          if (e.target.name === "message") $("[data-count]", form).textContent = st.message.length;
          const el = e.target;
          if (el.closest(".field")?.classList.contains("has-error")) fieldError(el, detailErrors()[el.name] || "");
          renderSummary(); renderStepper();
        });
        form.addEventListener("change", () => { sync(); renderSummary(); renderStepper(); });
        $$("input:not([type=checkbox]), select", form).forEach((el) => el.addEventListener("blur", () => {
          if (el.value) { const msg = detailErrors()[el.name] || ""; fieldError(el, msg); if (!msg) el.closest(".field").classList.add("is-valid"); }
        }));
        // server-side errors from a failed submission
        Object.entries(st.errors).forEach(([k, v]) => form.elements[k] && fieldError(form.elements[k], v));
        $("[data-back]", body).addEventListener("click", () => { sync(); go(2); });
        $("[data-next]", body).addEventListener("click", () => {
          sync();
          const errs = detailErrors();
          ["name", "email", "phone", "reason", "consent"].forEach((k) => fieldError(form.elements[k], errs[k] || ""));
          const firstBad = ["name", "email", "phone", "reason", "consent"].find((k) => errs[k]);
          if (firstBad) { form.elements[firstBad].focus(); form.classList.add("shake"); setTimeout(() => form.classList.remove("shake"), 400); return; }
          st.errors = {};
          go(4);
        });
        form.addEventListener("submit", (e) => { e.preventDefault(); $("[data-next]", body).click(); });
        form.elements.website.value = st.hp || "";
        form.elements.website.addEventListener("input", (e) => { st.hp = e.target.value; });
      }

      /* ---------------- step 4 ---------------- */
      function renderReview(errorHtml = "") {
        const block = (title, step, rows) => `<div class="review__block"><div class="review__head"><h3>${title}</h3>
          <button type="button" class="review__edit" data-edit="${step}" aria-label="Edit ${title.toLowerCase()}">Edit</button></div>
          <dl>${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v) || '<span class="muted">—</span>'}</dd></div>`).join("")}</dl></div>`;
        body.innerHTML = `<div class="step">
          <div class="step__head"><span class="eyebrow">Step 4 of 5</span><h2 class="h2">Review your request</h2>
            <p class="muted">Check everything is correct, then send your request to the clinic.</p></div>
          <div class="review">
            ${block("Dentist", 1, [["Dentist", spName(st.specialistId)]])}
            ${block("Date & time", 2, [["Preferred date", fmtDate(st.date)], ["Preferred time", st.time]])}
            ${block("Your details", 3, [["Name", st.name], ["Email", st.email], ["Phone", st.phone], ["Reason", reasonLabel(st.reason)],
              ["Travelling", st.traveling ? "Yes" : "No"], ["Message", st.message]])}
            <div class="notice notice--warn">${icon("info")}<p><strong>Pending until confirmed.</strong> Sending this form does not reserve a time. The clinic will contact you by phone or email to confirm or suggest an alternative.</p></div>
            <div data-submit-alert aria-live="assertive">${errorHtml}</div>
          </div>
          <div class="step__foot">
            <button type="button" class="btn btn--ghost" data-back>${icon("arrowLeft")} Back</button>
            <button type="button" class="btn btn--primary" data-submit>Send request</button>
          </div>
        </div>`;
        $$("[data-edit]", body).forEach((b) => b.addEventListener("click", () => go(Number(b.dataset.edit))));
        $("[data-back]", body).addEventListener("click", () => go(3));
        $("[data-submit]", body).addEventListener("click", submit);
      }

      async function submit() {
        if (st.submitting) return; // prevent double submit
        const btn = $("[data-submit]", body);
        st.submitting = true;
        btn.classList.add("is-loading"); btn.disabled = true; btn.setAttribute("aria-busy", "true");
        $("[data-back]", body).disabled = true;
        $("[data-submit-alert]", body).innerHTML = "";
        try {
          const res = cfg.static ? {
            ok: true, created: true, ref: localRef("QD"), status: "pending", date: st.date, time: st.time,
            specialist: { id: st.specialistId, name: spName(st.specialistId) }, email: {},
          } : await api("/api/book-appointment", { method: "POST", body: {
            idempotencyKey: st.key, specialistId: st.specialistId, date: st.date, time: st.time,
            name: st.name, email: st.email, phone: st.phone, reason: st.reason, message: st.message,
            traveling: st.traveling, consent: st.consent, website: st.hp || "", elapsedMs: Math.round(performance.now() - st.started),
          } });
          if (cfg.formsubmit && res.created) {
            const status = await sendFormSubmit(cfg.formsubmit, {
              Reference: res.ref, Patient: st.name, Phone: st.phone, Dentist: res.specialist.name,
              "Preferred date": fmtDate(res.date), "Preferred time": res.time, Reason: reasonLabel(st.reason),
              Travelling: st.traveling ? "Yes" : "No", Message: st.message || "-", Status: "Pending - please contact the patient to confirm",
            }, {
              subject: `New appointment request ${res.ref} - ${res.date} ${res.time}`,
              replyTo: st.email,
              autoresponse: `Dear ${st.name}, thank you for contacting Quantum Dental Clinic & Implant Center. We received your appointment request ${res.ref} for ${fmtDate(res.date)} at ${res.time} (${res.specialist.name}). This is a request, not a confirmed appointment - the clinic will contact you to confirm. To change or cancel, call +383 49 536 944.`,
            });
            res.email = { patient: status === "sent" ? "fs_sent" : "failed", clinic: status === "sent" ? "fs_sent" : "failed" };
          }
          st.result = res;
          st.submitting = false;
          render();
          const h = $(".confirm h2", body);
          h?.setAttribute("tabindex", "-1"); h?.focus();
          root.querySelector("[data-booking]").scrollIntoView({ block: "start", behavior: "auto" });
          window.scrollBy(0, -100);
        } catch (err) {
          st.submitting = false;
          if (err.status === 422 && err.fields) {
            st.errors = err.fields;
            const stepOf = (k) => (k === "specialistId" ? 1 : k === "date" || k === "time" ? 2 : 3);
            const keys = Object.keys(err.fields).filter((k) => k !== "idempotencyKey");
            if (err.fields.idempotencyKey) { st.key = newKey(); }
            if (keys.length) { toast("Please check the highlighted information."); go(Math.min(...keys.map(stepOf))); return; }
          }
          renderReview(`<div class="notice notice--error" role="alert">${icon("alert")}<div><p><strong>Your request was not sent.</strong> ${esc(err.message)}</p>
            <p style-mt-sm>You can try again — you won't create a duplicate request — or call <a class="text-link" href="tel:+38349536944">+383 49 536 944</a>.</p></div></div>`);
          $("[data-submit]", body).focus();
        }
      }

      /* ---------------- confirmation ---------------- */
      function emailText(status, who) {
        if (who === "patient") return {
          accepted: ["ok", `Sent to ${st.email}. Our mail server accepted it — if it doesn't arrive, check your spam folder.`],
          fs_sent: ["ok", `A confirmation of your request is on its way to ${st.email}. If it doesn't arrive, check your spam folder.`],
          outbox: ["warn", "Test mode — the acknowledgement was captured on the server and not sent."],
          not_configured: ["warn", "Not sent — email isn't set up yet. Please keep your reference number."],
          failed: ["error", "We couldn't send your acknowledgement email. Please keep your reference number."],
          sending: ["warn", "Sending…"],
        }[status] || ["warn", "Unknown"];
        return {
          accepted: ["ok", "The clinic team has been notified."],
          fs_sent: ["ok", "The clinic team has been notified by email."],
          outbox: ["warn", "Test mode — clinic notification captured on the server."],
          not_configured: ["warn", "Saved for the clinic team; email notification isn't set up yet."],
          failed: ["warn", "Saved for the clinic team; the email notification couldn't be sent."],
          sending: ["warn", "Sending…"],
        }[status] || ["warn", "Saved for the clinic team."];
      }
      function renderConfirmation() {
        const r = st.result;
        const [pc, pt] = emailText(r.email?.patient, "patient");
        const [cc, ct] = emailText(r.email?.clinic, "clinic");
        body.innerHTML = `<div class="confirm">
          <span class="confirm__icon">${icon("check")}</span>
          <div class="stack"><h2 class="h1">Request sent</h2>
            <p class="lead">Thank you, ${esc(st.name.split(" ")[0])}. Your request is <strong>pending confirmation</strong> — the clinic will contact you to confirm your appointment.</p></div>
          <div class="stack"><p class="info-list__label">Your reference</p><p class="confirm__ref" data-ref>${esc(r.ref)}</p></div>
          <div class="card confirm__card"><dl class="summary__list">
            <div class="summary__row"><dt>Dentist</dt><dd>${esc(r.specialist.name)}</dd></div>
            <div class="summary__row"><dt>Preferred date</dt><dd>${esc(fmtDate(r.date))}</dd></div>
            <div class="summary__row"><dt>Preferred time</dt><dd>${esc(r.time)}</dd></div>
            <div class="summary__row"><dt>Status</dt><dd><span class="status-pill status-pill--pending">Pending confirmation</span></dd></div>
            <div class="summary__row"><dt>Email to you</dt><dd><span class="status-pill status-pill--${pc}">${{ ok: "Sent", warn: "Not sent", error: "Failed" }[pc]}</span><br><span class="small muted">${esc(pt)}</span></dd></div>
            <div class="summary__row"><dt>Clinic</dt><dd><span class="status-pill status-pill--${cc === "ok" ? "ok" : "warn"}">${cc === "ok" ? "Notified" : "Request saved"}</span><br><span class="small muted">${esc(ct)}</span></dd></div>
          </dl></div>
          <div class="confirm__actions">
            <button type="button" class="btn btn--primary" data-ics>${icon("calendar")} Add to calendar</button>
            <button type="button" class="btn btn--ghost" data-print>${icon("print")} Print summary</button>
            <a class="btn btn--ghost" href="tel:+38349536944">${icon("phone")} Contact clinic</a>
            <a class="btn btn--ghost" href="/" data-link>${icon("home")} Home</a>
            <button type="button" class="btn btn--ghost" data-again>New request</button>
          </div>
          <p class="small muted">The calendar entry is marked as pending — update it once the clinic confirms.</p>
        </div>`;
        $("[data-ics]", body).addEventListener("click", () => downloadIcs(r, cfg.timezone));
        $("[data-print]", body).addEventListener("click", () => window.print());
        $("[data-again]", body).addEventListener("click", () => window.dispatchEvent(new CustomEvent("qd:rerender")));
      }

      render();
      // Initial focus only if arrived via preselect (step 2) – otherwise router focuses the page.
    },
  };
}

/* ---------- .ics (pending) ---------- */
function tzOffsetMs(utcMs, tz) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })
    .formatToParts(new Date(utcMs)).map((x) => [x.type, x.value]));
  return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - utcMs;
}
function toUtcStamp(ms) { return new Date(ms).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, ""); }
export function buildIcs(r, tz) {
  const [y, m, d] = r.date.split("-").map(Number);
  const [hh, mm] = r.time.split(":").map(Number);
  const guess = Date.UTC(y, m - 1, d, hh, mm);
  const start = guess - tzOffsetMs(guess, tz);
  const end = start + 30 * 60 * 1000;
  const escIcs = (s) => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
  return [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Quantum Dental//Appointment Request//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    "BEGIN:VEVENT", `UID:${r.ref}@quantum-dental`, `DTSTAMP:${toUtcStamp(Date.now())}`, `DTSTART:${toUtcStamp(start)}`, `DTEND:${toUtcStamp(end)}`,
    `SUMMARY:${escIcs(`PENDING CONFIRMATION – Dental appointment request (${r.ref})`)}`,
    `DESCRIPTION:${escIcs(`This is the preferred time you requested at Quantum Dental Clinic & Implant Center. It is NOT confirmed yet — the clinic will contact you to confirm or suggest another time.\nReference: ${r.ref}\nDentist: ${r.specialist.name}\nTelephone: +383 49 536 944`)}`,
    "STATUS:TENTATIVE", "TRANSP:TRANSPARENT", "END:VEVENT", "END:VCALENDAR",
  ].join("\r\n") + "\r\n";
}
function downloadIcs(r, tz) {
  const blob = new Blob([buildIcs(r, tz)], { type: "text/calendar;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `quantum-dental-request-${r.ref}.ics`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  toast("Calendar file downloaded (marked pending).");
}
