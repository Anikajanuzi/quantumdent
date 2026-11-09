"""Browser tests (Playwright). Starts its own server on a temp DB with the dev outbox.
Run:  python3 tests/test_e2e.py            (CHROME_PATH=/path/to/chrome to use a system browser)
Screenshots are written to tests/artifacts/."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server  # noqa: E402
from app.config import Config  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

ART = ROOT / "tests" / "artifacts"
ART.mkdir(parents=True, exist_ok=True)
TOKEN = "e2e-admin-token-0123456789"
PAGES = ["/", "/treatments", "/treatments/dental-implants", "/results", "/doctors", "/pricing", "/travel", "/booking", "/contact", "/privacy"]
WIDTHS = [320, 375, 390, 430, 768, 1024, 1280, 1440]
results: list[tuple[str, bool, str]] = []


def check(name):
    def deco(fn):
        def run(*a):
            try:
                fn(*a)
                results.append((name, True, ""))
                print(f"  PASS  {name}")
            except Exception as e:
                results.append((name, False, f"{type(e).__name__}: {e}"))
                print(f"  FAIL  {name}\n        {type(e).__name__}: {str(e)[:400]}")
                traceback.print_exc(limit=2, file=sys.stdout)
        return run
    return deco


def start():
    tmp = Path(tempfile.mkdtemp())
    cfg = Config(host="127.0.0.1", port=0, site_url="http://127.0.0.1", db_path=tmp / "e2e.sqlite3", email_backend="outbox",
                 outbox_dir=tmp / "outbox", clinic_notify_emails=["staff.a@example.test", "staff.b@example.test", "staff.c@example.test"],
                 admin_token=TOKEN, session_secret="e" * 64, booking_rate_limit=100, contact_rate_limit=100)
    httpd = server.make_server(cfg)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}", tmp


def main():
    httpd, base, tmp = start()
    tomorrow = (datetime.now(ZoneInfo("Europe/Belgrade")) + timedelta(days=1)).date().isoformat()
    exe = os.environ.get("CHROME_PATH") or (shutil.which("google-chrome") or None)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else p.chromium.launch()

        def new_page(width=1280, height=900, **kw):
            ctx = browser.new_context(viewport={"width": width, "height": height}, **kw)
            pg = ctx.new_page()
            pg.errors = []
            pg.on("pageerror", lambda e: pg.errors.append(f"pageerror: {e}"))
            pg.on("console", lambda m: m.type == "error" and "fonts.g" not in m.text and "ERR_" not in m.text and pg.errors.append(f"console: {m.text}"))
            return pg

        def settle(pg):
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(250)

        # ---------- responsive sweep ----------
        @check("No horizontal overflow, no JS errors on every page at 320–1440px")
        def responsive():
            problems = []
            for w in WIDTHS:
                pg = new_page(w, 860, reduced_motion="reduce")
                for path in PAGES:
                    pg.goto(base + path)
                    settle(pg)
                    over = pg.evaluate("""() => {
                      const vw = document.documentElement.clientWidth;
                      const bad = [...document.querySelectorAll('main *, header *, footer *')].filter(el => {
                        const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
                        return r.width > 0 && (r.right > vw + 1 || r.left < -1) && cs.position !== 'fixed' && !el.closest('.hp,.sr-only,.skip-link,.mobile-menu');
                      }).slice(0, 3).map(el => el.tagName + '.' + el.className.toString().slice(0, 40));
                      return { sw: document.documentElement.scrollWidth, vw, bad };
                    }""")
                    if over["sw"] > over["vw"] or over["bad"]:
                        problems.append(f"{w}px {path}: scrollWidth={over['sw']} vw={over['vw']} {over['bad']}")
                    if w in (375, 1280) and path in ("/", "/booking", "/treatments", "/contact"):
                        pg.screenshot(path=str(ART / f"{w}{path.replace('/', '_') or '_home'}.png"), full_page=True)
                if pg.errors:
                    problems += [f"{w}px: {e}" for e in pg.errors[:3]]
                pg.context.close()
            assert not problems, "\n".join(problems[:15])
        responsive()

        # ---------- desktop nav ----------
        @check("Desktop nav: one-line labels, no overlap, active indicator, history back/forward, direct links")
        def nav():
            for w in (1200, 1280, 1440):
                pg = new_page(w)
                pg.goto(base + "/")
                settle(pg)
                boxes = pg.eval_on_selector_all(".primary-nav a", "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right, r.height, e.textContent] })")
                assert len(boxes) == 8
                for (l1, r1, h1, t1), (l2, *_rest) in zip(boxes, boxes[1:]):
                    assert r1 < l2, f"{w}px nav items overlap: {t1}"
                assert all(h < 50 for *_x, h, _t in boxes), f"{w}px nav label wraps: {boxes}"
                actions = pg.eval_on_selector(".site-header__actions", "e => e.getBoundingClientRect().left")
                assert boxes[-1][1] < actions, f"{w}px nav collides with header actions"
                pg.context.close()
            pg = new_page(1280)
            pg.goto(base + "/")
            settle(pg)
            pg.evaluate("window.scrollTo(0, 1500)")
            pg.click(".primary-nav >> text=Treatments")
            expect(pg).to_have_url(base + "/treatments")
            expect(pg.locator("h1")).to_have_text("Treatment areas")
            expect(pg.locator('.primary-nav a[aria-current="page"]')).to_have_text("Treatments")
            assert pg.evaluate("window.scrollY") == 0, "new page should start at top"
            assert "Treatments" in pg.title()
            pg.wait_for_timeout(400)
            assert pg.eval_on_selector(".primary-nav__indicator", "e => getComputedStyle(e).opacity") == "1"
            pg.click(".primary-nav >> text=Doctors")
            expect(pg).to_have_url(base + "/doctors")
            pg.go_back(); expect(pg).to_have_url(base + "/treatments"); expect(pg.locator("h1")).to_have_text("Treatment areas")
            pg.go_back(); expect(pg).to_have_url(base + "/")
            pg.go_forward(); expect(pg).to_have_url(base + "/treatments")
            pg.goto(base + "/travel"); settle(pg)
            expect(pg.locator("h1")).to_contain_text("Visiting from another city")
            expect(pg.locator('.primary-nav a[aria-current="page"]')).to_have_text("Travel")
            assert not pg.errors, pg.errors
            pg.goto(base + "/does-not-exist"); settle(pg)  # intentional 404 response
            expect(pg.locator("h1")).to_have_text("This page could not be found")
            pg.context.close()
        nav()

        @check("Mobile menu: opens, focus moves in, Escape closes and returns focus, link navigates")
        def mobile_menu():
            pg = new_page(375, 760)
            pg.goto(base + "/"); settle(pg)
            assert pg.is_visible(".action-bar"), "sticky action bar visible on mobile"
            pg.click(".menu-toggle")
            expect(pg.locator("#mobile-menu")).to_be_visible()
            expect(pg.locator(".menu-toggle")).to_have_attribute("aria-expanded", "true")
            assert pg.evaluate("document.activeElement.matches('[data-close-menu]')")
            for _ in range(12):
                pg.keyboard.press("Tab")
                assert pg.evaluate("!!document.activeElement.closest('#mobile-menu')"), "focus escaped the open menu"
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(500)
            expect(pg.locator("#mobile-menu")).to_be_hidden()
            assert pg.evaluate("document.activeElement.classList.contains('menu-toggle')")
            pg.click(".menu-toggle"); pg.wait_for_timeout(450)
            pg.click("#mobile-menu >> text=Pricing")
            expect(pg).to_have_url(base + "/pricing")
            pg.wait_for_timeout(500)
            expect(pg.locator("#mobile-menu")).to_be_hidden()
            assert not pg.evaluate("document.body.classList.contains('menu-open')")
            # bottom bar must not cover the footer's last content
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(200)
            bar_top = pg.eval_on_selector(".action-bar", "e => e.getBoundingClientRect().top")
            last = pg.eval_on_selector(".site-footer__base", "e => e.getBoundingClientRect().bottom")
            assert last <= bar_top + 1, f"action bar covers footer ({last} > {bar_top})"
            pg.context.close()
        mobile_menu()

        # ---------- interactions ----------
        @check("Gallery lightbox: opens, next/prev, keyboard, Escape restores focus")
        def gallery():
            pg = new_page(1280)
            pg.goto(base + "/"); settle(pg)
            pg.locator(".gallery__item").nth(1).click()
            expect(pg.locator("#lightbox")).to_be_visible()
            expect(pg.locator(".lightbox__count")).to_have_text("2 / 6")
            pg.click("[data-lb-next]"); pg.wait_for_timeout(300)
            expect(pg.locator(".lightbox__count")).to_have_text("3 / 6")
            pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(300)
            expect(pg.locator(".lightbox__count")).to_have_text("2 / 6")
            pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
            expect(pg.locator("#lightbox")).to_be_hidden()
            assert pg.evaluate("document.activeElement.dataset.index") == "1"
            pg.context.close()
        gallery()

        @check("Accordion expands/collapses; results filters and before/after viewer respond")
        def accordion_results():
            pg = new_page(1024)
            pg.goto(base + "/travel"); settle(pg)
            btn = pg.locator(".acc-item__btn").first
            btn.click(); expect(btn).to_have_attribute("aria-expanded", "true")
            expect(pg.locator(".acc-item__panel").first).to_be_visible()
            btn.click(); expect(btn).to_have_attribute("aria-expanded", "false")
            pg.wait_for_timeout(400); expect(pg.locator(".acc-item__panel").first).to_be_hidden()
            pg.goto(base + "/results"); settle(pg)
            pg.click("[data-filter='dental-implants']")
            expect(pg.locator("[data-filter='dental-implants']")).to_have_attribute("aria-pressed", "true")
            expect(pg.locator("[data-results]")).to_contain_text("No published cases for Dental Implants")
            r = pg.locator(".compare__range"); r.focus(); pg.keyboard.press("End")
            assert pg.eval_on_selector(".compare", "e => e.style.getPropertyValue('--pos')") == "100%"
            pg.context.close()
        accordion_results()

        @check("Treatment 'Book consultation' pre-fills the booking topic; treatment Learn more opens detail")
        def treatment_links():
            pg = new_page(1280)
            pg.goto(base + "/treatments"); settle(pg)
            pg.click("text=Learn more about Endodontics >> nth=0") if pg.locator("[aria-label='Learn more about Endodontics']").count() == 0 else pg.click("[aria-label='Learn more about Endodontics']")
            expect(pg).to_have_url(base + "/treatments/endodontics")
            expect(pg.locator("h1")).to_have_text("Endodontics")
            pg.click("text=Book consultation >> nth=0")
            expect(pg).to_have_url(base + "/booking?topic=endodontics")
            pg.click("input[value='first-available'] >> xpath=..")
            pg.click("[data-next]")
            pg.click(f"[data-date='{tomorrow}']"); pg.click("[data-time='11:00']"); pg.click("[data-next]")
            expect(pg.locator("#b-message")).to_have_value("Consultation about: Endodontics")
            expect(pg.locator("#b-reason")).to_have_value("consultation")
            pg.context.close()
        treatment_links()

        # ---------- booking ----------
        @check("Booking: validation (no dentist, no date/time, invalid email, missing fields), past dates disabled")
        def booking_validation():
            pg = new_page(390, 844)
            pg.goto(base + "/booking"); settle(pg)
            pg.click("[data-next]")
            expect(pg.locator("[data-group-error]")).to_contain_text("Please choose a dentist")
            pg.click("input[value='first-available'] >> xpath=..")
            expect(pg.locator("[data-group-error]")).to_have_count(0)
            pg.click("[data-next]")
            pg.click("[data-next]")
            expect(pg.locator("[data-group-error]").first).to_contain_text("preferred date")
            disabled_past = pg.eval_on_selector_all(".calendar__day:disabled", "els => els.length")
            today = datetime.now(ZoneInfo("Europe/Belgrade")).day
            assert disabled_past >= today - 1, "past days must be disabled"
            assert pg.is_disabled("[data-cal='-1']"), "cannot go to previous month"
            pg.click(f"[data-date='{tomorrow}']")
            pg.click("[data-time='09:30']")
            pg.click("[data-next]")
            pg.fill("#b-name", "Mock Patient")
            pg.fill("#b-email", "not-an-email")
            pg.fill("#b-phone", "12")
            pg.click("[data-next]")
            expect(pg.locator("#b-email")).to_have_attribute("aria-invalid", "true")
            expect(pg.locator(".field:has(#b-email) .field__error")).to_contain_text("valid email")
            expect(pg.locator(".field:has(#b-phone) .field__error")).to_contain_text("valid phone")
            expect(pg.locator(".field:has(#b-reason) .field__error")).to_be_visible()
            expect(pg.locator(".field:has(#b-consent) .field__error")).to_be_visible()
            assert pg.evaluate("document.activeElement.id") == "b-email"
            assert not pg.errors, pg.errors
            pg.context.close()
        booking_validation()

        def fill_valid(pg, email="mock.patient@example.test"):
            pg.click("input[value='first-available'] >> xpath=..")
            pg.click("[data-next]")
            pg.click(f"[data-date='{tomorrow}']"); pg.click("[data-time='14:30']"); pg.click("[data-next]")
            pg.fill("#b-name", "Mock Patient"); pg.fill("#b-email", email); pg.fill("#b-phone", "+383 44 000 111")
            pg.select_option("#b-reason", "checkup"); pg.fill("#b-message", "Test only — mock data.")
            pg.check("input[name=traveling]", force=True); pg.check("#b-consent", force=True)
            pg.wait_for_timeout(2600)  # anti-bot minimum fill time
            pg.click("[data-next]")

        @check("Booking: valid request end-to-end, review/edit, double-click submits once, confirmation + .ics")
        def booking_ok():
            pg = new_page(1280)
            pg.goto(base + "/booking"); settle(pg)
            fill_valid(pg)
            expect(pg.locator(".review")).to_contain_text("Mock Patient")
            expect(pg.locator(".review")).to_contain_text("14:30")
            pg.click("[data-edit='2']")
            pg.click("[data-time='15:00']"); pg.click("[data-next]"); pg.click("[data-next]")
            expect(pg.locator(".review")).to_contain_text("15:00")
            before = httpd.RequestHandlerClass.app.db.query("SELECT COUNT(*) c FROM appointments")[0]["c"]
            pg.locator("[data-submit]").dblclick()
            expect(pg.locator(".confirm h2")).to_have_text("Request sent", timeout=10000)
            after = httpd.RequestHandlerClass.app.db.query("SELECT COUNT(*) c FROM appointments")[0]["c"]
            assert after - before == 1, f"double click created {after - before} appointments"
            ref = pg.locator("[data-ref]").inner_text()
            assert ref.startswith("QD-")
            expect(pg.locator(".confirm")).to_contain_text("pending confirmation")
            expect(pg.locator(".confirm")).not_to_contain_text("confirmed appointment")
            expect(pg.locator(".confirm")).to_contain_text("Test mode")  # dev outbox reported honestly
            with pg.expect_download() as dl:
                pg.click("[data-ics]")
            ics = Path(dl.value.path()).read_text()
            assert "STATUS:TENTATIVE" in ics and "PENDING CONFIRMATION" in ics and ref in ics
            assert "DTSTART:" in ics and "T140000Z" in ics or "T130000Z" in ics, ics  # 15:00 CET/CEST -> UTC
            pg.screenshot(path=str(ART / "booking_confirmation_1280.png"), full_page=True)
            pg.click("[data-again]")
            expect(pg.locator(".step h2")).to_have_text("Choose a dentist")
            assert not pg.errors, pg.errors
            pg.context.close()
        booking_ok()

        @check("Booking: server error and network failure show an error, never a success screen; retry works")
        def booking_errors():
            pg = new_page(430, 900)
            pg.goto(base + "/booking"); settle(pg)
            fill_valid(pg)
            pg.route("**/api/book-appointment", lambda r: r.fulfill(status=500, content_type="application/json", body='{"ok":false,"error":"Something went wrong on our side."}'))
            pg.click("[data-submit]")
            expect(pg.locator("[data-submit-alert] .notice--error")).to_contain_text("was not sent")
            expect(pg.locator(".confirm")).to_have_count(0)
            pg.unroute("**/api/book-appointment")
            pg.route("**/api/book-appointment", lambda r: r.abort())
            pg.click("[data-submit]")
            expect(pg.locator("[data-submit-alert]")).to_contain_text("couldn't reach the server")
            pg.unroute("**/api/book-appointment")
            pg.click("[data-submit]")
            expect(pg.locator(".confirm h2")).to_have_text("Request sent", timeout=10000)
            pg.screenshot(path=str(ART / "booking_confirmation_430.png"), full_page=True)
            pg.context.close()
        booking_errors()

        @check("Booking: server-side validation error returns user to the right step")
        def booking_422():
            pg = new_page(1280)
            pg.goto(base + "/booking"); settle(pg)
            fill_valid(pg)
            pg.route("**/api/book-appointment", lambda r: r.fulfill(status=422, content_type="application/json",
                      body='{"ok":false,"error":"Please check the highlighted fields.","fields":{"time":"That time has already passed today."}}'))
            pg.click("[data-submit]")
            expect(pg.locator(".step h2")).to_have_text("Preferred date & time")
            expect(pg.locator("[data-group-error]")).to_contain_text("already passed")
            pg.context.close()
        booking_422()

        @check("Contact form: validation, successful submission")
        def contact():
            pg = new_page(375, 812)
            pg.goto(base + "/contact?subject=Price%20enquiry"); settle(pg)
            expect(pg.locator("#c-subject")).to_have_value("Price enquiry")
            pg.click("[data-contact-form] button[type=submit]")
            expect(pg.locator(".field:has(#c-name) .field__error")).to_be_visible()
            pg.fill("#c-name", "Mock Sender"); pg.fill("#c-email", "mock.sender@example.test"); pg.fill("#c-message", "Mock message for testing.")
            pg.wait_for_timeout(2600)
            pg.click("[data-contact-form] button[type=submit]")
            expect(pg.locator("[data-contact-card] .confirm h2")).to_have_text("Message received")
            pg.context.close()
        contact()

        @check("Keyboard: skip link, visible focus, calendar arrow keys")
        def keyboard():
            pg = new_page(1280)
            pg.goto(base + "/booking"); settle(pg)
            pg.keyboard.press("Tab")
            assert pg.evaluate("document.activeElement.className") == "skip-link"
            pg.keyboard.press("Enter")
            pg.click("input[value='first-available'] >> xpath=..")
            pg.click("[data-next]")
            pg.focus(f"[data-date='{tomorrow}']")
            pg.keyboard.press("ArrowRight")
            nxt = (datetime.fromisoformat(tomorrow) + timedelta(days=1)).date().isoformat()
            assert pg.evaluate("document.activeElement.dataset.date") == nxt
            pg.keyboard.press("Enter")
            expect(pg.locator(f"[data-date='{nxt}']")).to_have_attribute("aria-pressed", "true")
            outline = pg.evaluate("getComputedStyle(document.activeElement).outlineStyle")
            assert outline != "none", "focus indicator must be visible"
            pg.context.close()
        keyboard()

        @check("Admin dashboard: login required, shows requests and email status; public site exposes no staff emails")
        def admin():
            pg = new_page(1280)
            pg.goto(base + "/admin/"); settle(pg)
            expect(pg.locator("h1")).to_have_text("Staff sign in")
            pg.fill("#token", "wrong-token-123456789")
            pg.click("[data-login] button"); expect(pg.locator(".notice--error")).to_contain_text("Invalid")
            pg.fill("#token", TOKEN); pg.click("[data-login] button")
            expect(pg.locator("h1")).to_have_text("Appointment requests")
            pg.locator("tbody tr").first.click()
            expect(pg.locator(".kv")).to_contain_text("Mock Patient")
            expect(pg.locator(".data")).to_contain_text("clinic_notify")
            pg.click("[data-tab=email]")
            expect(pg.locator(".kv")).to_contain_text("staff.a@example.test")
            pg.click("[data-test] button"); expect(pg.locator("[data-test-result]")).to_contain_text("outbox")
            pg.screenshot(path=str(ART / "admin_email_1280.png"), full_page=True)
            pub = new_page(1280)
            for path in PAGES:
                pub.goto(base + path); settle(pub)
                assert "staff.a@example.test" not in pub.content(), path
            pub.context.close(); pg.context.close()
        admin()

        browser.close()
    httpd.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} browser checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
