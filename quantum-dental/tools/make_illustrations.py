"""Generate interim interior illustrations (SVG -> JPEG via headless Chromium).

These are stylised artwork, not photographs of the clinic. Replace each file in
static/img/clinic/ with a real photo of the same name and set `illustration: false`
for that slot in static/js/content.js.

    python3 tools/make_illustrations.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "static" / "img" / "clinic"
W, H = 1200, 1500

DEFS = """
<defs>
  <filter id="stone" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.012 0.06" numOctaves="4" seed="7" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.55  0 0 0 0 0.46  0 0 0 0 0.36  0 0 0 0.22 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="pores" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0.45  0 0 0 0 0.38  0 0 0 0 0.3  0 0 0 0.10 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="lime" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.004 0.006" numOctaves="5" seed="11"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0.62  0 0 0 0 0.55  0 0 0 0 0.47  0 0 0 0.35 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.004 0.18" numOctaves="3" seed="5"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0.16  0 0 0 0 0.09  0 0 0 0 0.05  0 0 0 0.55 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="brush" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9 0.004" numOctaves="2" seed="2"/>
    <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.35 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
  <filter id="blur40"><feGaussianBlur stdDeviation="40"/></filter>
  <filter id="blur14"><feGaussianBlur stdDeviation="14"/></filter>
  <filter id="blur4"><feGaussianBlur stdDeviation="4"/></filter>
  <filter id="film" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves="1" seed="9"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0.5  0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0.06 0"/>
    <feComposite in2="SourceGraphic" operator="in"/>
  </filter>
  <linearGradient id="wall" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#F3ECE2"/><stop offset=".55" stop-color="#E9DFD2"/><stop offset="1" stop-color="#D9CBBA"/>
  </linearGradient>
  <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#D8C8B2"/><stop offset="1" stop-color="#EADFCF"/>
  </linearGradient>
  <linearGradient id="steel" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#8E8F8E"/><stop offset=".18" stop-color="#C9CACA"/><stop offset=".38" stop-color="#ECEDEC"/>
    <stop offset=".55" stop-color="#B4B5B5"/><stop offset=".78" stop-color="#DCDDDC"/><stop offset="1" stop-color="#7D7E7D"/>
  </linearGradient>
  <linearGradient id="steelTop" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#F4F2EE"/><stop offset="1" stop-color="#CFCCC6"/>
  </linearGradient>
  <linearGradient id="flute" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#3B2416"/><stop offset=".3" stop-color="#7A4E31"/><stop offset=".55" stop-color="#9A6843"/>
    <stop offset=".8" stop-color="#6A4129"/><stop offset="1" stop-color="#2E1B10"/>
  </linearGradient>
  <radialGradient id="glow" cx=".5" cy=".5" r=".5">
    <stop offset="0" stop-color="#FFF6E8" stop-opacity=".95"/><stop offset="1" stop-color="#FFF6E8" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="vignette" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#2B2A27" stop-opacity=".10"/><stop offset=".35" stop-color="#2B2A27" stop-opacity="0"/>
    <stop offset=".8" stop-color="#2B2A27" stop-opacity="0"/><stop offset="1" stop-color="#2B2A27" stop-opacity=".14"/>
  </linearGradient>
</defs>
"""

FINISH = f'<rect width="{W}" height="{H}" fill="url(#vignette)"/><rect width="{W}" height="{H}" fill="#fff" filter="url(#film)"/>'


def tiles(y0, y1, vx, vy, n_lines=14, rows=9):
    """Perspective floor grid: lines from bottom edge converging to (vx, vy), horizontals spaced geometrically."""
    out = []
    for i in range(-n_lines, n_lines + 1):
        x = W / 2 + i * 150
        t = (y0 - vy) / (H - vy)
        out.append(f'<line x1="{vx + (x - vx) * t:.1f}" y1="{y0}" x2="{x:.1f}" y2="{H}"/>')
    y = y0
    step = 12
    for _ in range(rows):
        y += step
        step *= 1.45
        if y > H:
            break
        out.append(f'<line x1="0" y1="{y:.1f}" x2="{W}" y2="{y:.1f}"/>')
    return f'<g stroke="#B9A78F" stroke-opacity=".55" stroke-width="1.6">{"".join(out)}</g>'


def reception():
    floor_y = 1060
    return f"""
    <rect width="{W}" height="{H}" fill="url(#wall)"/><rect width="{W}" height="{H}" fill="#fff" filter="url(#lime)"/>
    <!-- arched niche -->
    <path d="M300 {floor_y} V470 A300 300 0 0 1 900 470 V{floor_y} Z" fill="#E3D6C5"/>
    <path d="M300 {floor_y} V470 A300 300 0 0 1 900 470 V{floor_y} Z" fill="#fff" filter="url(#lime)" opacity=".8"/>
    <path d="M330 {floor_y} V475 A270 270 0 0 1 870 475 V{floor_y}" fill="none" stroke="#FFF7EA" stroke-width="6" opacity=".7" filter="url(#blur4)"/>
    <ellipse cx="600" cy="330" rx="260" ry="160" fill="url(#glow)" filter="url(#blur40)" opacity=".9"/>
    <!-- fluted walnut panel in niche -->
    <g>{''.join(f'<rect x="{360 + i*24}" y="560" width="24" height="{floor_y-560}" fill="url(#flute)"/>' for i in range(20))}
      <rect x="360" y="560" width="480" height="{floor_y-560}" fill="#000" filter="url(#grain)" opacity=".6"/>
      <rect x="360" y="560" width="480" height="140" fill="#FFF3E0" opacity=".14" filter="url(#blur14)"/></g>
    <path d="M360 560 A240 240 0 0 1 840 560" fill="none" stroke="#CDBEA9" stroke-width="2"/>
    <!-- floor -->
    <rect y="{floor_y}" width="{W}" height="{H-floor_y}" fill="url(#floor)"/>
    <rect y="{floor_y}" width="{W}" height="{H-floor_y}" fill="#fff" filter="url(#stone)"/>
    {tiles(floor_y, H, 600, 600)}
    <rect y="{floor_y-4}" width="{W}" height="10" fill="#C9B9A3"/>
    <!-- curved steel counter -->
    <ellipse cx="600" cy="1300" rx="560" ry="40" fill="#5B4F42" opacity=".28" filter="url(#blur14)"/>
    <path d="M80 1000 Q600 900 1120 1000 L1120 1290 Q600 1200 80 1290 Z" fill="url(#steel)"/>
    <path d="M80 1000 Q600 900 1120 1000 L1120 1290 Q600 1200 80 1290 Z" fill="#fff" filter="url(#brush)"/>
    <path d="M70 990 Q600 882 1130 990 L1130 1010 Q600 905 70 1010 Z" fill="url(#steelTop)"/>
    <path d="M90 1006 Q600 912 1110 1006" fill="none" stroke="#fff" stroke-width="3" opacity=".8"/>
    <path d="M80 1288 Q600 1198 1120 1288" fill="none" stroke="#6E6C68" stroke-width="3" opacity=".6"/>
    <!-- travertine counter top slab -->
    <path d="M260 944 Q600 890 940 944 L940 962 Q600 910 260 962 Z" fill="#E6D8C3"/>
    <!-- pendant lights -->
    {''.join(f'<line x1="{x}" y1="0" x2="{x}" y2="300" stroke="#7B746A" stroke-width="2"/><ellipse cx="{x}" cy="310" rx="34" ry="12" fill="#B9B3A9"/><ellipse cx="{x}" cy="330" rx="90" ry="60" fill="url(#glow)" filter="url(#blur14)"/>' for x in (420, 600, 780))}
    {FINISH}"""


def hallway():
    vx, vy = 600, 640
    return f"""
    <rect width="{W}" height="{H}" fill="#EDE3D6"/>
    <!-- ceiling -->
    <polygon points="0,0 {W},0 760,520 440,520" fill="#F5EFE6"/>
    <polygon points="560,0 640,0 612,520 588,520" fill="#FFF8EC"/>
    <polygon points="560,0 640,0 612,520 588,520" fill="url(#glow)" filter="url(#blur14)"/>
    <!-- side walls -->
    <polygon points="0,0 440,520 440,800 0,{H}" fill="#E4D7C6"/><polygon points="0,0 440,520 440,800 0,{H}" fill="#fff" filter="url(#lime)"/>
    <polygon points="{W},0 760,520 760,800 {W},{H}" fill="#DCCDBA"/><polygon points="{W},0 760,520 760,800 {W},{H}" fill="#fff" filter="url(#lime)"/>
    <!-- end wall with arch light -->
    <rect x="440" y="520" width="320" height="280" fill="#E9DDCC"/>
    <path d="M520 800 V650 A80 80 0 0 1 680 650 V800 Z" fill="#FFF5E4"/>
    <ellipse cx="600" cy="700" rx="140" ry="120" fill="url(#glow)" filter="url(#blur40)"/>
    <!-- floor -->
    <polygon points="0,{H} 440,800 760,800 {W},{H}" fill="url(#floor)"/>
    <polygon points="0,{H} 440,800 760,800 {W},{H}" fill="#fff" filter="url(#stone)"/>
    <g stroke="#B9A78F" stroke-opacity=".5" stroke-width="1.6">
      {''.join(f'<line x1="{440 + i*40}" y1="800" x2="{-600 + i*300}" y2="{H}"/>' for i in range(9))}
      {''.join(f'<line x1="{440 - (y-800)*0.629:.0f}" y1="{y}" x2="{760 + (y-800)*0.629:.0f}" y2="{y}"/>' for y in (818, 846, 890, 958, 1060, 1210, 1430))}
    </g>
    <!-- floor reflection of light -->
    <ellipse cx="600" cy="980" rx="120" ry="260" fill="#FFF6E6" opacity=".35" filter="url(#blur40)"/>
    <!-- skirting cove light -->
    <line x1="0" y1="{H-2}" x2="440" y2="800" stroke="#FFF3DD" stroke-width="5" opacity=".7" filter="url(#blur4)"/>
    <line x1="{W}" y1="{H-2}" x2="760" y2="800" stroke="#FFF3DD" stroke-width="5" opacity=".7" filter="url(#blur4)"/>
    {FINISH}"""


def walnut():
    n = 22
    fw = W / n
    flutes = "".join(f'<rect x="{i*fw:.1f}" y="0" width="{fw+0.5:.1f}" height="{H}" fill="url(#flute)"/>' for i in range(n))
    return f"""
    <rect width="{W}" height="{H}" fill="#4A2E1C"/>{flutes}
    <rect width="{W}" height="{H}" fill="#000" filter="url(#grain)" opacity=".75"/>
    <!-- soft raking light from top-left -->
    <ellipse cx="300" cy="200" rx="700" ry="600" fill="#FFE7C8" opacity=".28" filter="url(#blur40)"/>
    <rect width="{W}" height="{H}" fill="url(#vignette)"/>
    <!-- travertine plinth and steel reveal -->
    <rect y="1290" width="{W}" height="14" fill="url(#steel)"/>
    <rect y="1304" width="{W}" height="{H-1304}" fill="#E4D6C1"/><rect y="1304" width="{W}" height="{H-1304}" fill="#fff" filter="url(#stone)"/>
    <rect y="1304" width="{W}" height="40" fill="#5A4430" opacity=".25" filter="url(#blur14)"/>
    {FINISH}"""


def doors():
    labels = ["Training Room", "Orthopan", "Surgery"]
    xs = [110, 470, 830]
    door = ""
    for x, lab in zip(xs, labels):
        door += f"""
        <rect x="{x-14}" y="406" width="288" height="854" fill="#CDBFAC"/>
        <rect x="{x}" y="420" width="260" height="840" fill="url(#flute)" opacity=".0"/>
        <rect x="{x}" y="420" width="260" height="840" fill="#6B4429"/>
        {''.join(f'<rect x="{x + j*20}" y="420" width="20" height="840" fill="url(#flute)" opacity=".75"/>' for j in range(13))}
        <rect x="{x}" y="420" width="260" height="840" fill="#000" filter="url(#grain)" opacity=".55"/>
        <rect x="{x+222}" y="800" width="10" height="150" rx="5" fill="url(#steel)"/>
        <rect x="{x+30}" y="340" width="200" height="44" rx="6" fill="#F7F3EC" stroke="#C9C4BB"/>
        <text x="{x+130}" y="369" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="20" letter-spacing="1.5" fill="#3B3A36">{lab.upper()}</text>"""
    return f"""
    <rect width="{W}" height="{H}" fill="url(#wall)"/><rect width="{W}" height="{H}" fill="#fff" filter="url(#lime)"/>
    {''.join(f'<ellipse cx="{x+130}" cy="250" rx="170" ry="150" fill="url(#glow)" filter="url(#blur40)" opacity=".85"/>' for x in xs)}
    {''.join(f'<circle cx="{x+130}" cy="120" r="16" fill="#F2EEE7" stroke="#CFC8BD"/>' for x in xs)}
    {door}
    <rect y="1260" width="{W}" height="{H-1260}" fill="url(#floor)"/><rect y="1260" width="{W}" height="{H-1260}" fill="#fff" filter="url(#stone)"/>
    <g stroke="#B9A78F" stroke-opacity=".5" stroke-width="1.6"><line x1="0" y1="1330" x2="{W}" y2="1330"/><line x1="0" y1="1440" x2="{W}" y2="1440"/>
      {''.join(f'<line x1="{x}" y1="1260" x2="{x*1.12-70:.0f}" y2="{H}"/>' for x in range(0, W+1, 200))}</g>
    <rect y="1250" width="{W}" height="12" fill="#BFAE97"/>
    {''.join(f'<rect x="{x}" y="1262" width="260" height="120" fill="#6B4429" opacity=".14" filter="url(#blur14)"/>' for x in xs)}
    {FINISH}"""


def curves():
    return f"""
    <rect width="{W}" height="{H}" fill="#E9DFD2"/>
    <path d="M-100 {H} C 200 900, 500 380, {W+100} 160 L {W+100} {H} Z" fill="#E1D3C1"/>
    <path d="M-100 {H} C 200 900, 500 380, {W+100} 160 L {W+100} {H} Z" fill="#fff" filter="url(#lime)"/>
    <path d="M-100 {H} C 260 1000, 600 560, {W+100} 420 L {W+100} {H} Z" fill="#D5C4AE"/>
    <path d="M-100 {H} C 260 1000, 600 560, {W+100} 420 L {W+100} {H} Z" fill="#fff" filter="url(#lime)" opacity=".8"/>
    <path d="M-100 {H} C 200 900, 500 380, {W+100} 160" fill="none" stroke="#FFF6E6" stroke-width="10" opacity=".85" filter="url(#blur4)"/>
    <path d="M-100 {H} C 200 900, 500 380, {W+100} 160" fill="none" stroke="#FFF2DC" stroke-width="80" opacity=".35" filter="url(#blur40)"/>
    <path d="M-100 {H} C 320 1120, 700 760, {W+100} 700 L {W+100} {H} Z" fill="#C8B49A" opacity=".9"/>
    <path d="M-100 {H} C 320 1120, 700 760, {W+100} 700 L {W+100} {H} Z" fill="#fff" filter="url(#stone)"/>
    <path d="M-100 {H} C 320 1120, 700 760, {W+100} 700" fill="none" stroke="url(#steel)" stroke-width="12"/>
    <ellipse cx="880" cy="300" rx="380" ry="260" fill="url(#glow)" filter="url(#blur40)" opacity=".8"/>
    {FINISH}"""


def limewash():
    return f"""
    <rect width="{W}" height="{H}" fill="#E8DDCF"/><rect width="{W}" height="{H}" fill="#fff" filter="url(#lime)"/>
    <rect width="{W}" height="{H}" fill="#fff" filter="url(#lime)" opacity=".6"/>
    <!-- light beam -->
    <polygon points="380,0 820,0 1200,1000 1200,1240 620,1240" fill="#FFF5E2" opacity=".55" filter="url(#blur40)"/>
    <polygon points="560,0 700,0 1080,1240 900,1240" fill="#FFF8EC" opacity=".35" filter="url(#blur14)"/>
    <!-- travertine bench -->
    <rect x="120" y="1080" width="960" height="90" fill="#E3D2BB"/><rect x="120" y="1080" width="960" height="90" fill="#fff" filter="url(#stone)"/>
    <rect x="120" y="1080" width="960" height="8" fill="#F1E6D6"/>
    <rect x="180" y="1170" width="840" height="70" fill="#CDB99F"/>
    <rect x="120" y="1240" width="960" height="40" fill="#4C3F33" opacity=".22" filter="url(#blur14)"/>
    <!-- ceramic vessel and branch -->
    <path d="M820 1080 C 790 1010, 800 960, 850 940 C 900 960, 910 1010, 880 1080 Z" fill="#CFC3B2"/>
    <path d="M850 940 C 840 800, 880 700, 960 600 M852 860 C 800 800, 760 760, 700 740 M870 760 C 920 720, 960 720, 1000 700"
          fill="none" stroke="#5E5240" stroke-width="5" stroke-linecap="round"/>
    {''.join(f'<ellipse cx="{x}" cy="{y}" rx="16" ry="7" fill="#777B67" transform="rotate({r} {x} {y})"/>' for x, y, r in ((960,600,-35),(930,640,25),(700,740,15),(740,752,-20),(1000,700,-10),(960,716,30),(880,700,-50)))}
    <rect y="1280" width="{W}" height="{H-1280}" fill="url(#floor)"/><rect y="1280" width="{W}" height="{H-1280}" fill="#fff" filter="url(#stone)"/>
    {FINISH}"""


SCENES = {"reception": reception, "hallway": hallway, "walnut": walnut, "doors": doors, "curves": curves, "limewash": limewash}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = shutil.which("google-chrome")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for name, fn in SCENES.items():
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{DEFS}{fn()}</svg>'
            pg.set_content(f"<html><body style='margin:0'>{svg}</body></html>")
            pg.wait_for_timeout(150)
            path = OUT / f"{name}.jpg"
            pg.screenshot(path=str(path), type="jpeg", quality=82, clip={"x": 0, "y": 0, "width": W, "height": H})
            print(f"{path.name}: {path.stat().st_size // 1024} KB")
        b.close()


if __name__ == "__main__":
    main()
