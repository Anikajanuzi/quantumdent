/* App shell: config, router (History API), navigation, mobile menu, page transitions. */
import * as pages from "./pages.js";
import { booking } from "./booking.js";
import { $, $$, initReveal, trapFocus, prefersReducedMotion, closeLightboxIfOpen } from "./ui.js";

const FALLBACK_CONFIG = {
  clinic: { name: "Quantum Dental Clinic & Implant Center", phone: "+383 49 536 944", phoneLocal: "049-536-944", phoneHref: "tel:+38349536944", address: null, hours: null },
  specialists: [{ id: "first-available", name: "First available dentist", specialty: "The clinic matches your request to a suitable dentist", generic: true }],
  reasons: [{ id: "checkup", label: "Check-up or cleaning" }, { id: "pain", label: "Tooth pain or discomfort" }, { id: "consultation", label: "Consultation about a treatment" }, { id: "second-opinion", label: "Second opinion" }, { id: "follow-up", label: "Follow-up visit" }, { id: "other", label: "Something else" }],
  times: Array.from({ length: 18 }, (_, i) => `${String(9 + Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`),
  timezone: "Europe/Belgrade", demo: false, draftBanner: true, routes: {},
  // Used on static hosting (e.g. Vercel) where the Python server isn't running:
  formsubmit: { to: "ajanuzi28@kla.education", cc: "ekelmendi27@kla.education,dramaxhiku27@kla.education,ashatrolli27@kla.education" },
  static: true,
};

const ROUTES = [
  [/^\/$/, pages.home, "/"],
  [/^\/treatments$/, pages.treatments, "/treatments"],
  [/^\/treatments\/([a-z-]+)$/, pages.treatmentDetail, "/treatments"],
  [/^\/results$/, pages.results, "/results"],
  [/^\/doctors$/, pages.doctors, "/doctors"],
  [/^\/doctors\/([a-z0-9-]+)$/, pages.doctorDetail, "/doctors"],
  [/^\/pricing$/, pages.pricing, "/pricing"],
  [/^\/travel$/, pages.travel, "/travel"],
  [/^\/booking$/, booking, "/booking"],
  [/^\/contact$/, pages.contact, "/contact"],
  [/^\/privacy$/, pages.privacy, null],
];

const main = $("#main");
const announcer = $("#route-announcer");
let config = FALLBACK_CONFIG;
let cleanup = null;
let firstRender = true;
let renderToken = 0;

function setMeta(title, description) {
  document.title = title;
  const set = (sel, attr, val) => { const el = $(sel); if (el && val) el.setAttribute(attr, val); };
  set('meta[name="description"]', "content", description);
  set('meta[property="og:title"]', "content", title);
  set('meta[property="og:description"]', "content", description);
  const canonical = location.origin + (location.pathname.replace(/\/$/, "") || "/");
  set('link[rel="canonical"]', "href", canonical);
  set('meta[property="og:url"]', "content", canonical);
}

function setActiveNav(section) {
  $$("[data-nav]").forEach((a) => {
    if (a.dataset.nav === section) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  moveIndicator();
}

function moveIndicator() {
  const nav = $(".primary-nav");
  const ind = $(".primary-nav__indicator");
  if (!nav || !ind) return;
  const active = $('.primary-nav a[aria-current="page"]', nav);
  if (!active || nav.offsetParent === null) { ind.style.opacity = "0"; return; }
  const nr = nav.getBoundingClientRect(), ar = active.getBoundingClientRect();
  ind.style.width = `${ar.width}px`;
  ind.style.transform = `translateX(${ar.left - nr.left}px)`;
  ind.style.opacity = "1";
}

function applyDelays(root) {
  $$("[data-d]", root).forEach((el) => el.style.setProperty("--d", `${el.dataset.d}ms`));
}

async function render({ focus = true } = {}) {
  const token = ++renderToken;
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const query = new URLSearchParams(location.search);
  let view, section = null, params = [];
  for (const [re, fn, sec] of ROUTES) {
    const m = path.match(re);
    if (m) { view = fn; section = sec; params = m.slice(1); break; }
  }
  const ctx = { params, query, config, navigate };
  const page = view ? view(ctx) : pages.notFound();

  closeLightboxIfOpen();
  const animate = !firstRender && !prefersReducedMotion();
  if (animate) {
    main.classList.add("is-leaving");
    await new Promise((r) => setTimeout(r, 160));
    if (token !== renderToken) return; // a newer navigation started
  }
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }

  main.innerHTML = page.html;
  applyDelays(main);
  window.scrollTo({ top: 0, left: 0, behavior: "instant" in window ? "instant" : "auto" });
  if (animate) {
    main.classList.remove("is-leaving");
    main.classList.add("is-entering");
    requestAnimationFrame(() => requestAnimationFrame(() => main.classList.remove("is-entering")));
  }

  const routeMeta = config.routes?.[path];
  const title = page.title || routeMeta?.title || "Quantum Dental Clinic & Implant Center";
  setMeta(title, page.description || routeMeta?.description || "");
  setActiveNav(section);
  document.body.dataset.route = section || "other";

  const ret = page.mount?.(main, ctx);
  if (typeof ret === "function") cleanup = ret;
  initReveal(main);

  if (!firstRender) {
    announcer.textContent = title.split(" — ")[0];
    if (focus) main.focus({ preventScroll: true });
  }
  firstRender = false;
}

export function navigate(url, { replace = false } = {}) {
  const u = new URL(url, location.origin);
  if (u.pathname + u.search === location.pathname + location.search && !replace) { window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" }); return; }
  history[replace ? "replaceState" : "pushState"]({}, "", u.pathname + u.search + u.hash);
  render();
}

/* ---------- Link interception ---------- */
document.addEventListener("click", (e) => {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target.closest("a[href]");
  if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin) return;
  if (/^\/(api|admin|static)\b/.test(url.pathname) || /\.[a-z0-9]+$/i.test(url.pathname)) return;
  e.preventDefault();
  closeMenu(false);
  navigate(url.pathname + url.search);
});
window.addEventListener("popstate", () => render());
window.addEventListener("qd:rerender", () => render());

/* ---------- Mobile menu ---------- */
const menu = $("#mobile-menu");
const toggle = $(".menu-toggle");
let releaseTrap = null;
function openMenu() {
  menu.hidden = false;
  document.body.classList.add("menu-open");
  toggle.setAttribute("aria-expanded", "true");
  requestAnimationFrame(() => requestAnimationFrame(() => menu.classList.add("is-open")));
  releaseTrap = trapFocus(menu, () => closeMenu(true));
  $("[data-close-menu]", menu).focus();
}
function closeMenu(returnFocus = true) {
  if (menu.hidden) return;
  menu.classList.remove("is-open");
  document.body.classList.remove("menu-open");
  toggle.setAttribute("aria-expanded", "false");
  releaseTrap?.(); releaseTrap = null;
  setTimeout(() => { if (!menu.classList.contains("is-open")) menu.hidden = true; }, prefersReducedMotion() ? 0 : 420);
  if (returnFocus) toggle.focus();
}
toggle.addEventListener("click", () => (menu.hidden ? openMenu() : closeMenu()));
$("[data-close-menu]", menu).addEventListener("click", () => closeMenu());
menu.addEventListener("click", (e) => { if (e.target === menu) closeMenu(); });
window.addEventListener("resize", () => { if (window.innerWidth >= 1200) closeMenu(false); moveIndicator(); }, { passive: true });

/* ---------- Header state ---------- */
const header = $("#site-header");
const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
window.addEventListener("scroll", onScroll, { passive: true });
onScroll();

/* ---------- Draft banner ---------- */
function initBanner() {
  const banner = $("#draft-banner");
  let dismissed = false;
  try { dismissed = sessionStorage.getItem("qd-banner") === "1"; } catch { /* storage unavailable */ }
  if (config.draftBanner && !dismissed) banner.hidden = false;
  $("[data-dismiss-banner]", banner).addEventListener("click", () => {
    banner.hidden = true;
    try { sessionStorage.setItem("qd-banner", "1"); } catch { /* ignore */ }
  });
}

$$("[data-year]").forEach((el) => (el.textContent = new Date().getFullYear()));
if (!("IntersectionObserver" in window)) document.documentElement.classList.add("no-io");
document.fonts?.ready.then(moveIndicator);

/* ---------- Boot ---------- */
(async function boot() {
  try {
    const res = await fetch("/api/site-config", { credentials: "same-origin" });
    if (res.ok && (res.headers.get("content-type") || "").includes("json")) config = await res.json();
  } catch { /* use fallback; forms will report errors honestly on submit */ }
  initBanner();
  await render({ focus: false });
})();
