#!/usr/bin/env python3
"""Generate the animated SVG assets for Anurag's GitHub profile README.

Everything is plain SVG (CSS + SMIL animation), written with the standard
library only. Nothing here needs a third-party image service at runtime.

Inputs
  - Live Dehradun weather from Open-Meteo (no API key). If it is unreachable
    the scene falls back to a month-based season.
  - The real GitHub contribution calendar (GraphQL first, public HTML fallback).

Outputs (assets/)
  hero.svg, terminal.svg, contribution-runner.svg,
  diagram-deployforge.svg, diagram-scaleflow.svg,
  band-*.svg (section dividers), rail-*-l.svg / rail-*-r.svg (side rails),
  scene.json (last rendered scene; used to avoid noisy commits)

Environment (all optional)
  GITHUB_USERNAME, GITHUB_TOKEN / PROFILE_TOKEN
  WEATHER_JSON   '{"temp":18,"code":0,"is_day":true}'  -> skip the network call
  FORCE_SEASON   spring|summer|monsoon|autumn|winter
  CONTRIB_HTML   path to a saved contributions page (offline preview)
  DEMO_MODE=1    clearly labelled sample contribution data
  OUT_DIR        write somewhere other than ./assets (previews)
"""
from __future__ import annotations

import itertools
import json
import math
import os
import random
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(os.environ["OUT_DIR"]) if os.getenv("OUT_DIR") else ROOT / "assets"
USERNAME = os.getenv("GITHUB_USERNAME", "anuragdevcode")
IST = ZoneInfo("Asia/Kolkata")
LAT, LON = 30.3165, 78.0322  # Dehradun

MONO = "'JetBrains Mono','DejaVu Sans Mono','Menlo','Consolas',monospace"
SANS = "'Inter','DejaVu Sans','Segoe UI',Arial,sans-serif"
CW = 0.6  # monospace glyph advance, in em

INK, VIOLET, LAVENDER, PEACH = "#0B0D14", "#BB9AF7", "#E0CFFF", "#F0B3A6"
TEXT, SOFT, MUTED = "#E8E4F5", "#B9B4C9", "#827A96"
LINE = "#3A3356"

# ----------------------------------------------------------------------------
# Seasons and scene
# ----------------------------------------------------------------------------
PALETTE = {
    "leaf": ["#E8590C", "#F76707", "#F59F00", "#C92A2A", "#FD7E14", "#D9480F"],
    "petal": ["#F783AC", "#FFA8CD", "#FFD6E7", "#FFC53D"],
    "snow": ["#A5D8FF", "#CFE8FF", "#8EC5FF"],
    "rain": ["#74B9FF", "#A5D8FF", "#5C9DE0"],
    "firefly": ["#FFD43B", "#FFE066", "#FFC857"],
}
SEASONS = {
    "spring": dict(kind="petal", accent="#F783AC", note="new things bloom. old bugs survive."),
    "summer": dict(kind="firefly", accent="#FFC857", note="high temperatures. higher abstractions."),
    "monsoon": dict(kind="rain", accent="#74B9FF", note="the sky is crying. so is CI."),
    "autumn": dict(kind="leaf", accent="#FF8A3D", note="leaves fall. so do builds."),
    "winter": dict(kind="snow", accent="#9CC9FF", note="cold hands. warm terminal."),
}


def season_for(month: int) -> str:
    """Dehradun-flavoured calendar. Weather, when available, overrides the particles."""
    if month in (3, 4):
        return "spring"
    if month in (5, 6):
        return "summer"
    if month in (7, 8, 9):
        return "monsoon"
    if month in (10, 11):
        return "autumn"
    return "winter"


def fetch_weather() -> dict | None:
    raw = os.getenv("WEATHER_JSON")
    if raw:
        return json.loads(raw)
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,weather_code,is_day&timezone=Asia%2FKolkata"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "anurag-profile-animations"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            cur = json.loads(resp.read().decode("utf-8"))["current"]
        return {"temp": float(cur["temperature_2m"]), "code": int(cur["weather_code"]), "is_day": bool(cur["is_day"])}
    except Exception as exc:  # noqa: BLE001 - any failure means "use season mode"
        print(f"WARNING: live weather unavailable ({exc}); using season mode.", file=sys.stderr)
        return None


def build_scene(now: datetime, weather: dict | None, previous: dict | None) -> dict:
    season = os.getenv("FORCE_SEASON") or season_for(now.month)
    kind, cond = SEASONS[season]["kind"], "season mode"
    temp = None
    is_day = 6 <= now.hour < 18
    if weather:
        code, is_day, temp = weather["code"], bool(weather["is_day"]), round(weather["temp"])
        if code in (95, 96, 99):
            kind, cond = "storm", "thunderstorm"
        elif code in (71, 73, 75, 77, 85, 86):
            kind, cond = "snow", "snow"
        elif code in (51, 53, 55, 56, 57):
            kind, cond = "rain", "drizzle"
        elif code in (61, 63, 65, 66, 67, 80, 81, 82):
            kind, cond = "rain", "rain"
        elif code in (45, 48):
            kind, cond = "fog", "fog"
        elif code in (0, 1):
            cond = "clear" if is_day else "clear night"
        elif code in (2, 3):
            cond = "cloudy"
        else:
            cond = "weather"
    scene = dict(season=season, kind=kind, cond=cond, temp=temp, is_day=is_day, live=bool(weather))
    # Keep the picture stable (and the git history quiet) unless something visible changed.
    if (
        previous
        and previous.get("live")
        and scene["live"]
        and all(previous.get(k) == scene[k] for k in ("season", "kind", "cond", "is_day"))
        and abs((previous.get("temp") or 0) - (scene["temp"] or 0)) < 3
    ):
        scene["temp"] = previous["temp"]
    return scene


# ----------------------------------------------------------------------------
# SVG helpers
# ----------------------------------------------------------------------------
_uid = itertools.count(1)


def uid(prefix: str) -> str:
    return f"{prefix}{next(_uid)}"


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def svg_doc(w: int, h: int, body: str, defs: str = "", style: str = "", title: str | None = None) -> str:
    t = f"<title>{escape(title)}</title>" if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none">{t}<defs>{defs}</defs>{style}{body}</svg>\n'
    )


def base_css(h: int) -> str:
    return (
        "<style>"
        ".p{animation:fall linear infinite}.s{animation:sway ease-in-out infinite alternate}"
        ".t{animation:swing ease-in-out infinite alternate}.f{animation:flip ease-in-out infinite alternate}"
        ".g{animation:drift ease-in-out infinite alternate}.b{animation:pulse ease-in-out infinite alternate}"
        f"@keyframes fall{{from{{transform:translateY(-28px)}}to{{transform:translateY({h + 28}px)}}}}"
        "@keyframes sway{from{transform:translateX(calc(var(--a)*-1))}to{transform:translateX(var(--a))}}"
        "@keyframes swing{from{transform:rotate(var(--r0))}to{transform:rotate(var(--r1))}}"
        "@keyframes flip{from{transform:scale(1,1)}to{transform:scale(.28,1)}}"
        "@keyframes drift{from{transform:translate(0,0)}to{transform:translate(var(--dx),var(--dy))}}"
        "@keyframes pulse{from{opacity:.12}to{opacity:1}}"
        "@media (prefers-reduced-motion:reduce){.p,.g{display:none}}"
        "</style>"
    )


COMMON_DEFS = (
    '<radialGradient id="ff"><stop offset="0" stop-color="#FFE066" stop-opacity=".95"/>'
    '<stop offset="1" stop-color="#FFC857" stop-opacity="0"/></radialGradient>'
    '<radialGradient id="mist"><stop offset="0" stop-color="#B8C4D4" stop-opacity=".38"/>'
    '<stop offset="1" stop-color="#B8C4D4" stop-opacity="0"/></radialGradient>'
)


def normalize(points, cycle, discrete):
    pts = sorted(points, key=lambda p: p[0])
    if pts[0][0] > 0:
        pts.insert(0, (0, pts[0][1]))
    out, last = [], -1.0
    for t, v in pts:
        t = min(t, cycle)
        if t <= last:
            t = last + 0.002
        out.append((t, v))
        last = t
    if not discrete and out[-1][0] < cycle:
        out.append((cycle, out[-1][1]))
    return out


def animate(attr, points, cycle, *, discrete=False, transform=None, dur=None):
    """SMIL animate/animateTransform from (time_seconds, value_string) points."""
    pts = normalize(points, cycle, discrete)
    values = ";".join(v for _, v in pts)
    times = ";".join(f"{min(1.0, t / cycle):.4f}" for t, _ in pts)
    mode = ' calcMode="discrete"' if discrete else ""
    d = f"{(dur or cycle):.2f}s"
    if transform:
        return (
            f'<animateTransform attributeName="transform" type="{transform}" values="{values}" '
            f'keyTimes="{times}" dur="{d}"{mode} repeatCount="indefinite"/>'
        )
    return f'<animate attributeName="{attr}" values="{values}" keyTimes="{times}" dur="{d}"{mode} repeatCount="indefinite"/>'


def windows(spans, cycle, base="0", on="1"):
    """Discrete opacity: `on` inside each (start, end) span, `base` elsewhere."""
    pts = [(0, base)]
    for a, b in spans:
        pts += [(a, on), (b, base)]
    return animate("opacity", pts, cycle, discrete=True)


def typed(x, y, text, t0, per, t_end, cycle, fill, size, weight="400", cursor=True, cursor_fill=VIOLET):
    """Typewriter text revealed by a clip that grows one glyph at a time."""
    n, cw = len(text), size * CW
    cid = uid("c")
    pts = [(0, "0")] + [(t0 + k * per, fmt(k * cw)) for k in range(1, n + 1)]
    if t_end is not None and t_end < cycle:
        pts.append((t_end, "0"))
    out = (
        f'<clipPath id="{cid}"><rect x="{fmt(x)}" y="{fmt(y - size)}" width="0" height="{fmt(size * 1.6)}">'
        f'{animate("width", pts, cycle, discrete=True)}</rect></clipPath>'
        f'<text x="{fmt(x)}" y="{fmt(y)}" font-family="{MONO}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'textLength="{fmt(n * cw)}" lengthAdjust="spacingAndGlyphs" clip-path="url(#{cid})" xml:space="preserve">{escape(text)}</text>'
    )
    if cursor:
        cur = [(0, fmt(x))] + [(t0 + k * per, fmt(x + k * cw)) for k in range(1, n + 1)]
        stop = min(t_end if t_end is not None else cycle, t0 + n * per + 0.7)
        out += (
            f'<rect x="{fmt(x)}" y="{fmt(y - size + 1)}" width="{fmt(cw * 0.8)}" height="{fmt(size + 2)}" rx="1.5" fill="{cursor_fill}" opacity="0">'
            f'{animate("x", cur, cycle, discrete=True)}{windows([(t0, stop)], cycle)}</rect>'
        )
    return out


# ----------------------------------------------------------------------------
# Particles
# ----------------------------------------------------------------------------
MAPLE = [(0, -10), (2, -5), (6, -7), (5, -2), (10, -1), (6, 3), (8, 7), (2, 6), (1, 10), (-1, 10), (-2, 6),
         (-8, 7), (-6, 3), (-10, -1), (-5, -2), (-6, -7), (-2, -5)]


def shape(kind, rng, col, s):
    if kind == "leaf":
        if rng.random() < 0.55:
            pts = " ".join(f"{fmt(x * s)},{fmt(y * s)}" for x, y in MAPLE)
            return (f'<polygon points="{pts}" fill="{col}"/>'
                    f'<line x1="0" y1="{fmt(5 * s)}" x2="0" y2="{fmt(12 * s)}" stroke="{col}" stroke-width="{fmt(max(.8, .7 * s))}" stroke-linecap="round"/>')
        d = f"M0,{fmt(-9 * s)} C{fmt(6 * s)},{fmt(-7 * s)} {fmt(8 * s)},{fmt(s)} 0,{fmt(10 * s)} C{fmt(-8 * s)},{fmt(s)} {fmt(-6 * s)},{fmt(-7 * s)} 0,{fmt(-9 * s)}Z"
        return (f'<path d="{d}" fill="{col}"/>'
                f'<path d="M0,{fmt(-7 * s)} L0,{fmt(9 * s)}" stroke="#000" stroke-opacity=".22" stroke-width=".8"/>')
    if kind == "petal":
        d = f"M0,{fmt(-7 * s)} C{fmt(6 * s)},{fmt(-6 * s)} {fmt(6 * s)},{fmt(3 * s)} 0,{fmt(8 * s)} C{fmt(-6 * s)},{fmt(3 * s)} {fmt(-6 * s)},{fmt(-6 * s)} 0,{fmt(-7 * s)}Z"
        return f'<path d="{d}" fill="{col}"/>'
    if kind == "snow":
        r = 1.2 + 1.8 * s
        if rng.random() < 0.3:
            arms = "".join(
                f'<line x1="{fmt(-4 * s * math.cos(a))}" y1="{fmt(-4 * s * math.sin(a))}" x2="{fmt(4 * s * math.cos(a))}" y2="{fmt(4 * s * math.sin(a))}"/>'
                for a in (0, math.pi / 3, 2 * math.pi / 3)
            )
            return f'<g stroke="{col}" stroke-width="1.1" stroke-linecap="round">{arms}</g>'
        return f'<circle r="{fmt(r)}" fill="{col}" stroke="#5C9DE0" stroke-opacity=".5" stroke-width=".6"/>'
    return ""


def particles(kind, w, h, n, seed, *, speed=(40, 70), amp=(6, 14), size=(0.7, 1.2), xpad=0.0):
    rng = random.Random(seed)
    colors = PALETTE[kind]
    out = []
    dist = h + 56
    if kind in ("leaf", "petal", "snow"):
        for _ in range(n):
            x = rng.uniform(xpad, w - xpad)
            col, s = rng.choice(colors), rng.uniform(*size)
            dur = dist / rng.uniform(*speed)
            delay = rng.uniform(0, dur)
            a, sd = rng.uniform(*amp), rng.uniform(2.4, 4.6)
            op = rng.uniform(0.62, 0.96)
            core = shape(kind, rng, col, s)
            if kind != "snow":
                r0 = rng.randint(-70, -20)
                core = (f'<g class="t" style="--r0:{r0}deg;--r1:{r0 + rng.randint(70, 130)}deg;animation-duration:{fmt(rng.uniform(2.2, 4.4))}s">'
                        f'<g class="f" style="animation-duration:{fmt(rng.uniform(1.3, 2.6))}s;animation-delay:-{fmt(rng.uniform(0, 2))}s">{core}</g></g>')
            out.append(
                f'<g class="p" style="animation-duration:{fmt(dur)}s;animation-delay:-{fmt(delay)}s">'
                f'<g transform="translate({fmt(x)},0)" opacity="{fmt(op)}">'
                f'<g class="s" style="--a:{fmt(a)}px;animation-duration:{fmt(sd)}s;animation-delay:-{fmt(rng.uniform(0, sd))}s">{core}</g></g></g>'
            )
    elif kind == "rain":
        for _ in range(n):
            x, ln = rng.uniform(0, w), rng.uniform(9, 17)
            dur = dist / rng.uniform(260, 430)
            out.append(
                f'<g class="p" style="animation-duration:{fmt(dur)}s;animation-delay:-{fmt(rng.uniform(0, dur))}s">'
                f'<g transform="translate({fmt(x)},0)" opacity="{fmt(rng.uniform(.35, .8))}">'
                f'<line x1="0" y1="0" x2="-2" y2="{fmt(ln)}" stroke="{rng.choice(colors)}" stroke-width="1.2" stroke-linecap="round"/></g></g>'
            )
    elif kind == "firefly":
        for _ in range(n):
            x, y = rng.uniform(xpad, w - xpad), rng.uniform(4, h - 4)
            dd = rng.uniform(5, 10)
            out.append(
                f'<g class="g" style="--dx:{fmt(rng.uniform(-18, 18))}px;--dy:{fmt(rng.uniform(-14, 14))}px;animation-duration:{fmt(dd)}s;animation-delay:-{fmt(rng.uniform(0, dd))}s">'
                f'<g transform="translate({fmt(x)},{fmt(y)})"><g class="b" style="animation-duration:{fmt(rng.uniform(1.2, 2.8))}s;animation-delay:-{fmt(rng.uniform(0, 2))}s">'
                f'<circle r="{fmt(rng.uniform(6, 10))}" fill="url(#ff)"/><circle r="1.5" fill="#FFF4C2"/></g></g></g>'
            )
    return "".join(out)


def mist(w, h, n, seed):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        rx = rng.uniform(w * .12, w * .3) if w > 200 else rng.uniform(26, 44)
        ry = rng.uniform(h * .22, h * .45) if h < 200 else rng.uniform(40, 80)
        dd = rng.uniform(14, 26)
        out.append(
            f'<g class="g" style="--dx:{fmt(rng.uniform(-60, 60) if w > 200 else rng.uniform(-8, 8))}px;--dy:0px;animation-duration:{fmt(dd)}s;animation-delay:-{fmt(rng.uniform(0, dd))}s">'
            f'<ellipse cx="{fmt(rng.uniform(0, w))}" cy="{fmt(rng.uniform(0, h))}" rx="{fmt(rx)}" ry="{fmt(ry)}" fill="url(#mist)"/></g>'
        )
    return "".join(out)


def scene_layer(scene, w, h, n, seed, **kw):
    """Particles for the current scene, sized for a w x h canvas."""
    kind = scene["kind"]
    season_kind = SEASONS[scene["season"]]["kind"]
    if kind == "storm":
        return particles("rain", w, h, int(n * 1.6), seed, **kw)
    if kind == "fog":
        extra = particles(season_kind, w, h, max(2, n // 3), seed + 7, **kw) if season_kind != "rain" else ""
        return mist(w, h, max(3, n // 4), seed) + extra
    return particles(kind, w, h, n, seed, **kw)


# ----------------------------------------------------------------------------
# Hero
# ----------------------------------------------------------------------------
HERO_LINES = [
    "Sometimes they even work. That's the whole business model.",
    "Backend + systems + AI. Open to internships & freelance work.",
    "Turning coffee into questionable engineering decisions.",
    "Currently debugging my life in production...",
]


def badge_text(scene):
    s = scene["season"]
    if scene["live"] and scene["temp"] is not None:
        return f"dehradun · {scene['temp']}°C · {scene['cond']} · {s}"
    return f"dehradun · {s} · season mode"


def make_hero(scene):
    W, H = 1100, 250
    S = SEASONS[scene["season"]]
    accent = S["accent"]
    night = not scene["is_day"]
    bt = badge_text(scene)
    bw = len(bt) * 7.3 + 44
    bx = 1056 - bw
    T, cycle = 5.4, 5.4 * len(HERO_LINES)

    defs = (
        f'<linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse">'
        f'<stop stop-color="{"#080A12" if night else "#0B0D14"}"/><stop offset=".56" stop-color="#151225"/><stop offset="1" stop-color="#211832"/></linearGradient>'
        f'<linearGradient id="accent" x1="92" y1="60" x2="780" y2="184" gradientUnits="userSpaceOnUse">'
        f'<stop stop-color="{LAVENDER}"/><stop offset=".52" stop-color="{VIOLET}"/><stop offset="1" stop-color="{PEACH}"/></linearGradient>'
        f'<radialGradient id="glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(890 72) rotate(130) scale(370 470)">'
        f'<stop stop-color="{accent}" stop-opacity=".22"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        '<pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" stroke="#BBA2E8" stroke-opacity=".07"/></pattern>'
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath>'
        f'<linearGradient id="hl" x1="120" x2="{fmt(bx - 14)}" gradientUnits="userSpaceOnUse"><stop stop-color="{VIOLET}" stop-opacity=".05"/><stop offset="1" stop-color="{VIOLET}" stop-opacity=".4"/></linearGradient>'
        + COMMON_DEFS
    )
    rng = random.Random(11)
    stars = ""
    if night:
        for _ in range(30):
            stars += (f'<circle class="b" cx="{fmt(rng.uniform(20, 1080))}" cy="{fmt(rng.uniform(14, 150))}" r="{fmt(rng.uniform(.6, 1.4))}" fill="#E8E4F5" '
                      f'style="animation-duration:{fmt(rng.uniform(1.6, 3.8))}s;animation-delay:-{fmt(rng.uniform(0, 3))}s"/>')
    extras = ""
    if scene["kind"] in ("rain", "storm"):
        for i in range(6):
            extras += (f'<ellipse cx="{fmt(rng.uniform(60, 1040))}" cy="{H - 16}" rx="2" ry=".8" stroke="{accent}" stroke-opacity=".6" fill="none">'
                       f'<animate attributeName="rx" values="2;20" dur="1.6s" begin="{fmt(i * .27)}s" repeatCount="indefinite"/>'
                       f'<animate attributeName="ry" values=".8;4" dur="1.6s" begin="{fmt(i * .27)}s" repeatCount="indefinite"/>'
                       f'<animate attributeName="opacity" values=".8;0" dur="1.6s" begin="{fmt(i * .27)}s" repeatCount="indefinite"/></ellipse>')
    if scene["kind"] == "storm":
        extras += (f'<rect width="{W}" height="{H}" fill="#DCE6FF" opacity="0"><animate attributeName="opacity" '
                   'values="0;0;.5;.08;.38;0;0" keyTimes="0;.55;.56;.58;.6;.66;1" dur="7s" repeatCount="indefinite"/></rect>')

    typed_lines = "".join(
        typed(72, 190, line, i * T, 0.032, (i + 1) * T - 0.25, cycle, "#D5D0E1", 16)
        for i, line in enumerate(HERO_LINES)
    )
    body = (
        f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#glow)"/>'
        f'<rect width="{W}" height="{H}" fill="url(#grid)"/>{stars}{scene_layer(scene, W, H, 34, 101, speed=(34, 58), amp=(8, 22), size=(.9, 1.5))}{extras}</g>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="21.5" stroke="#2A2440"/>'
        f'<rect x="120" y="33.5" width="{fmt(bx - 134)}" height="1" fill="url(#hl)"/>'
        '<circle cx="66" cy="34" r="4" fill="#F7768E"/><circle cx="82" cy="34" r="4" fill="#E0AF68"/><circle cx="98" cy="34" r="4" fill="#9ECE6A"/>'
        f'<rect x="{fmt(bx)}" y="17" width="{fmt(bw)}" height="34" rx="17" fill="#12101F" fill-opacity=".85" stroke="{accent}" stroke-opacity=".55"/>'
        f'<circle cx="{fmt(bx + 18)}" cy="34" r="4" fill="{accent}"><animate attributeName="opacity" values="1;.25;1" dur="2.4s" repeatCount="indefinite"/></circle>'
        f'<text x="{fmt(bx + 32)}" y="38" font-family="{MONO}" font-size="12" fill="{TEXT}" textLength="{fmt(len(bt) * 7.2)}" lengthAdjust="spacingAndGlyphs">{escape(bt)}</text>'
        f'<text x="72" y="91" font-family="{MONO}" font-size="13" fill="{MUTED}" letter-spacing="1.5">anurag kumar singh / developer profile</text>'
        f'<text x="68" y="153" font-family="{SANS}" font-size="58" font-weight="800" letter-spacing="-2" fill="url(#accent)">I build things.</text>'
        f'{typed_lines}'
        f'<rect x="72" y="207" width="190" height="2" rx="1" fill="url(#accent)"/>'
        f'<text x="1028" y="226" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">cse / backend / systems / too many tabs</text>'
    )
    return svg_doc(W, H, body, defs, base_css(H), "Anurag Kumar Singh. I build things. Sometimes they even work.")


# ----------------------------------------------------------------------------
# Bands (section dividers) and rails (side columns)
# ----------------------------------------------------------------------------
def make_band(scene, idx):
    W, H = 1100, 56
    accent = SEASONS[scene["season"]]["accent"]
    defs = (f'<linearGradient id="hl" x1="0" x2="{W}" gradientUnits="userSpaceOnUse"><stop stop-color="{accent}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="{accent}" stop-opacity=".6"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient>' + COMMON_DEFS)
    kind = scene["kind"]
    n = 22 if kind in ("rain", "storm") else 12
    layer = scene_layer(scene, W, H, n, 300 + idx * 13, speed=(9, 16), amp=(10, 26), size=(.55, .9))
    body = layer + f'<rect x="60" y="{H - 5}" width="980" height="1.5" rx=".75" fill="url(#hl)"/>'
    return svg_doc(W, H, body, defs, base_css(H))


def make_rail(scene, h, side, idx):
    W = 40
    accent = SEASONS[scene["season"]]["accent"]
    defs = (f'<linearGradient id="vl" x1="0" y1="0" x2="0" y2="{h}" gradientUnits="userSpaceOnUse"><stop stop-color="{accent}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="{accent}" stop-opacity=".4"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></linearGradient>' + COMMON_DEFS)
    kind = scene["kind"]
    n = max(6, h // (24 if kind in ("rain", "storm") else 38))
    layer = scene_layer(scene, W, h, n, 700 + idx * 31 + (0 if side == "l" else 17), speed=(34, 58), amp=(4, 9), size=(.7, 1.1), xpad=10)
    edge = W - 1.5 if side == "l" else 0.5
    body = layer + f'<rect x="{edge}" y="0" width="1" height="{h}" fill="url(#vl)"/>'
    return svg_doc(W, h, body, defs, base_css(h))


# ----------------------------------------------------------------------------
# Terminal
# ----------------------------------------------------------------------------
def terminal_scenes(scene):
    if scene["live"] and scene["temp"] is not None:
        wx = f"{scene['cond']} · {scene['temp']}°C · {scene['season']} build active"
    else:
        wx = "no live reading in this build. blaming the network."
    return [
        ("whoami", "anurag: software engineer, work in progress"),
        ("ls ~/projects", "DeployForge/  ScaleFlow/  NeuroNav/  LogicLab/  Tangent/"),
        ("git blame life.py", "it was me. it's always me."),
        ("curl wttr.in/dehradun", wx),
        ("sudo make me productive", "permission denied: coffee required."),
    ]


def make_terminal(scene):
    W, H = 1000, 390
    accent = SEASONS[scene["season"]]["accent"]
    size, prompt = 15, "anurag@devbox ~ % "
    cw = size * CW
    sc = terminal_scenes(scene)
    t = 0.6
    parts, spans = [], []
    for i, (cmd, res) in enumerate(sc):
        y = 100 + i * 52
        t_cmd = t
        t_res = t_cmd + len(cmd) * 0.05 + 0.4
        t = t_res + len(res) * 0.022 + 1.0
        spans.append((t_cmd, t_res, i))
        parts.append((i, y, cmd, res, t_cmd, t_res))
    cycle = t + 3.2
    body = ""
    for i, y, cmd, res, t_cmd, t_res in parts:
        body += (f'<text x="28" y="{y}" font-family="{MONO}" font-size="{size}" fill="{VIOLET}" opacity="0" xml:space="preserve">{escape(prompt)}'
                 f'{windows([(t_cmd, cycle)], cycle)}</text>')
        body += typed(28 + len(prompt) * cw, y, cmd, t_cmd, 0.05, None, cycle, TEXT, size)
        body += typed(28, y + 24, res, t_res, 0.022, None, cycle, accent if i == 3 else SOFT, size, cursor=False)
    defs = (f'<clipPath id="win"><rect width="{W}" height="{H}" rx="16"/></clipPath>')
    frame = (
        f'<rect width="{W}" height="{H}" rx="16" fill="#0E1019"/><rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="15.5" stroke="#3A3356"/>'
        f'<path d="M0 16a16 16 0 0 1 16-16h{W - 32}a16 16 0 0 1 16 16V38H0Z" fill="#181A28"/>'
        '<circle cx="24" cy="19" r="5.5" fill="#FF5F56"/><circle cx="44" cy="19" r="5.5" fill="#FFBD2E"/><circle cx="64" cy="19" r="5.5" fill="#27C93F"/>'
        f'<text x="{W // 2}" y="23" text-anchor="middle" font-family="{MONO}" font-size="12" fill="#9DA4B4">anurag — zsh</text>'
        f'<text x="28" y="64" font-family="{MONO}" font-size="12" fill="#6C7389">// interactive in spirit. legally an svg.</text>'
        f'<text x="28" y="{H - 22}" font-family="{MONO}" font-size="11" fill="#5B6579">exit 0 · no warranties expressed or implied</text>'
    )
    return svg_doc(W, H, frame + body, defs, "", "A terminal typing out sarcastic commands, including a live weather check for Dehradun.")


# ----------------------------------------------------------------------------
# Architecture diagrams (animated packets)
# ----------------------------------------------------------------------------
def d_defs(accent, W, H):
    return (
        f'<linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse"><stop stop-color="#0B0D14"/>'
        '<stop offset=".6" stop-color="#151225"/><stop offset="1" stop-color="#1D1630"/></linearGradient>'
        '<pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" stroke="#BBA2E8" stroke-opacity=".06"/></pattern>'
        '<marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 1L9 5L0 9Z" fill="#8C7BC4"/></marker>'
        f'<radialGradient id="pk"><stop stop-color="{accent}"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
    )


def d_frame(W, H, title):
    return (f'<rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/><rect width="{W}" height="{H}" rx="18" fill="url(#grid)"/>'
            f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="17.5" stroke="#2A2440"/>'
            f'<text x="30" y="34" font-family="{MONO}" font-size="12" fill="{MUTED}">{escape(title)}</text>')


def d_node(x, y, w, h, label, sub, accent=None):
    stroke = accent or LINE
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="#171A29" stroke="{stroke}" stroke-opacity="{1 if accent else .9}"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 - 1}" text-anchor="middle" font-family="{MONO}" font-size="13" font-weight="600" fill="{TEXT}">{escape(label)}</text>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 15}" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{MUTED}">{escape(sub)}</text>')


def d_edge(eid, path, accent, delay, dur=2.8, dashed=False, packet=True):
    dash = ' stroke-dasharray="4 5"' if dashed else ""
    out = f'<path id="{eid}" d="{path}" stroke="#5B4B8A" stroke-width="1.5" fill="none"{dash} marker-end="url(#ar)"/>'
    if packet:
        hide = lambda to: f'<set attributeName="opacity" to="{to}" begin="{delay}s" fill="freeze"/>'  # noqa: E731
        mp = f'<mpath href="#{eid}" xlink:href="#{eid}"/>'
        out += (f'<circle r="7" fill="url(#pk)" opacity="0">{hide(.9)}<animateMotion dur="{dur}s" begin="{delay}s" repeatCount="indefinite">{mp}</animateMotion></circle>'
                f'<circle r="2.6" fill="#fff" opacity="0">{hide(1)}<animateMotion dur="{dur}s" begin="{delay}s" repeatCount="indefinite">{mp}</animateMotion></circle>')
    return out


def d_label(x, y, text, anchor="middle"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{MONO}" font-size="9.5" fill="{MUTED}">{escape(text)}</text>'


def make_diagram_deployforge(scene):
    W, H = 1000, 300
    a = SEASONS[scene["season"]]["accent"]
    nodes = (
        d_node(30, 56, 150, 52, "GitHub repo", "connect + trigger")
        + d_node(230, 56, 150, 52, "Node.js API", "builds + deploys", a)
        + d_node(430, 56, 150, 52, "Redis Streams", "build queue")
        + d_node(630, 56, 150, 52, "Build worker", "clone + build")
        + d_node(830, 56, 150, 52, "Docker", "app container")
        + d_node(330, 192, 150, 52, "PostgreSQL", "deploy lifecycle")
        + d_node(630, 192, 150, 52, "visitor", "public url")
        + d_node(830, 192, 150, 52, "Nginx proxy", "dynamic routing", a)
    )
    edges = (
        d_edge("e1", "M180 82 L228 82", a, 0.0)
        + d_edge("e2", "M380 82 L428 82", a, 0.5)
        + d_edge("e3", "M580 82 L628 82", a, 1.0)
        + d_edge("e4", "M780 82 L828 82", a, 1.5)
        + d_edge("e5", "M305 108 C305 150 405 150 405 190", a, 0.4, 2.6)
        + d_edge("e6", "M705 108 C705 152 560 218 482 218", a, 1.2, 3.0, dashed=True)
        + d_edge("e7", "M780 218 L828 218", a, 0.2)
        + d_edge("e8", "M905 190 L905 110", a, 0.9, 2.2)
    )
    labels = (d_label(205, 74, "repo") + d_label(405, 74, "enqueue") + d_label(605, 74, "consume") + d_label(805, 74, "run")
              + d_label(330, 160, "lifecycle", "end") + d_label(610, 190, "status", "end") + d_label(805, 210, "https") + d_label(918, 154, "proxy", "start"))
    return svg_doc(W, H, d_frame(W, H, "deployforge / request path") + edges + nodes + labels, d_defs(a, W, H), "",
                   "DeployForge architecture: GitHub repo to Node.js API to Redis Streams to a build worker to Docker, with PostgreSQL tracking state and Nginx routing visitors to the container.")


def make_diagram_scaleflow(scene):
    W, H = 1000, 300
    a = SEASONS[scene["season"]]["accent"]
    clients = "".join(d_node(30, y, 140, 46, f"client {c}", "request") for c, y in (("a", 52), ("b", 127), ("c", 202)))
    servers = "".join(d_node(780, y, 150, 46, f"server {i}", "healthy") + f'<circle cx="{780 + 134}" cy="{y + 14}" r="3.5" fill="#9ECE6A"><animate attributeName="opacity" values="1;.3;1" dur="{2 + i * .5}s" repeatCount="indefinite"/></circle>'
                      for i, y in ((1, 52), (2, 127), (3, 202)))
    lb = d_node(390, 100, 220, 98, "ScaleFlow", "load balancer", a)
    edges = (
        d_edge("c1", "M170 75 C280 75 300 135 388 135", a, 0.0)
        + d_edge("c2", "M170 150 L388 150", a, 0.7)
        + d_edge("c3", "M170 225 C280 225 300 165 388 165", a, 1.4)
        + d_edge("s1", "M612 135 C700 135 700 75 778 75", a, 0.3)
        + d_edge("s2", "M612 150 L778 150", a, 1.0)
        + d_edge("s3", "M612 165 C700 165 700 225 778 225", a, 1.7)
    )
    health = (f'<path d="M952 66 V238" stroke="#9ECE6A" stroke-opacity=".55" stroke-dasharray="3 5"/>'
              f'<circle cx="952" cy="152" r="5" fill="#9ECE6A"><animate attributeName="r" values="4;7;4" dur="2.2s" repeatCount="indefinite"/></circle>'
              f'<text transform="translate(974 152) rotate(90)" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{MUTED}">health checks</text>')
    labels = (d_label(700, 100, "round robin", "middle") + d_label(700, 144, "least connections", "middle") + d_label(700, 214, "weighted", "middle")
              + d_label(500, 222, "sockets · multithreaded", "middle"))
    return svg_doc(W, H, d_frame(W, H, "scaleflow / request path") + edges + clients + lb + servers + health + labels, d_defs(a, W, H), "",
                   "ScaleFlow architecture: clients send requests to the load balancer, which routes to three servers using round robin, least connections or weighted scheduling, with health checks on each server.")


# ----------------------------------------------------------------------------
# Contributions
# ----------------------------------------------------------------------------
LEVEL_COLORS = ["#191D28", "#2D2148", "#4E317D", "#875BC1", "#CDB8FA"]
GQL_LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def dow(d: date) -> int:  # Sunday = 0
    return (d.weekday() + 1) % 7


def to_grid(days: dict) -> list:
    """days: {date: (level, count)} -> 53 x 7 grid of (level, count) or None."""
    first = min(days)
    start = first - timedelta(days=dow(first))
    grid = [[None] * 7 for _ in range(53)]
    for d, val in days.items():
        wi = (d - start).days // 7
        if 0 <= wi < 53:
            grid[wi][dow(d)] = val
    return grid


def gql_contributions():
    token = os.getenv("PROFILE_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("no GitHub token in the environment")
    query = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{totalContributions "
             "weeks{contributionDays{contributionCount contributionLevel date}}}}}}")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USERNAME}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "anurag-profile-animations"},
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = json.loads(resp.read().decode())
    if body.get("errors"):
        raise RuntimeError("; ".join(e.get("message", "?") for e in body["errors"]))
    cal = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = {}
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            days[date.fromisoformat(day["date"])] = (GQL_LEVELS.get(day["contributionLevel"], 0), int(day["contributionCount"]))
    return to_grid(days), int(cal["totalContributions"])


def scrape_contributions():
    path = os.getenv("CONTRIB_HTML")
    if path:
        html = Path(path).read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(f"https://github.com/users/{USERNAME}/contributions",
                                     headers={"User-Agent": "Mozilla/5.0 (profile-animations)", "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", "replace")
    tips = dict(re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>([^<]*)</tool-tip>', html))
    days = {}
    for tag in re.findall(r"<td\b[^>]*ContributionCalendar-day[^>]*>", html):
        d, lv, i = (re.search(p, tag) for p in (r'data-date="([^"]+)"', r'data-level="(\d)"', r'\bid="([^"]+)"'))
        if not (d and lv and i):
            continue
        m = re.match(r"\s*(\d+)\s+contribution", tips.get(i.group(1), ""))
        days[date.fromisoformat(d.group(1))] = (int(lv.group(1)), int(m.group(1)) if m else 0)
    if not days:
        raise RuntimeError("no contribution cells found in the page")
    return to_grid(days), sum(c for _, c in days.values())


def demo_contributions():
    rng = random.Random(28)
    grid = [[(0 if rng.random() > .45 else rng.randint(1, 4), 0) for _ in range(7)] for _ in range(53)]
    return grid, 0


def load_contributions():
    if os.getenv("DEMO_MODE") == "1":
        return demo_contributions()[0], 0, "sample data"
    for name, fn in (("api", gql_contributions), ("public page", scrape_contributions)):
        try:
            grid, total = fn()
            print(f"Contributions: {total} via {name}.")
            return grid, total, "public calendar"
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: contributions via {name} failed: {exc}", file=sys.stderr)
    return [[None] * 7 for _ in range(53)], 0, "data unavailable"


# ----------------------------------------------------------------------------
# Mascot + contribution punch scene
# ----------------------------------------------------------------------------
def _pts(points):
    return " ".join(f"{x},{y}" for x, y in points)


def _line(points, color, width):
    return f'<polyline points="{_pts(points)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'


def _ell(cx, cy, rx, ry, fill, stroke=None, sw=1):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}"{s}/>'


def _legs(phase):
    if phase == "A":
        l1, l2 = [(38, 75), (34, 87), (23, 94), (17, 91)], [(52, 74), (58, 84), (71, 86), (75, 82)]
    else:
        l1, l2 = [(38, 75), (43, 85), (53, 91), (60, 88)], [(52, 74), (47, 85), (33, 86), (28, 82)]
    out = _line(l1, "#272637", 8) + _line(l2, "#272637", 8)
    for pts in (l1, l2):
        fx, fy = pts[-1]
        out += _ell(fx + .5, fy + 1.5, 7.5, 3.5, "#E8E8F4") + f'<line x1="{fx - 5}" y1="{fy + 1}" x2="{fx + 5}" y2="{fy + 1}" stroke="#A989E2" stroke-width="2" stroke-linecap="round"/>'
    return out


def _arm_back(sw):
    return _line([(26, 52), (15, 61 + sw), (10, 54 + sw)], "#211C33", 9) + _ell(10, 55 + sw, 4, 4, "#EFBEB1")


def _arm_front(sw):
    return _line([(58, 51), (68, 60 - sw), (74, 51 - sw)], "#211C33", 9) + _ell(74, 51 - sw, 4, 4, "#EFBEB1")


def mascot(punch_spans, cycle):
    """Original anime-style runner. Local coordinates ~80 x 102, faces right."""
    toggle = lambda a, b: (  # noqa: E731 - tiny local helper
        f'<g opacity="{a}"><animate attributeName="opacity" values="{a};{b}" keyTimes="0;.5" dur="0.32s" calcMode="discrete" repeatCount="indefinite"/>', "</g>")
    ga, gb = toggle(1, 0), toggle(0, 1)
    legs = ga[0] + _legs("A") + ga[1] + gb[0] + _legs("B") + gb[1]
    back = ga[0] + _arm_back(-5) + ga[1] + gb[0] + _arm_back(5) + gb[1]
    front = ga[0] + _arm_front(-5) + ga[1] + gb[0] + _arm_front(5) + gb[1]
    punch = (_line([(58, 51), (78, 48), (94, 46)], "#211C33", 9) + _ell(98, 46, 6, 5.5, "#EFBEB1")
             + '<g stroke="#BB9AF7" stroke-width="2" stroke-linecap="round" opacity=".8"><line x1="66" y1="38" x2="82" y2="39"/><line x1="64" y1="56" x2="80" y2="55"/></g>')
    head = (
        f'<polygon points="{_pts([(20, 29), (17, 17), (27, 20), (30, 8), (39, 17), (49, 7), (53, 18), (66, 13), (62, 26), (73, 32), (65, 43), (27, 45)])}" fill="#181623"/>'
    )
    torso = (
        f'<polygon points="{_pts([(25, 45), (57, 44), (68, 65), (61, 79), (28, 79), (17, 65)])}" fill="#251D39" stroke="#645391" stroke-width="2" stroke-linejoin="round"/>'
        f'<polygon points="{_pts([(29, 47), (53, 47), (58, 73), (27, 73)])}" fill="#33264E"/>' + _line([(34, 66), (51, 66), (54, 71)], "#6A4D97", 2)
    )
    face = (
        _ell(46, 46.5, 7, 7.5, "#E5B1A4") + _ell(44.5, 38, 18.5, 19, "#F5CDBE", "#AF7F89", 1) + _ell(62, 39, 4, 5, "#EEBEB1")
        + f'<polygon points="{_pts([(24, 34), (20, 23), (27, 12), (35, 18), (41, 8), (48, 18), (58, 12), (64, 24), (60, 34), (51, 29), (45, 37), (39, 29), (32, 38)])}" fill="#191625"/>'
        + _ell(51, 38, 3, 3, "#4F427F") + _ell(52, 36, 1, 1, "#F5EEFF") + _line([(43, 47), (48, 48)], "#9D6378", 1)
        + _line([(41, 51), (42, 59)], VIOLET, 1) + _line([(47, 51), (48, 58)], VIOLET, 1) + _line([(29, 20), (37, 15), (41, 17)], "#4E4368", 2)
    )
    bob = '<animateTransform attributeName="transform" type="translate" values="0 0;0 -2" keyTimes="0;.5" dur="0.32s" calcMode="discrete" repeatCount="indefinite"/>'
    return (
        _ell(47, 97.5, 33, 3.5, "#05040A") + legs
        + f'<g>{bob}{head}{back}{torso}'
        + f'<g>{windows(punch_spans, cycle, base="1", on="0")}{front}</g>'
        + f'<g opacity="0">{windows(punch_spans, cycle)}{punch}</g>{face}</g>'
    )


CHIPS = ["fix: typo", "feat: coffee", "wip", "final_FINAL_v2", "it works?", "TODO: later", "refactor: why", "merge conflict"]
WORDS = ["pow!", "bam!", "fixed!", "shipped!", "nope!", "merged!", "gone!", "lgtm!"]


def pick_cells(grid, k, seed):
    rng = random.Random(seed)
    cells = [(w, d) for w, col in enumerate(grid) for d, v in enumerate(col) if v and v[0] >= 2]
    cells = cells or [(w, d) for w, col in enumerate(grid) for d, v in enumerate(col) if v and v[0] >= 1]
    cells = cells or [(w, d) for w, col in enumerate(grid) for d, v in enumerate(col) if v]
    if not cells:
        return []
    chosen = sorted(rng.sample(cells, min(k, len(cells))))
    while len(chosen) < k:
        chosen.append(chosen[len(chosen) % max(1, len(chosen))])
    return chosen


def burst_points(r_out=26, r_in=10, spikes=8):
    pts = []
    for i in range(spikes * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi * i / spikes - math.pi / 2
        pts.append(f"{fmt(r * math.cos(a))},{fmt(r * math.sin(a))}")
    return " ".join(pts)


def make_runner(scene, grid, total, source):
    W, H = 1100, 390
    a = SEASONS[scene["season"]]["accent"]
    cell, gap = 12, 5
    gw = 53 * (cell + gap) - gap
    gx, gy = (W - gw) // 2, 84
    C, n = 15.0, len(CHIPS)
    hit_x, fist_y = 252, 274
    t_hits = [2.3 + i * 1.55 for i in range(n)]
    spans = [(t - 0.1, t + 0.22) for t in t_hits]
    cells = pick_cells(grid, n, 5)

    defs = (
        f'<linearGradient id="bg" x1="0" y1="0" x2="{W}" y2="{H}" gradientUnits="userSpaceOnUse"><stop stop-color="#0B0D14"/><stop offset=".6" stop-color="#151225"/><stop offset="1" stop-color="#1D1630"/></linearGradient>'
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="20"/></clipPath><clipPath id="gridclip"><rect x="{gx}" y="{gy}" width="{gw}" height="114"/></clipPath>'
        '<linearGradient id="sweep"><stop stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        + COMMON_DEFS
    )
    grid_svg = ""
    for wi, col in enumerate(grid):
        for di, v in enumerate(col):
            if v is None:
                continue
            grid_svg += f'<rect x="{gx + wi * (cell + gap)}" y="{gy + di * (cell + gap)}" width="{cell}" height="{cell}" rx="2.5" fill="{LEVEL_COLORS[v[0]]}"/>'
    sweep = (f'<g clip-path="url(#gridclip)"><rect y="{gy}" width="140" height="114" fill="url(#sweep)"><animate attributeName="x" values="{gx - 140};{gx + gw}" dur="7s" repeatCount="indefinite"/></rect></g>')

    action = ""
    for i, t in enumerate(t_hits):
        text = CHIPS[i]
        cw_chip = len(text) * 6.7 + 34
        t0 = t - 2.2
        # chip: slides in, gets hit, tumbles away
        pos = [(0, "1200,0"), (t0, "1200,0"), (t, f"{hit_x},0"), (t + .7, f"{hit_x + 170},-120"), (C, f"{hit_x + 170},-120")]
        rot = [(0, f"0 {fmt(cw_chip / 2)} 0"), (t, f"0 {fmt(cw_chip / 2)} 0"), (t + .7, f"540 {fmt(cw_chip / 2)} 0"), (C, f"540 {fmt(cw_chip / 2)} 0")]
        op = [(0, "0"), (t0, "0"), (t0 + .08, "1"), (t + .05, "1"), (t + .7, "0"), (C, "0")]
        action += (
            f'<g transform="translate(0,{fist_y})"><g>{animate(None, pos, C, transform="translate")}'
            f'<g opacity="0">{animate("opacity", op, C)}<g>{animate(None, rot, C, transform="rotate")}'
            f'<rect x="0" y="-12" width="{fmt(cw_chip)}" height="24" rx="8" fill="#1B1730" stroke="{a}"/>'
            f'<circle cx="13" cy="0" r="3" fill="{a}"/>'
            f'<text x="24" y="4" font-family="{MONO}" font-size="11" fill="{TEXT}">{escape(text)}</text></g></g></g></g>'
        )
        # impact burst + word
        bop = [(0, "0"), (t, "0"), (t + .02, "1"), (t + .45, "0"), (C, "0")]
        bsc = [(0, "0.1"), (t, "0.1"), (t + .12, "1.1"), (t + .45, "1.5"), (C, "1.5")]
        wop = [(0, "0"), (t, "0"), (t + .04, "1"), (t + .75, "0"), (C, "0")]
        wy = [(0, "0"), (t, "0"), (t + .75, "-20"), (C, "-20")]
        action += (
            f'<g transform="translate({hit_x + 8},{fist_y})" opacity="0">{animate("opacity", bop, C)}<g>{animate(None, bsc, C, transform="scale")}'
            f'<polygon points="{burst_points()}" fill="{a}"/><polygon points="{burst_points(15, 6)}" fill="#FFF6E5"/></g></g>'
            f'<g transform="translate({hit_x + 14},{fist_y - 34})" opacity="0">{animate("opacity", wop, C)}<g>{animate(None, [(t_, f"0 {y}") for t_, y in wy], C, transform="translate")}'
            f'<text font-family="{MONO}" font-size="15" font-weight="800" fill="{a}">{WORDS[i]}</text></g></g>'
        )
        # the matching contribution square flashes
        if i < len(cells):
            wi, di = cells[i]
            fop = [(0, "0"), (t, "0"), (t + .04, ".95"), (t + .9, "0"), (C, "0")]
            action += (f'<rect x="{gx + wi * (cell + gap) - 2}" y="{gy + di * (cell + gap) - 2}" width="{cell + 4}" height="{cell + 4}" rx="4" fill="#FFF1D6" stroke="{a}" stroke-width="1.5" opacity="0">'
                       f'{animate("opacity", fop, C)}</rect>')

    runway = (f'<line x1="42" y1="337" x2="{W - 42}" y2="337" stroke="#30284A" stroke-width="2"/>'
              f'<line x1="42" y1="337" x2="{W - 42}" y2="337" stroke="#7A64B8" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 22">'
              '<animate attributeName="stroke-dashoffset" values="0;24" dur="0.6s" repeatCount="indefinite"/></line>')
    info = f"{total:,} contributions in the last year · {source}" if total or source == "public calendar" else source
    legend = "".join(f'<rect x="{gx + gw - 96 + i * 17}" y="{gy + 124}" width="11" height="11" rx="2.5" fill="{c}"/>' for i, c in enumerate(LEVEL_COLORS))
    body = (
        f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="url(#bg)"/>'
        f'{scene_layer(scene, W, H, 22, 411, speed=(30, 52), amp=(8, 20), size=(.8, 1.3))}</g>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="19.5" stroke="#2A2440"/>'
        f'<text x="42" y="46" font-family="{MONO}" font-size="16" fill="{TEXT}">anurag / contribution field</text>'
        f'<text x="{W - 42}" y="46" text-anchor="end" font-family="{MONO}" font-size="12" fill="{a}">{escape(info)}</text>'
        f'{grid_svg}{sweep}'
        f'<text x="{gx}" y="{gy + 134}" font-family="{MONO}" font-size="10" fill="{MUTED}">punch a commit. watch a square light up.</text>'
        f'<text x="{gx + gw - 106}" y="{gy + 134}" text-anchor="end" font-family="{MONO}" font-size="10" fill="{MUTED}">less</text>'
        f'{legend}<text x="{gx + gw + 8}" y="{gy + 134}" font-family="{MONO}" font-size="10" fill="{MUTED}">more</text>'
        f'{runway}<g transform="translate(150,228)">{mascot(spans, C)}</g>{action}'
        f'<text x="42" y="{H - 24}" font-family="{MONO}" font-size="11" fill="{MUTED}">commit. compile. repeat. pretend this was the plan.</text>'
    )
    return svg_doc(W, H, body, defs, base_css(H), "An anime developer runs in place and punches flying commit messages while the matching squares in the GitHub contribution calendar light up.")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
RAIL_HEIGHTS = {"about": 290, "terminal": 330, "projects": 1150, "runner": 300, "contact": 240}
BAND_COUNT = 7


def write(name: str, content: str) -> None:
    (ASSETS / name).write_text(content, encoding="utf-8")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    state = ASSETS / "scene.json"
    previous = json.loads(state.read_text()) if state.exists() else None
    now = datetime.now(IST)
    scene = build_scene(now, fetch_weather(), previous)
    grid, total, source = load_contributions()

    write("hero.svg", make_hero(scene))
    write("terminal.svg", make_terminal(scene))
    write("contribution-runner.svg", make_runner(scene, grid, total, source))
    write("diagram-deployforge.svg", make_diagram_deployforge(scene))
    write("diagram-scaleflow.svg", make_diagram_scaleflow(scene))
    for i in range(BAND_COUNT):
        write(f"band-{i}.svg", make_band(scene, i))
    for i, (name, h) in enumerate(RAIL_HEIGHTS.items()):
        write(f"rail-{name}-l.svg", make_rail(scene, h, "l", i))
        write(f"rail-{name}-r.svg", make_rail(scene, h, "r", i))
    write("rail-blank.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>\n')
    state.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    print(f"Scene: {scene['season']} / {scene['kind']} / {scene['cond']} / {'day' if scene['is_day'] else 'night'} "
          f"{'(live weather)' if scene['live'] else '(season mode)'}; contributions: {source}.")


if __name__ == "__main__":
    main()
