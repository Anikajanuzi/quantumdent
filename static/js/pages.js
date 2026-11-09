/* Page views. Each page returns { html, mount?(root, ctx) => cleanup? }. */
import { TREATMENTS, CONSULTATION_STEPS, GALLERY, PHOTOS, RESULTS, PRICES, FAQ_TRAVEL, FAQ_BOOKING } from "./content.js";
import {
  esc, icon, photo, placeholderInner, portraitPlaceholder, accordion, initAccordions, openLightbox,
  compareSlider, initCompare, $, $$, api, newKey, fieldError, validEmail, toast, sendFormSubmit, localRef,
} from "./ui.js";

const arrow = icon("arrow", "icon-arrow");
const verifiedTreatments = () => TREATMENTS.every((t) => t.verified);

function pageHero({ eyebrow, title, lead, crumbs, extra = "" }) {
  return `<section class="page-hero"><div class="container"><div class="page-hero__inner">
    ${crumbs ? `<nav class="breadcrumbs reveal" aria-label="Breadcrumb">${crumbs}</nav>` : ""}
    ${eyebrow ? `<span class="eyebrow reveal">${esc(eyebrow)}</span>` : ""}
    <h1 class="h1 reveal">${title}</h1>
    ${lead ? `<p class="lead reveal">${lead}</p>` : ""}
    ${extra}
  </div></div></section>`;
}

const crumb = (items) => items.map(([href, label], i) =>
  i < items.length - 1 ? `<a href="${href}" data-link>${esc(label)}</a>${icon("chevronRight")}` : `<span aria-current="page">${esc(label)}</span>`).join("");

const treatmentNotice = () => verifiedTreatments() ? "" : `
  <div class="notice reveal">${icon("info")}<p><strong>General information.</strong> These pages explain common treatment areas. Please contact the clinic to confirm which treatments are currently available at Quantum Dental.</p></div>`;

function treatmentCard(t, { compact = false } = {}) {
  return `<article class="card card--hover t-card reveal">
    <span class="icon-tile">${icon(t.icon)}</span>
    <h3 class="t-card__title"><a href="/treatments/${t.slug}" data-link>${esc(t.name)}</a></h3>
    <p class="t-card__desc">${esc(t.short)}</p>
    <div class="t-card__actions">
      <a class="link-arrow" href="/treatments/${t.slug}" data-link aria-label="Learn more about ${esc(t.name)}">Learn more ${icon("arrow")}</a>
      ${compact ? "" : `<a class="btn btn--ghost btn--sm" href="/booking?topic=${t.slug}" data-link aria-label="Book a consultation about ${esc(t.name)}">Book consultation</a>`}
    </div>
  </article>`;
}

function doctorCard(s) {
  const pic = s.photo
    ? `<figure class="photo"><img src="${esc(s.photo)}" alt="Portrait of ${esc(s.name)}" loading="lazy" decoding="async"></figure>`
    : `<figure class="photo">${portraitPlaceholder(s.demo)}</figure>`;
  return `<article class="card card--hover doc-card reveal">
    ${pic}
    <div class="doc-card__body">
      ${s.demo ? `<span class="tag tag--demo">Demo profile</span>` : ""}
      <h3 class="doc-card__name"><a href="/doctors/${esc(s.id)}" data-link>${esc(s.name)}</a></h3>
      <p class="doc-card__spec">${esc(s.specialty || "")}</p>
    </div>
    <div class="doc-card__foot">
      <a class="btn btn--primary btn--sm" href="/booking?specialist=${encodeURIComponent(s.id)}" data-link>Book with this dentist</a>
      <a class="btn btn--ghost btn--sm" href="/doctors/${esc(s.id)}" data-link>View profile</a>
    </div>
  </article>`;
}

const ctaBand = (title = "Ready when you are.", text = "Send an appointment request online, or call the clinic directly. The team will get back to you to confirm a time.") => `
  <section class="section section--tight"><div class="container">
    <div class="cta-band reveal">
      <div class="stack" style-stack>
        <span class="eyebrow">Appointments</span>
        <h2 class="h1">${title}</h2>
        <p class="lead">${text}</p>
      </div>
      <div class="btn-row">
        <a class="btn btn--light" href="/booking" data-link>Request an appointment ${arrow}</a>
        <a class="btn btn--outline-light" href="tel:+38349536944">${icon("phone")} 049-536-944</a>
      </div>
    </div>
  </div></section>`;

function infoRows(clinic) {
  return `<div class="info-list">
    <div class="info-list__row"><span class="icon-tile">${icon("phone")}</span><div><p class="info-list__label">Telephone</p>
      <p class="info-list__value"><a href="${clinic.phoneHref}">${esc(clinic.phone)}</a></p><p class="small muted">Local: ${esc(clinic.phoneLocal)}</p></div></div>
    <div class="info-list__row"><span class="icon-tile">${icon("pin")}</span><div><p class="info-list__label">Address</p>
      <p class="info-list__value">${clinic.address ? esc(clinic.address) : '<span class="muted">To be confirmed</span>'}</p></div></div>
    <div class="info-list__row"><span class="icon-tile">${icon("clock")}</span><div><p class="info-list__label">Opening hours</p>
      <p class="info-list__value">${clinic.hours ? esc(clinic.hours) : '<span class="muted">To be confirmed — please call</span>'}</p></div></div>
  </div>`;
}

/* ===================================================================== HOME */
export function home(ctx) {
  const team = ctx.config.specialists.filter((s) => !s.generic);
  const teamHtml = team.length
    ? `<div class="grid grid--3" data-stagger>${team.slice(0, 3).map(doctorCard).join("")}</div>`
    : `<div class="split">
        <div class="stack reveal">
          <p class="lead">Profiles of the clinic's dentists will be published here once they have been confirmed by the clinic.</p>
          <p class="muted">You can already request an appointment with the first available dentist — the clinic will match your request to a suitable member of the team.</p>
          <div class="btn-row"><a class="btn btn--dark" href="/booking" data-link>Request an appointment</a><a class="btn btn--ghost" href="/doctors" data-link>About our dentists</a></div>
        </div>
        <div class="grid grid--3 reveal" aria-hidden="true">${[0, 1, 2].map(() => `<figure class="photo photo--ratio-3-4">${portraitPlaceholder(false)}</figure>`).join("")}</div>
      </div>`;

  return {
    html: `
    <section class="hero"><div class="container hero__grid">
      <div class="hero__copy">
        <span class="eyebrow hero__fade" data-d="0">Clinic &amp; Implant Center</span>
        <h1 class="display hero__title" aria-label="Precision. Comfort. Care.">
          <span class="line" aria-hidden="true"><span data-d="80">Precision.</span></span>
          <span class="line" aria-hidden="true"><span data-d="200">Comfort.</span></span>
          <span class="line" aria-hidden="true"><span data-d="320"><em>Care.</em></span></span>
        </h1>
        <p class="lead hero__fade" data-d="520">Contemporary dentistry in a calm space shaped by natural stone, warm wood and soft light.</p>
        <div class="btn-row hero__fade" data-d="640">
          <a class="btn btn--primary" href="/booking" data-link>Request an appointment ${arrow}</a>
          <a class="btn btn--ghost" href="/treatments" data-link>Explore treatments</a>
        </div>
        <div class="hero__meta hero__fade" data-d="760">
          <span>Call <a href="tel:+38349536944">+383 49 536 944</a></span>
          <span>Online requests are confirmed by the clinic</span>
        </div>
      </div>
      <div class="hero__visual">
        ${photo("reception", { arch: true, ratio: null, reveal: false, eager: true })}
        <div class="hero__badge"><span class="icon-tile">${icon("calendar")}</span><span>Request an appointment online in a few minutes</span></div>
      </div>
    </div></section>

    <section class="section section--sand"><div class="container split">
      <div class="photo-pair">
        ${photo("hallway", { ratio: "3-4" })}
        ${photo("walnut", { ratio: "3-4" })}
      </div>
      <div>
        <span class="eyebrow reveal">The clinic</span>
        <h2 class="h2 reveal" style-gap>A calm, considered space for dental care.</h2>
        <p class="lead reveal">Travertine underfoot, limewash walls and fluted walnut — Quantum Dental was designed to feel quiet and unhurried from the moment you arrive at the curved steel reception.</p>
        <div class="features" data-stagger>
          <div class="feature reveal"><p class="feature__title">Natural materials</p><p class="muted small">Stone, wood and soft architectural light throughout the interior.</p></div>
          <div class="feature reveal"><p class="feature__title">Simple requests</p><p class="muted small">Choose a dentist and a preferred time online; the clinic confirms with you.</p></div>
          <div class="feature reveal"><p class="feature__title">Direct contact</p><p class="muted small">Prefer to talk? Call <a class="text-link" href="tel:+38349536944">049-536-944</a>.</p></div>
          <div class="feature reveal"><p class="feature__title">Travelling patients</p><p class="muted small">Coming from another city or country? <a class="text-link" href="/travel" data-link>Read our guidance</a>.</p></div>
        </div>
      </div>
    </div></section>

    <section class="section"><div class="container">
      <div class="section-head section-head--split">
        <div class="stack"><span class="eyebrow reveal">Treatments</span><h2 class="h2 reveal">Treatment areas</h2></div>
        <div class="stack"><p class="muted reveal">An overview of common areas of dental care and what to expect at a consultation.</p>
          <a class="link-arrow reveal" href="/treatments" data-link>View all treatments ${icon("arrow")}</a></div>
      </div>
      ${treatmentNotice()}
      <div class="grid grid--4" data-stagger style-mt>${TREATMENTS.slice(0, 4).map((t) => treatmentCard(t, { compact: true })).join("")}</div>
    </div></section>

    <section class="section section--sand"><div class="container">
      <div class="section-head"><span class="eyebrow reveal">Meet the team</span><h2 class="h2 reveal">Our dentists</h2></div>
      ${teamHtml}
    </div></section>

    <section class="section"><div class="container">
      <div class="section-head section-head--split">
        <div class="stack"><span class="eyebrow reveal">Inside the clinic</span><h2 class="h2 reveal">Interior</h2></div>
        <p class="muted reveal">Select an image to view it larger. Use the arrow keys to move between images.</p>
      </div>
      <div class="gallery" data-gallery data-stagger>
        ${GALLERY.map((slot, i) => `<button type="button" class="gallery__item reveal" data-index="${i}" aria-label="View larger: ${esc(PHOTOS[slot].alt)}">
          ${photo(slot, { ratio: null, reveal: false })}<span class="gallery__zoom" aria-hidden="true">${icon("expand")}</span></button>`).join("")}
      </div>
    </div></section>

    ${ctaBand()}

    <section class="section"><div class="container split">
      <div class="stack">
        <span class="eyebrow reveal">Contact</span>
        <h2 class="h2 reveal">Visit or get in touch</h2>
        <p class="muted reveal">The quickest way to reach the clinic is by phone. You can also send a message online.</p>
        <div class="btn-row reveal"><a class="btn btn--dark" href="/contact" data-link>Contact page</a></div>
      </div>
      <div class="reveal">${infoRows(ctx.config.clinic)}</div>
    </div></section>`,
    mount(root) { mountGallery(root); },
  };
}

function galleryItems() {
  return GALLERY.map((slot) => {
    const p = PHOTOS[slot];
    return {
      html: p.src ? `<img src="${esc(p.src)}" alt="${esc(p.illustration ? `Illustration: ${p.alt}` : p.alt)}">` : `<div role="img" aria-label="Photo placeholder: ${esc(p.alt)}">${placeholderInner(slot)}</div>`,
      caption: !p.src ? `${p.alt} — photograph pending` : p.illustration ? `${p.alt} — illustration; clinic photograph to follow` : p.alt,
    };
  });
}
function mountGallery(root) {
  const g = $("[data-gallery]", root);
  if (!g) return;
  const items = galleryItems();
  g.addEventListener("click", (e) => {
    const b = e.target.closest(".gallery__item");
    if (b) openLightbox(items, Number(b.dataset.index), b);
  });
}

/* ===================================================================== TREATMENTS */
export function treatments() {
  return {
    html: `
    ${pageHero({ eyebrow: "Treatments", title: "Treatment areas", lead: "Clear, general information about common areas of dental care. Select a treatment to read more or request a consultation." })}
    <section class="section"><div class="container">
      ${treatmentNotice()}
      <div class="grid grid--3" data-stagger style-mt>${TREATMENTS.map((t) => treatmentCard(t)).join("")}</div>
    </div></section>
    <section class="section section--sand"><div class="container container--narrow">
      <div class="section-head"><span class="eyebrow reveal">Questions</span><h2 class="h2 reveal">About appointment requests</h2></div>
      <div class="reveal">${accordion(FAQ_BOOKING, "faq-booking")}</div>
    </div></section>
    ${ctaBand("Not sure where to start?", "Request a general consultation. The dentist will discuss your concerns and explain your options.")}`,
    mount(root) { initAccordions(root); },
  };
}

export function treatmentDetail(ctx) {
  const t = TREATMENTS.find((x) => x.slug === ctx.params[0]);
  if (!t) return notFound();
  const related = ctx.config.specialists.filter((s) => !s.generic && Array.isArray(s.treatments) && s.treatments.includes(t.slug));
  const idx = TREATMENTS.indexOf(t);
  const next = TREATMENTS[(idx + 1) % TREATMENTS.length];
  return {
    title: `${t.name} — Quantum Dental`,
    description: t.short,
    html: `
    ${pageHero({ crumbs: crumb([["/", "Home"], ["/treatments", "Treatments"], ["", t.name]]), title: esc(t.name), lead: esc(t.short),
      extra: t.verified ? "" : `<div class="reveal"><span class="tag tag--olive">Availability to be confirmed with the clinic</span></div>` })}
    <section class="section"><div class="container detail">
      <article class="prose">
        <h2 class="reveal">Overview</h2>
        <p class="reveal">${esc(t.overview)}</p>
        <h2 class="reveal">What it involves</h2>
        <ul class="reveal">${t.explanation.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <h2 class="reveal">A typical consultation</h2>
        <ol class="steps-list reveal">${CONSULTATION_STEPS.map((s) => `<li><div><strong>${esc(s.title)}</strong><p>${esc(s.text)}</p></div></li>`).join("")}</ol>
        <h2 class="reveal">Things to consider</h2>
        <ul class="reveal">${t.considerations.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <div class="notice reveal" style-mt>${icon("info")}<p>This page is general information, not personal medical advice. Your dentist will advise you on what is suitable after an examination.</p></div>
      </article>
      <aside class="aside-card">
        <div class="card stack">
          <span class="icon-tile">${icon(t.icon)}</span>
          <h2 class="h3">Request a consultation</h2>
          <p class="muted small">Send a request with your preferred date and time. The clinic will contact you to confirm.</p>
          <a class="btn btn--primary btn--block" href="/booking?topic=${t.slug}" data-link>Book consultation</a>
          <a class="btn btn--ghost btn--block" href="tel:+38349536944">${icon("phone")} Call 049-536-944</a>
        </div>
        <div class="card card--sand stack">
          <p class="info-list__label">Associated specialist</p>
          ${related.length ? related.map((s) => `<a class="link-arrow" href="/doctors/${esc(s.id)}" data-link>${esc(s.name)} ${icon("arrow")}</a>`).join("")
            : `<p class="small muted">Specialist information will be shown once confirmed by the clinic.</p>`}
        </div>
        <a class="link-arrow" href="/treatments/${next.slug}" data-link>Next: ${esc(next.name)} ${icon("arrow")}</a>
      </aside>
    </div></section>`,
  };
}

/* ===================================================================== RESULTS */
export function results() {
  const filters = [{ slug: "all", name: "All" }, ...TREATMENTS.map((t) => ({ slug: t.slug, name: t.name }))];
  return {
    html: `
    ${pageHero({ eyebrow: "Results", title: "Before &amp; after", lead: "Treatment results will only be shown here when the clinic has the patient's written consent to publish them." })}
    <section class="section"><div class="container">
      <div class="chips reveal" role="group" aria-label="Filter results by treatment">
        ${filters.map((f, i) => `<button type="button" class="chip" data-filter="${f.slug}" aria-pressed="${i === 0}">${esc(f.name)}</button>`).join("")}
      </div>
      <div data-results style-mt-lg aria-live="polite"></div>
    </div></section>
    <section class="section section--sand"><div class="container split">
      <div class="stack">
        <span class="eyebrow reveal">The viewer</span>
        <h2 class="h2 reveal">How published results will appear</h2>
        <p class="muted reveal">Each case can be compared with a before-and-after slider and opened full-screen. Drag the handle or use the arrow keys.</p>
        <div class="reveal"><span class="tag tag--olive">Illustration only — no patient images</span></div>
      </div>
      <div class="reveal">${compareSlider({
        beforeHtml: `<div class="placeholder placeholder--dark"><svg class="placeholder__motif" viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice"><path d="M40 260c80-40 240-40 320 0M40 300c80 40 240 40 320 0"/></svg><div class="placeholder__label"><strong>Before</strong><span class="small">Example layout</span></div></div>`,
        afterHtml: `<div class="placeholder"><svg class="placeholder__motif" viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice"><path d="M40 260c80-40 240-40 320 0M40 300c80 40 240 40 320 0"/></svg><div class="placeholder__label placeholder__label--right"><strong>After</strong><span class="small">Example layout</span></div></div>`,
        label: "Example comparison layout",
      })}</div>
    </div></section>
    ${ctaBand()}`,
    mount(root) {
      const out = $("[data-results]", root);
      const render = (slug) => {
        const list = RESULTS.filter((r) => slug === "all" || r.treatment === slug);
        if (!list.length) {
          const name = slug === "all" ? "" : ` for ${TREATMENTS.find((t) => t.slug === slug)?.name}`;
          out.innerHTML = `<div class="empty">
            <span class="empty__icon">${icon("compare")}</span>
            <h2 class="h3">No published cases${esc(name)} yet</h2>
            <p>We don't show stock photos or simulated results. Cases will appear here once patients have consented to their publication.</p>
            <div class="btn-row"><a class="btn btn--ghost btn--sm" href="/treatments" data-link>Explore treatments</a></div>
          </div>`;
          return;
        }
        out.innerHTML = `<div class="grid grid--2">${list.map((r, i) => `<article class="card stack">
          ${compareSlider({ beforeHtml: `<img src="${esc(r.before.src)}" alt="${esc(r.before.alt)}" loading="lazy">`, afterHtml: `<img src="${esc(r.after.src)}" alt="${esc(r.after.alt)}" loading="lazy">`, label: r.title })}
          <h3 class="h4">${esc(r.title)}</h3>${r.note ? `<p class="small muted">${esc(r.note)}</p>` : ""}
          <button type="button" class="btn btn--ghost btn--sm" data-open="${i}">${icon("expand")} View full screen</button></article>`).join("")}</div>`;
        initCompare(out);
        $$("[data-open]", out).forEach((b) => b.addEventListener("click", () => {
          const items = list.flatMap((r) => [{ html: `<img src="${esc(r.before.src)}" alt="${esc(r.before.alt)}">`, caption: `${r.title} — before` }, { html: `<img src="${esc(r.after.src)}" alt="${esc(r.after.alt)}">`, caption: `${r.title} — after` }]);
          openLightbox(items, Number(b.dataset.open) * 2, b);
        }));
      };
      $$("[data-filter]", root).forEach((b) => b.addEventListener("click", () => {
        $$("[data-filter]", root).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        render(b.dataset.filter);
      }));
      render("all");
      initCompare(root);
    },
  };
}

/* ===================================================================== DOCTORS */
export function doctors(ctx) {
  const list = ctx.config.specialists.filter((s) => !s.generic);
  const demoNote = ctx.config.demo ? `<div class="notice notice--warn reveal">${icon("alert")}<p><strong>Development demo data is switched on.</strong> The profiles below are placeholders for testing and are not real clinic staff. Turn off <code>DEMO_DATA</code> before publishing.</p></div>` : "";
  return {
    html: `
    ${pageHero({ eyebrow: "Doctors", title: "Our dentists", lead: "Choose a dentist to view their profile, or book directly with the dentist of your choice." })}
    <section class="section"><div class="container">
      ${demoNote}
      ${list.length ? `<div class="grid grid--3" data-stagger style-mt>${list.map(doctorCard).join("")}</div>`
        : `<div class="empty reveal">
            <span class="empty__icon">${icon("users")}</span>
            <h2 class="h3">Team profiles are being prepared</h2>
            <p>Profiles will be published once each dentist's details and photograph have been confirmed by the clinic. In the meantime, you can request an appointment with the first available dentist.</p>
            <div class="btn-row"><a class="btn btn--primary" href="/booking?specialist=first-available" data-link>Request an appointment</a><a class="btn btn--ghost" href="tel:+38349536944">${icon("phone")} Call the clinic</a></div>
          </div>`}
    </div></section>
    ${ctaBand()}`,
  };
}

export function doctorDetail(ctx) {
  const s = ctx.config.specialists.find((x) => x.id === ctx.params[0] && !x.generic);
  if (!s) return notFound();
  return {
    title: `${s.name} — Quantum Dental`,
    description: `${s.name}${s.specialty ? `, ${s.specialty}` : ""} at Quantum Dental Clinic & Implant Center.`,
    html: `
    ${pageHero({ crumbs: crumb([["/", "Home"], ["/doctors", "Doctors"], ["", s.name]]), title: "" , lead: ""}).replace('<h1 class="h1 reveal"></h1>', "")}
    <section class="section"><div class="container detail">
      <article class="split split--profile">
        <div class="reveal">${s.photo ? `<figure class="photo photo--ratio-4-5"><img src="${esc(s.photo)}" alt="Portrait of ${esc(s.name)}"></figure>` : `<figure class="photo photo--ratio-4-5">${portraitPlaceholder(s.demo)}</figure>`}</div>
        <div class="stack">
          ${s.demo ? `<span class="tag tag--demo reveal">Demo profile · not a real person</span>` : ""}
          <h1 class="h1 reveal">${esc(s.name)}</h1>
          <p class="lead reveal">${esc(s.title || "")}${s.specialty ? ` · ${esc(s.specialty)}` : ""}</p>
          ${s.bio ? `<p class="reveal">${esc(s.bio)}</p>` : ""}
          <div class="reveal"><p class="info-list__label">Qualifications</p>
            ${s.qualifications?.length ? `<ul class="prose">${s.qualifications.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>` : `<p class="muted small">To be confirmed.</p>`}</div>
          ${s.appointment_types?.length ? `<div class="reveal"><p class="info-list__label">Appointment types</p><div class="chips" style-mt-sm>${s.appointment_types.map((a) => `<span class="tag">${esc(a)}</span>`).join("")}</div></div>` : ""}
        </div>
      </article>
      <aside class="aside-card"><div class="card stack">
        <h2 class="h3">Book with ${esc(s.name)}</h2>
        <p class="muted small">This dentist will be preselected in the appointment form.</p>
        <a class="btn btn--primary btn--block" href="/booking?specialist=${encodeURIComponent(s.id)}" data-link>Book with this dentist</a>
        <a class="link-arrow" href="/doctors" data-link>${icon("arrowLeft")} All dentists</a>
      </div></aside>
    </div></section>`,
  };
}

/* ===================================================================== PRICING */
export function pricing() {
  const has = PRICES.length > 0;
  return {
    html: `
    ${pageHero({ eyebrow: "Pricing", title: "Pricing", lead: "Treatment costs depend on your individual needs. Here's how to get a clear, current price." })}
    <section class="section"><div class="container">
      ${has ? `<div class="grid grid--3" data-stagger>${PRICES.map((c) => `<article class="card price-card reveal"><h2 class="h3">${esc(c.category)}</h2>
          ${c.items.map((it) => `<div class="price-row"><span>${esc(it.name)}${it.note ? `<br><span class="small muted">${esc(it.note)}</span>` : ""}</span><span class="price-row__amount">${esc(it.price)}</span></div>`).join("")}
          <a class="btn btn--ghost btn--sm" href="/booking" data-link>Book consultation</a></article>`).join("")}</div>`
        : `<div class="split">
            <div class="card stack reveal">
              <span class="icon-tile">${icon("tag")}</span>
              <h2 class="h2">Contact the clinic for current prices</h2>
              <p class="muted">Official prices have not been published on this website yet. Please call the clinic or send an enquiry and the team will provide current pricing.</p>
              <div class="btn-row"><a class="btn btn--primary" href="tel:+38349536944">${icon("phone")} Call 049-536-944</a>
                <a class="btn btn--ghost" href="/contact?subject=${encodeURIComponent("Price enquiry")}" data-link>Send a price enquiry</a></div>
            </div>
            <div class="stack">
              <h2 class="h3 reveal">Helpful to know</h2>
              <ol class="steps-list" data-stagger>
                <li class="reveal"><div><strong>Costs follow an assessment</strong><p>Many treatments can only be priced accurately after an examination, and sometimes imaging.</p></div></li>
                <li class="reveal"><div><strong>Ask for a written estimate</strong><p>Before agreeing to treatment, you can ask for the estimated cost of each stage in writing.</p></div></li>
                <li class="reveal"><div><strong>Compare your options</strong><p>Where more than one approach is suitable, ask how the costs and timelines differ.</p></div></li>
              </ol>
            </div>
          </div>`}
    </div></section>
    ${ctaBand()}`,
  };
}

/* ===================================================================== TRAVEL */
export function travel(ctx) {
  return {
    html: `
    ${pageHero({ eyebrow: "Travelling patients", title: "Visiting from another city or country", lead: "If you are planning to travel for dental care, a little preparation makes your visit easier. Here is how to get started." })}
    <section class="section"><div class="container split split--top">
      <div>
        <h2 class="h2 reveal">Plan your visit</h2>
        <ol class="steps-list" data-stagger>
          <li class="reveal"><div><strong>Contact the clinic early</strong><p>Call <a class="text-link" href="tel:+38349536944">+383 49 536 944</a> before booking travel so the clinic can advise on timing.</p></div></li>
          <li class="reveal"><div><strong>Request an appointment</strong><p>Use the online form and tick “I'm travelling from another city or country”. Include your travel dates in the message.</p></div></li>
          <li class="reveal"><div><strong>Gather your records</strong><p>Recent X-rays or scans, a list of medications and allergies, and notes from previous treatment can help the consultation.</p></div></li>
          <li class="reveal"><div><strong>Wait for confirmation</strong><p>Your appointment is confirmed only when the clinic contacts you. Consider flexible travel bookings until then.</p></div></li>
        </ol>
        <div class="btn-row reveal" style-mt><a class="btn btn--primary" href="/booking?traveling=1" data-link>Request an appointment ${arrow}</a></div>
      </div>
      <div class="stack">
        <div class="card stack reveal">
          <h2 class="h3">Location &amp; directions</h2>
          ${ctx.config.clinic.address ? `<p>${esc(ctx.config.clinic.address)}</p>` : `<p class="muted small">The clinic's address and directions will be published here once confirmed. Please call the clinic for directions in the meantime.</p>`}
          <div class="map-ph">
            <svg class="map-ph__grid" viewBox="0 0 400 250" preserveAspectRatio="none" aria-hidden="true"><path d="M0 60h400M0 140h400M0 200h400M80 0v250M200 0v250M320 0v250M0 230L400 20"/></svg>
            <div class="map-ph__inner"><span class="map-ph__pin">${icon("pin")}</span><p class="small"><strong>Map pending</strong><br>Shown once the address is verified.</p></div>
          </div>
        </div>
        <div class="notice reveal">${icon("info")}<p>This website does not arrange travel, accommodation or transfers. Please ask the clinic directly about any support available for travelling patients.</p></div>
      </div>
    </div></section>
    <section class="section section--sand"><div class="container container--narrow">
      <div class="section-head"><span class="eyebrow reveal">Questions</span><h2 class="h2 reveal">Travelling patients FAQ</h2></div>
      <div class="reveal">${accordion(FAQ_TRAVEL, "faq-travel")}</div>
    </div></section>
    ${ctaBand()}`,
    mount(root) { initAccordions(root); },
  };
}

/* ===================================================================== CONTACT */
export function contact(ctx) {
  const subject = (ctx.query.get("subject") || "").slice(0, 150);
  return {
    html: `
    ${pageHero({ eyebrow: "Contact", title: "Get in touch", lead: "Call the clinic, send a message, or request an appointment online." })}
    <section class="section"><div class="container split split--top">
      <div class="stack">
        <div class="reveal">${infoRows(ctx.config.clinic)}</div>
        <div class="btn-row reveal"><a class="btn btn--primary" href="/booking" data-link>Request an appointment ${arrow}</a><a class="btn btn--ghost" href="tel:+38349536944">${icon("phone")} Call now</a></div>
        <div class="map-ph reveal">
          <svg class="map-ph__grid" viewBox="0 0 400 250" preserveAspectRatio="none" aria-hidden="true"><path d="M0 60h400M0 140h400M0 200h400M80 0v250M200 0v250M320 0v250M0 230L400 20"/></svg>
          <div class="map-ph__inner"><span class="map-ph__pin">${icon("pin")}</span><p class="small"><strong>Map pending</strong><br>Shown once the address is verified.</p></div>
        </div>
      </div>
      <div class="card reveal" data-contact-card>
        <h2 class="h3">Send a message</h2>
        <p class="muted small" style-mb>For appointment requests, please use the <a class="text-link" href="/booking" data-link>booking form</a>. Don't include detailed medical information.</p>
        <form class="form" novalidate data-contact-form>
          <div class="hp" aria-hidden="true"><label>Website <input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>
          <div class="form-row form-row--2">
            <div class="field"><label class="field__label" for="c-name">Name <span class="req" aria-hidden="true">*</span></label>
              <input class="input" id="c-name" name="name" autocomplete="name" required maxlength="120"></div>
            <div class="field"><label class="field__label" for="c-email">Email <span class="req" aria-hidden="true">*</span></label>
              <input class="input" id="c-email" name="email" type="email" autocomplete="email" inputmode="email" required maxlength="254"></div>
          </div>
          <div class="field"><label class="field__label" for="c-subject">Subject <span class="req" aria-hidden="true">*</span></label>
            <input class="input" id="c-subject" name="subject" required maxlength="150" value="${esc(subject)}"></div>
          <div class="field"><label class="field__label" for="c-message">Message <span class="req" aria-hidden="true">*</span></label>
            <textarea class="textarea" id="c-message" name="message" required maxlength="3000" rows="6"></textarea>
            <p class="field__hint" id="c-message-hint">At least 10 characters.</p></div>
          <div class="form-alert" data-form-alert aria-live="assertive"></div>
          <button type="submit" class="btn btn--primary">Send message</button>
          <p class="small muted">Required fields are marked <span class="req" aria-hidden="true">*</span>. See our <a class="text-link" href="/privacy" data-link>privacy notice</a>.</p>
        </form>
      </div>
    </div></section>`,
    mount(root) { mountContactForm(root, ctx); },
  };
}

function mountContactForm(root, ctx) {
  const form = $("[data-contact-form]", root);
  const card = $("[data-contact-card]", root);
  const alertBox = $("[data-form-alert]", form);
  const started = performance.now();
  let key = newKey();
  const rules = {
    name: (v) => (v.trim().length < 2 ? "Please enter your name." : ""),
    email: (v) => (!v.trim() ? "Please enter your email address." : !validEmail(v.trim()) ? "Please enter a valid email address, e.g. name@example.com." : ""),
    subject: (v) => (v.trim().length < 2 ? "Please add a subject." : ""),
    message: (v) => (v.trim().length < 10 ? "Please write a message of at least 10 characters." : ""),
  };
  Object.keys(rules).forEach((name) => {
    const el = form.elements[name];
    el.addEventListener("blur", () => { if (el.value) fieldError(el, rules[name](el.value)); });
    el.addEventListener("input", () => { if (el.closest(".field").classList.contains("has-error")) fieldError(el, rules[name](el.value)); });
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    alertBox.innerHTML = "";
    let firstBad = null;
    for (const [name, rule] of Object.entries(rules)) {
      const msg = rule(form.elements[name].value);
      fieldError(form.elements[name], msg);
      if (msg && !firstBad) firstBad = form.elements[name];
    }
    if (firstBad) { firstBad.focus(); form.classList.add("shake"); setTimeout(() => form.classList.remove("shake"), 400); return; }
    const btn = $("button[type=submit]", form);
    btn.classList.add("is-loading"); btn.disabled = true; btn.setAttribute("aria-busy", "true");
    try {
      const res = ctx.config.static ? { ok: true, created: true, ref: localRef("QM"), email: {} } : await api("/api/contact", { method: "POST", body: {
        idempotencyKey: key, name: form.elements.name.value, email: form.elements.email.value,
        subject: form.elements.subject.value, message: form.elements.message.value,
        website: form.elements.website.value, elapsedMs: Math.round(performance.now() - started),
      } });
      if (ctx.config.formsubmit && res.created) {
        const fsStatus = await sendFormSubmit(ctx.config.formsubmit, {
          Reference: res.ref, Name: form.elements.name.value, Subject: form.elements.subject.value, Message: form.elements.message.value,
        }, { subject: `Website message ${res.ref}: ${form.elements.subject.value}`, replyTo: form.elements.email.value });
        res.email = { clinic: fsStatus === "sent" ? "accepted" : "failed" };
      }
      const delivered = ["accepted", "outbox"].includes(res.email?.clinic);
      card.innerHTML = `<div class="confirm" tabindex="-1">
        <span class="confirm__icon">${icon("check")}</span>
        <h2 class="h2">Message received</h2>
        <p class="confirm__ref">${esc(res.ref)}</p>
        <p class="muted">${delivered ? "Your message has been saved and the clinic team has been notified by email." : "Your message has been saved. The email notification to the clinic could not be sent right now, so a reply may take longer — for anything urgent, please call."}</p>
        <div class="confirm__actions"><a class="btn btn--ghost" href="tel:+38349536944">${icon("phone")} Call the clinic</a><button type="button" class="btn btn--dark" data-new-msg>Send another message</button></div>
      </div>`;
      $(".confirm", card).focus();
      $("[data-new-msg]", card).addEventListener("click", () => window.dispatchEvent(new CustomEvent("qd:rerender")));
    } catch (err) {
      if (err.fields) {
        Object.entries(err.fields).forEach(([k, v]) => form.elements[k] && fieldError(form.elements[k], v));
      }
      alertBox.innerHTML = `<div class="notice notice--error" role="alert">${icon("alert")}<p><strong>Your message was not sent.</strong> ${esc(err.message)} You can also call <a class="text-link" href="tel:+38349536944">+383 49 536 944</a>.</p></div>`;
    } finally {
      btn.classList.remove("is-loading"); btn.disabled = false; btn.removeAttribute("aria-busy");
    }
  });
}

/* ===================================================================== PRIVACY */
export function privacy() {
  return {
    html: `
    ${pageHero({ eyebrow: "Privacy", title: "Privacy notice", extra: `<div class="reveal"><span class="tag tag--olive">Draft — to be reviewed and approved by the clinic</span></div>` })}
    <section class="section"><div class="container container--narrow prose">
      <p>This notice explains how information submitted through this website is handled.</p>
      <h2>What we collect</h2>
      <ul><li>Appointment requests: your name, email address, phone number, preferred dentist, reason category, preferred date and time, and any optional message.</li>
          <li>Contact form messages: your name, email address, subject and message.</li></ul>
      <h2>Why</h2>
      <p>Only to respond to your request or message and arrange your appointment. Submitting a request does not create a confirmed appointment.</p>
      <h2>Who can see it</h2>
      <p>Authorised clinic staff. Notification emails to staff contain your contact details and request summary; optional messages are not included in those emails and can only be viewed by logged-in staff.</p>
      <h2>Please don't send detailed medical information</h2>
      <p>The online forms are not intended for medical records. Health details are best discussed in person with your dentist.</p>
      <h2>Your choices</h2>
      <p>To ask about, correct or delete information you submitted, call <a class="text-link" href="tel:+38349536944">+383 49 536 944</a>.</p>
    </div></section>`,
  };
}

/* ===================================================================== 404 */
export function notFound() {
  return {
    status: 404,
    title: "Page not found — Quantum Dental",
    html: `<section class="container notfound">
      <p class="notfound__num" aria-hidden="true">404</p>
      <h1 class="h1">This page could not be found</h1>
      <p class="lead">The link may be out of date, or the page may have moved.</p>
      <div class="btn-row"><a class="btn btn--dark" href="/" data-link>${icon("home")} Back to home</a><a class="btn btn--ghost" href="/contact" data-link>Contact the clinic</a></div>
    </section>`,
  };
}
