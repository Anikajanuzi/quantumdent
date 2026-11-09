/* Shared UI helpers: escaping, icons, photos/placeholders, reveal, accordion, lightbox, toast, API. */
import { PHOTOS } from "./content.js";

export const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/* ---------- Icons (24px line set) ---------- */
const P = {
  tooth: '<path d="M12 5.5C10.2 4 8.6 3.6 7 4 4.6 4.6 3.7 7.3 4.4 10.2c.5 2 1.3 3.3 1.7 5.4.4 2 .6 4.3 1.9 4.4 1.5.1 1.6-2.9 2.3-4.6.3-.8 1-.9 1.7-.9s1.4.1 1.7.9c.7 1.7.8 4.7 2.3 4.6 1.3-.1 1.5-2.4 1.9-4.4.4-2.1 1.2-3.4 1.7-5.4.7-2.9-.2-5.6-2.6-6.2-1.6-.4-3.2 0-5 1.5Z"/>',
  implant: '<path d="M8 3.5h8l-1 4H9z"/><path d="M9.5 9h5M9.8 11.5h4.4M10.1 14h3.8M10.4 16.5h3.2M11 19h2"/><path d="M9 7.5l1.5 13h3L15 7.5"/>',
  aligner: '<path d="M3.5 9c2 2.2 4.8 3.5 8.5 3.5S18.5 11.2 20.5 9"/><path d="M4.5 13c1.8 3 4.4 4.5 7.5 4.5s5.7-1.5 7.5-4.5"/><path d="M8 11.8v3.6M12 12.5v5M16 11.8v3.6"/>',
  sparkle: '<path d="M12 3.5l1.6 4.9 4.9 1.6-4.9 1.6L12 16.5l-1.6-4.9L5.5 10l4.9-1.6z"/><path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>',
  root: '<path d="M7 4.5c1.6-1 3.4-.8 5 .2 1.6-1 3.4-1.2 5-.2 1.9 1.3 1.9 4.1.8 6.6"/><path d="M6.2 11.1C5.1 8.6 5.1 5.8 7 4.5"/><path d="M6.2 11.1c.8 1.8 1.2 4.2 1.6 6.2.3 1.7.9 2.7 1.6 2.7 1 0 1-2.3 1.4-4.3M17.8 11.1c-.8 1.8-1.2 4.2-1.6 6.2-.3 1.7-.9 2.7-1.6 2.7-1 0-1-2.3-1.4-4.3"/><path d="M12 8v7.5"/>',
  gum: '<path d="M3.5 8.5c2.8 1.6 5.6 2.4 8.5 2.4s5.7-.8 8.5-2.4"/><path d="M6 10.2v4.2c0 1.6 1 2.6 2 2.6s2-1 2-2.6v-3.6M14 10.8v3.6c0 1.6 1 2.6 2 2.6s2-1 2-2.6v-4.2"/>',
  child: '<circle cx="12" cy="8" r="3.5"/><path d="M6 20.5c.6-3.6 3-5.5 6-5.5s5.4 1.9 6 5.5"/><path d="M10.6 8.6h.01M13.4 8.6h.01"/>',
  crown: '<path d="M4 8.5l3.5 3 4.5-6 4.5 6 3.5-3-1.5 9.5H5.5z"/><path d="M5.5 20.5h13"/>',
  phone: '<path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5l8.5 6 8.5-6"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  pin: '<path d="M12 21s-6.5-5.8-6.5-11a6.5 6.5 0 0 1 13 0c0 5.2-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  plane: '<path d="M10.5 13.5L4 11l1.5-1.5 7.5.5 4-4c.8-.8 2.2-.8 2.5 0 .3.3.3 1.7-.5 2.5l-4 4 .5 7.5L14 21.5 11.5 15"/>',
  arrow: '<path d="M4 12h15M13.5 6.5L19 12l-5.5 5.5"/>',
  arrowLeft: '<path d="M20 12H5M10.5 6.5L5 12l5.5 5.5"/>',
  chevronRight: '<path d="M9.5 6l6 6-6 6"/>',
  chevronLeft: '<path d="M14.5 6l-6 6 6 6"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
  alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4.5M12 17.2h.01"/>',
  user: '<circle cx="12" cy="8.5" r="3.8"/><path d="M4.5 20.5c1-3.8 3.9-5.8 7.5-5.8s6.5 2 7.5 5.8"/>',
  users: '<circle cx="9" cy="8.5" r="3.3"/><path d="M2.8 19.5c.8-3.2 3.2-5 6.2-5s5.4 1.8 6.2 5"/><path d="M15.5 5.6a3.2 3.2 0 0 1 0 6.1M17.5 14.6c1.8.6 3.1 2.2 3.7 4.9"/>',
  expand: '<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="9" cy="10" r="1.8"/><path d="M20.5 16l-5-5-9 8.5"/>',
  print: '<path d="M7 9V4h10v5"/><rect x="3.5" y="9" width="17" height="8" rx="1.5"/><path d="M7 14h10v6H7z"/>',
  home: '<path d="M4 10.5L12 4l8 6.5V20H4z"/><path d="M10 20v-5.5h4V20"/>',
  tag: '<path d="M3.5 12.5V4.5h8l9 9-8 8z"/><circle cx="8" cy="9" r="1.3"/>',
  doc: '<path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4M9 12h6M9 15.5h6"/>',
  shield: '<path d="M12 3.5l7 3v5.5c0 4.2-3 7.4-7 8.5-4-1.1-7-4.3-7-8.5V6.5z"/><path d="M9 12l2 2 4-4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  compare: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M12 5v14M8 10l-2 2 2 2M16 10l2 2-2 2"/>',
};
export const icon = (name, cls = "") => `<svg aria-hidden="true" viewBox="0 0 24 24"${cls ? ` class="${cls}"` : ""}>${P[name] || P.info}</svg>`;

/* ---------- Placeholder motifs (abstract line drawings — not depictions of the clinic) ---------- */
const MOTIFS = {
  arch: '<path d="M80 500V230a120 120 0 0 1 240 0v270"/><path d="M120 500V240a80 80 0 0 1 160 0v260"/><path d="M40 420c80-34 240-34 320 0"/><path d="M40 440c80-34 240-34 320 0"/>',
  corridor: '<path d="M0 0l150 180v140L0 500M400 0L250 180v140l150 180"/><path d="M150 180h100v140H150z"/><path d="M0 500l150-180M400 500L250 320M60 500l110-180M340 500L230 320M130 500l50-180M270 500l-50-180"/>',
  flutes: Array.from({ length: 21 }, (_, i) => `<path d="M${10 + i * 19} 0v500"/>`).join("") + '<path d="M0 470h400"/>',
  curves: '<path d="M-20 520C40 300 160 160 420 120"/><path d="M-20 560C60 340 190 210 420 180"/><path d="M-20 600C80 380 220 260 420 240"/><path d="M-20 640C100 420 250 310 420 300"/>',
  doors: '<path d="M40 500V120h90v380M155 500V120h90v380M270 500V120h90v380"/><path d="M118 310v30M233 310v30M348 310v30"/><path d="M0 500h400M20 100h360"/>',
  lime: '<path d="M30 120c60-20 140 10 220-8s110-10 130 4"/><path d="M10 220c90-14 160 16 240-2s100-6 140 6"/><path d="M40 320c80-18 150 12 220-4s90-6 130 8"/><path d="M20 410c70-10 160 14 230 0s100-8 140 2"/>',
};

export function photo(slot, { cls = "", ratio = "4-5", arch = false, reveal = true, eager = false, label = true } = {}) {
  const p = PHOTOS[slot];
  const classes = ["photo", ratio && `photo--ratio-${ratio}`, arch && "photo--arch", reveal && "photo-reveal reveal-target", cls].filter(Boolean).join(" ");
  if (p && p.src) {
    const alt = p.illustration ? `Illustration: ${p.alt}` : p.alt;
    return `<figure class="${classes}"><img src="${esc(p.src)}" alt="${esc(alt)}" width="${p.width}" height="${p.height}" ${eager ? 'fetchpriority="high"' : 'loading="lazy"'} decoding="async">${p.illustration && label ? '<span class="tag photo__tag" aria-hidden="true">Illustration</span>' : ""}</figure>`;
  }
  return `<figure class="${classes}" role="img" aria-label="Photo placeholder: ${esc(p ? p.alt : slot)}">${placeholderInner(slot, label)}</figure>`;
}

export function placeholderInner(slot, label = true) {
  const p = PHOTOS[slot] || { motif: "lime", label: "Photo", note: "" };
  return `<div class="placeholder">
    <svg class="placeholder__motif" viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${MOTIFS[p.motif] || MOTIFS.lime}</svg>
    ${label ? `<div class="placeholder__label"><span class="tag">${icon("image")} Photo pending</span><strong>${esc(p.label)}</strong><span class="small">${esc(p.note || "")}</span></div>` : ""}
  </div>`;
}

export function portraitPlaceholder(demo = false) {
  return `<div class="portrait-ph" role="img" aria-label="Portrait placeholder">
    <svg viewBox="0 0 100 120" aria-hidden="true"><circle cx="50" cy="42" r="20"/><path d="M14 118c4-26 18-40 36-40s32 14 36 40"/><path d="M50 2v8M50 110v8" stroke-dasharray="2 4"/></svg>
    <span class="tag ${demo ? "tag--demo" : ""}">${demo ? "Demo · not real staff" : "Portrait pending"}</span>
  </div>`;
}

/* ---------- Scroll reveal ---------- */
let io;
export function initReveal(root = document) {
  const targets = $$(".reveal, .reveal-target", root);
  if (!("IntersectionObserver" in window) || prefersReducedMotion()) {
    targets.forEach((el) => el.classList.add("is-visible"));
    return;
  }
  io ||= new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
    });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  targets.forEach((el) => io.observe(el));
  // Stagger siblings marked with data-stagger
  $$("[data-stagger]", root).forEach((group) => {
    [...group.children].forEach((child, i) => child.style.setProperty("--delay", `${Math.min(i, 8) * 70}ms`));
  });
}

/* ---------- Accordion ---------- */
export function accordion(items, idPrefix) {
  return `<div class="accordion">${items.map((it, i) => `
    <div class="acc-item">
      <h3><button type="button" class="acc-item__btn" aria-expanded="false" aria-controls="${idPrefix}-${i}" id="${idPrefix}-${i}-btn">
        <span>${esc(it.q)}</span><span class="acc-item__icon" aria-hidden="true"></span></button></h3>
      <div class="acc-item__panel" id="${idPrefix}-${i}" role="region" aria-labelledby="${idPrefix}-${i}-btn" hidden><div><p>${esc(it.a)}</p></div></div>
    </div>`).join("")}</div>`;
}
export function initAccordions(root) {
  $$(".acc-item__btn", root).forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = document.getElementById(btn.getAttribute("aria-controls"));
      const open = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!open));
      if (open) {
        panel.classList.remove("is-open");
        const done = () => { panel.hidden = true; };
        prefersReducedMotion() ? done() : setTimeout(done, 280);
      } else {
        panel.hidden = false;
        requestAnimationFrame(() => requestAnimationFrame(() => panel.classList.add("is-open")));
      }
    });
  });
}

/* ---------- Focus trap ---------- */
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
export function trapFocus(container, onEscape) {
  const handler = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onEscape?.(); return; }
    if (e.key !== "Tab") return;
    const f = $$(FOCUSABLE, container).filter((el) => el.offsetParent !== null || el === document.activeElement);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  container.addEventListener("keydown", handler);
  return () => container.removeEventListener("keydown", handler);
}

/* ---------- Lightbox ---------- */
export function openLightbox(items, index = 0, opener = null) {
  const lb = $("#lightbox");
  let i = index;
  const render = () => {
    const it = items[i];
    const media = $(".lightbox__media", lb);
    const fill = () => {
      media.innerHTML = it.html;
      $(".lightbox__count", lb).textContent = `${i + 1} / ${items.length}`;
      $(".lightbox__caption", lb).textContent = it.caption || "";
      media.classList.remove("is-switching");
    };
    if (media.innerHTML && !prefersReducedMotion()) { media.classList.add("is-switching"); setTimeout(fill, 200); }
    else fill();
    $("[data-lb-prev]", lb).disabled = items.length < 2;
    $("[data-lb-next]", lb).disabled = items.length < 2;
  };
  lb.innerHTML = `
    <div class="lightbox__top"><span class="lightbox__count" aria-live="polite"></span>
      <button type="button" class="icon-btn" data-lb-close aria-label="Close image viewer">${icon("x")}</button></div>
    <div class="lightbox__stage"><div class="lightbox__media"></div></div>
    <div class="lightbox__bottom"><p class="lightbox__caption"></p>
      <div class="lightbox__nav">
        <button type="button" class="icon-btn" data-lb-prev aria-label="Previous image">${icon("chevronLeft")}</button>
        <button type="button" class="icon-btn" data-lb-next aria-label="Next image">${icon("chevronRight")}</button>
      </div></div>`;
  const prev = () => { i = (i - 1 + items.length) % items.length; render(); };
  const next = () => { i = (i + 1) % items.length; render(); };
  let releaseTrap;
  const keys = (e) => { if (e.key === "ArrowLeft") prev(); if (e.key === "ArrowRight") next(); };
  const close = () => {
    lb.classList.remove("is-open");
    document.removeEventListener("keydown", keys);
    releaseTrap?.();
    document.body.style.overflow = "";
    setTimeout(() => { lb.hidden = true; lb.innerHTML = ""; }, prefersReducedMotion() ? 0 : 260);
    opener?.focus();
  };
  $("[data-lb-close]", lb).addEventListener("click", close);
  $("[data-lb-prev]", lb).addEventListener("click", prev);
  $("[data-lb-next]", lb).addEventListener("click", next);
  lb.addEventListener("click", (e) => { if (e.target.classList.contains("lightbox__stage")) close(); }, { once: false });
  // swipe
  let x0 = null;
  lb.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  lb.addEventListener("touchend", (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 50) (dx > 0 ? prev : next)();
    x0 = null;
  });
  document.addEventListener("keydown", keys);
  releaseTrap = trapFocus(lb, close);
  lb.hidden = false;
  document.body.style.overflow = "hidden";
  render();
  requestAnimationFrame(() => lb.classList.add("is-open"));
  $("[data-lb-close]", lb).focus();
  lb._close = close;
}
export function closeLightboxIfOpen() { const lb = $("#lightbox"); if (lb && !lb.hidden && lb._close) lb._close(); }

/* ---------- Before / after comparer ---------- */
export function compareSlider({ beforeHtml, afterHtml, label }) {
  return `<div class="compare" data-compare>
    <div class="compare__layer compare__layer--before">${beforeHtml}</div>
    <div class="compare__layer compare__layer--after">${afterHtml}</div>
    <span class="tag compare__label compare__label--before">Before</span>
    <span class="tag compare__label compare__label--after">After</span>
    <input class="compare__range" type="range" min="0" max="100" value="50" aria-label="${esc(label || "Before and after comparison")}: drag to compare">
    <span class="compare__handle" aria-hidden="true"></span>
  </div>`;
}
export function initCompare(root) {
  $$("[data-compare]", root).forEach((c) => {
    const r = $(".compare__range", c);
    const set = () => c.style.setProperty("--pos", `${r.value}%`);
    r.addEventListener("input", set);
    set();
  });
}

/* ---------- Toast ---------- */
let toastEl, toastTimer;
export function toast(msg) {
  toastEl ||= Object.assign(document.body.appendChild(document.createElement("div")), { className: "toast", role: "status" });
  toastEl.textContent = msg;
  toastEl.classList.add("is-show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("is-show"), 3200);
}

/* ---------- API ---------- */
export async function api(path, { method = "GET", body, signal } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method, signal, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    const e = new Error("We couldn't reach the server. Please check your connection and try again.");
    e.network = true;
    throw e;
  }
  let data = {};
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) {
    const e = new Error(data.error || `The server returned an error (${res.status}). Please try again.`);
    e.status = res.status; e.fields = data.fields || null;
    throw e;
  }
  return data;
}

export function newKey() {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return [...a].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/* ---------- Form helpers ---------- */
export function fieldError(field, message) {
  const wrap = field.closest(".field");
  if (!wrap) return;
  let err = $(".field__error", wrap);
  const control = $("input, select, textarea", wrap);
  if (message) {
    wrap.classList.add("has-error");
    wrap.classList.remove("is-valid");
    if (!err) {
      err = document.createElement("p");
      err.className = "field__error";
      err.id = `${control.id || control.name}-error`;
      wrap.appendChild(err);
    }
    err.innerHTML = `${icon("alert")}<span>${esc(message)}</span>`;
    control.setAttribute("aria-invalid", "true");
    const described = new Set((control.getAttribute("aria-describedby") || "").split(" ").filter(Boolean));
    described.add(err.id);
    control.setAttribute("aria-describedby", [...described].join(" "));
  } else {
    wrap.classList.remove("has-error");
    control.removeAttribute("aria-invalid");
    if (err) {
      const described = (control.getAttribute("aria-describedby") || "").split(" ").filter((id) => id && id !== err.id);
      described.length ? control.setAttribute("aria-describedby", described.join(" ")) : control.removeAttribute("aria-describedby");
      err.remove();
    }
  }
}
export const EMAIL_RE = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
export const validEmail = (v) => EMAIL_RE.test(v) && !v.includes("..") && v.length <= 254;
export const validPhone = (v) => /^[+()\-.\s0-9]+$/.test(v) && (v.replace(/\D/g, "").length >= 7 && v.replace(/\D/g, "").length <= 15);

/* ---------- Dates ---------- */
export function fmtDate(iso, opts = { weekday: "long", day: "numeric", month: "long", year: "numeric" }) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-GB", opts);
}
/* "Today" in the clinic's time zone, as YYYY-MM-DD, plus current HH:MM. */
export function clinicNow(tz) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(new Date()).map((p) => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour === "24" ? "00" : parts.hour}:${parts.minute}` };
}
