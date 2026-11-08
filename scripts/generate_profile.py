#!/usr/bin/env python3
"""Generate Anurag's animated GitHub profile assets.

- contribution-anime.gif: real GitHub contribution levels + an original running mascot
- seasonal-atmosphere.gif: month-based seasonal particles (India / Asia-Kolkata calendar)
- terminal.gif: looping, deliberately non-interactive terminal vignette

No external image or animation service is required at runtime. Pillow is the only dependency.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
USERNAME = os.getenv("GITHUB_USERNAME", "anuragdevcode")
IST = ZoneInfo("Asia/Kolkata")

BG = (10, 12, 19)
PANEL = (16, 19, 29)
PURPLE = (187, 154, 247)
LAVENDER = (218, 199, 255)
MUTED = (129, 139, 158)
TEXT = (232, 234, 242)


def font(size: int, mono: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf"]
        if mono else
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/lato/Lato-Medium.ttf"]
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def current_season(now: datetime) -> tuple[str, str, tuple[int, int, int], str]:
    """A simple Dehradun-inspired calendar, not a live weather observation."""
    month = now.month
    if month in (3, 4):
        return "SPRING", "PETALS / NEW BUILDS", (238, 154, 195), "new things bloom. old bugs survive."
    if month in (5, 6):
        return "SUMMER", "FIREFLIES / HOT TAKES", (255, 196, 104), "high temperatures. higher abstractions."
    if month in (7, 8, 9):
        return "MONSOON", "RAIN / REBUILD", (123, 177, 224), "the sky is crying. CI is too."
    if month in (10, 11):
        return "AUTUMN", "FALLING PETALS / SOFT CHAOS", (238, 173, 158), "petals in the air. bugs in the code."
    return "WINTER", "SNOW / LOW LATENCY", (184, 207, 244), "cold hands. warm terminal."


def gql_contributions() -> tuple[list[list[int]], int]:
    """Read the public contribution calendar through GitHub GraphQL."""
    token = os.getenv("PROFILE_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("No GitHub token found. Set PROFILE_TOKEN or GITHUB_TOKEN.")
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount } }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": USERNAME}}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "anurag-profile-animations",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        body = json.loads(response.read().decode("utf-8"))
    if body.get("errors"):
        raise RuntimeError("GitHub GraphQL: " + "; ".join(e.get("message", "unknown error") for e in body["errors"]))
    calendar = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [[int(day["contributionCount"]) for day in week["contributionDays"]] for week in calendar["weeks"]]
    return weeks, int(calendar["totalContributions"])


def demo_contributions() -> tuple[list[list[int]], int]:
    rng = random.Random(28)
    weeks = []
    for w in range(53):
        col = []
        for d in range(7):
            # Deterministic sample data for local previews only; never enabled by CI.
            wave = (math.sin(w / 5.0) + 1) / 2
            count = 0 if rng.random() > (0.34 + wave * 0.5) else rng.randint(1, 11)
            col.append(count)
        weeks.append(col)
    return weeks, sum(map(sum, weeks))


def normalize_grid(weeks: list[list[int]]) -> list[list[int]]:
    grid = [list(week[:7]) + [0] * max(0, 7 - len(week)) for week in weeks[:53]]
    while len(grid) < 53:
        grid.append([0] * 7)
    return grid


def contribution_palette(weeks: list[list[int]]) -> list[tuple[int, int, int]]:
    values = sorted(v for week in weeks for v in week if v > 0)
    if not values:
        return [(25, 29, 40), (44, 33, 68), (73, 48, 112), (132, 91, 188), (193, 164, 245)]
    qs = [values[min(len(values) - 1, int((len(values) - 1) * q))] for q in (0.25, 0.5, 0.75)]
    levels = [
        (25, 29, 40),
        (45, 33, 72),
        (78, 49, 125),
        (135, 91, 193),
        (205, 184, 250),
    ]
    def level(value: int) -> int:
        if value <= 0: return 0
        if value <= qs[0]: return 1
        if value <= qs[1]: return 2
        if value <= qs[2]: return 3
        return 4
    return levels


def pick_level(value: int, weeks: list[list[int]]) -> int:
    values = sorted(v for week in weeks for v in week if v > 0)
    if value <= 0 or not values:
        return 0
    q1, q2, q3 = [values[min(len(values)-1, int((len(values)-1)*q))] for q in (0.25, 0.5, 0.75)]
    return 1 if value <= q1 else 2 if value <= q2 else 3 if value <= q3 else 4


def draw_mascot(draw: ImageDraw.ImageDraw, x: float, baseline: float, frame: int, s: int = 2) -> None:
    """Small original anime-inspired runner, drawn as vector-like primitives."""
    # All coordinates are local to the character; x is its left edge.
    def pt(a: float, b: float) -> tuple[int, int]:
        return (int((x + a) * s), int((baseline + b - 98) * s))
    def ellipse(box, fill, outline=None, width=1):
        x1, y1, x2, y2 = box
        mapped = (x + x1, baseline + y1 - 98, x + x2, baseline + y2 - 98)
        draw.ellipse(tuple(int(v * s) for v in mapped), fill=fill, outline=outline, width=max(1, int(width*s)))
    def polygon(points, fill, outline=None):
        draw.polygon([pt(a,b) for a,b in points], fill=fill)
        if outline:
            draw.line([pt(a,b) for a,b in points + [points[0]]], fill=outline, width=2*s, joint="curve")
    def line(points, fill, width):
        draw.line([pt(a,b) for a,b in points], fill=fill, width=max(1,width*s), joint="curve")

    bob = (frame % 4 in (1, 2)) * -2
    # Ground shadow
    ellipse((14, 94, 80, 101), (25, 20, 38))
    # Back hair silhouette
    polygon([(20, 29+bob),(17,17+bob),(27,20+bob),(30,8+bob),(39,17+bob),(49,7+bob),(53,18+bob),(66,13+bob),(62,26+bob),(73,32+bob),(65,43+bob),(27,45+bob)], (24,22,35))
    # Legs / sneakers alternate to create a running cycle
    phase = frame % 8
    if phase in (0, 1, 2, 3):
        leg1 = [(38,75+bob),(34,87),(23,94),(17,91)]
        leg2 = [(52,74+bob),(58,84),(71,86),(75,82)]
    else:
        leg1 = [(38,75+bob),(43,85),(53,91),(60,88)]
        leg2 = [(52,74+bob),(47,85),(33,86),(28,82)]
    line(leg1, (39,38,55), 8)
    line(leg2, (39,38,55), 8)
    # Sneakers
    for fx, fy in ((leg1[-1][0],leg1[-1][1]), (leg2[-1][0],leg2[-1][1])):
        ellipse((fx-7, fy-2, fx+8, fy+5), (232,232,244))
        line([(fx-5,fy+1),(fx+5,fy+1)], (169,137,226), 2)
    # Hoodie torso
    polygon([(25,45+bob),(57,44+bob),(68,65+bob),(61,79+bob),(28,79+bob),(17,65+bob)], (37,29,57), (100,83,145))
    polygon([(29,47+bob),(53,47+bob),(58,73+bob),(27,73+bob)], (51,38,78))
    # Hoodie pocket + tiny terminal mark
    line([(34,66+bob),(51,66+bob),(54,71+bob)], (106,77,151), 2)
    # Arms swing
    swing = -5 if phase < 4 else 5
    line([(26,52+bob),(15,61+bob+swing),(10,54+bob+swing)], (33,28,51), 9)
    line([(58,51+bob),(68,60+bob-swing),(74,51+bob-swing)], (33,28,51), 9)
    ellipse((6, 51+bob+swing, 14, 59+bob+swing), (239,190,177))
    ellipse((70, 47+bob-swing, 78, 55+bob-swing), (239,190,177))
    # Neck and face
    ellipse((39,39+bob,53,54+bob), (229,177,164))
    ellipse((26,19+bob,63,57+bob), (245,205,190), (175,127,137), 1)
    # Ear
    ellipse((58,34+bob,66,44+bob), (238,190,177))
    # Hair fringe, deliberately tousled
    polygon([(24,34+bob),(20,23+bob),(27,12+bob),(35,18+bob),(41,8+bob),(48,18+bob),(58,12+bob),(64,24+bob),(60,34+bob),(51,29+bob),(45,37+bob),(39,29+bob),(32,38+bob)], (25,22,37))
    # Visible eye and glint
    ellipse((48,35+bob,54,41+bob), (79,66,127))
    ellipse((51,35+bob,53,37+bob), (245,238,255))
    line([(43,47+bob),(48,48+bob)], (157,99,120), 1)
    # Violet hoodie drawstrings
    line([(41,51+bob),(42,59+bob)], (187,154,247), 1)
    line([(47,51+bob),(48,58+bob)], (187,154,247), 1)
    # Hair highlights
    line([(29,20+bob),(37,15+bob),(41,17+bob)], (78,67,104), 2)


def seasonal_particles(draw: ImageDraw.ImageDraw, width: int, height: int, frame: int, season: str, rng_seed: int = 41) -> None:
    rng = random.Random(rng_seed)
    for i in range(44):
        base_x = rng.randrange(width)
        base_y = rng.randrange(height)
        speed = 1 + (i % 4)
        x = (base_x + frame * (0.8 + speed * 0.33) + math.sin(frame / 5 + i) * 9) % width
        y = (base_y + frame * speed * 0.55) % height
        if season == "MONSOON":
            draw.line((int(x), int(y), int(x-3), int(y+12+speed*2)), fill=(93, 147, 203), width=1)
        elif season == "WINTER":
            r = 1 + (i % 3)
            draw.ellipse((int(x-r), int(y-r), int(x+r), int(y+r)), fill=(185, 207, 242))
            if i % 5 == 0:
                draw.line((int(x-3),int(y),int(x+3),int(y)), fill=(218,228,248), width=1)
        elif season == "SUMMER":
            r = 1 + (i % 2)
            draw.ellipse((int(x-r), int(y-r), int(x+r), int(y+r)), fill=(255, 203, 111))
        else:
            # Petals for AUTUMN are intentionally warm peach + lavender.
            if season == "AUTUMN":
                color = (238, 173, 158) if i % 2 else (187, 154, 247)
            else:
                color = (238, 154, 195) if i % 2 else (187, 154, 247)
            size = 8 if i % 6 == 0 else 5
            draw.ellipse((int(x-size), int(y-size/2), int(x+size), int(y+size/2)), fill=color)
            draw.ellipse((int(x-size/2), int(y-size), int(x+size/2), int(y+size)), fill=tuple(max(0,c-18) for c in color))


def make_contribution_gif(weeks: list[list[int]], total: int, now: datetime, season_info: tuple, source_label: str) -> None:
    width, height, scale = 1100, 360, 2
    season, season_label, accent, _ = season_info
    palette = contribution_palette(weeks)
    frames = []
    total_frames = 48
    cell, gap = 12, 5
    graph_w = 53 * (cell + gap) - gap
    start_x = (width - graph_w) // 2
    graph_y = 103

    for frame in range(total_frames):
        im = Image.new("RGB", (width*scale, height*scale), BG)
        d = ImageDraw.Draw(im)
        def xy(v): return int(v*scale)
        # Soft decorative horizontal band
        d.rounded_rectangle((xy(18),xy(18),xy(width-18),xy(height-18)), radius=xy(18), fill=PANEL, outline=(37,35,53), width=xy(1))
        seasonal_particles(d, width*scale, height*scale, frame, season, 41)
        d.text((xy(42),xy(38)), "ANURAG / CONTRIBUTION FIELD", font=font(17*scale, True), fill=TEXT)
        d.text((xy(width-360),xy(42)), f"{total:,} CONTRIBUTIONS  ·  {source_label}", font=font(12*scale, True), fill=accent)
        # Month-ish ticks, deliberately decorative rather than date labels.
        d.text((xy(start_x),xy(77)), "LESS ACTIVITY", font=font(9*scale, True), fill=MUTED)
        d.text((xy(width-start_x-90),xy(77)), "MORE ACTIVITY", font=font(9*scale, True), fill=MUTED)
        # Contribution grid
        for wi, week in enumerate(weeks):
            for di, count in enumerate(week):
                level = pick_level(count, weeks)
                x = start_x + wi*(cell+gap)
                y = graph_y + di*(cell+gap)
                col = palette[level]
                d.rounded_rectangle((xy(x),xy(y),xy(x+cell),xy(y+cell)), radius=xy(2), fill=col)
        # Runway, little illuminated dashes
        runway_y = 307
        d.line((xy(42),xy(runway_y+7),xy(width-42),xy(runway_y+7)), fill=(48,39,68), width=xy(2))
        progress = frame/(total_frames-1)
        runner_x = 56 + progress*(width-130)
        for j in range(10):
            spark_x = runner_x - 16 - j*22
            if spark_x > 48:
                alpha_color = (113, 82, 157) if j < 3 else (60, 48, 83)
                d.ellipse((xy(spark_x),xy(runway_y+3),xy(spark_x+4),xy(runway_y+7)), fill=alpha_color)
        # Mascot at 2x resolution
        draw_mascot(d, runner_x-38, runway_y+6 + (math.sin(frame*math.pi/4)*2), frame, scale)
        d.text((xy(42),xy(337)), "COMMIT. COMPILE. REPEAT. PRETEND THIS WAS THE PLAN.", font=font(9*scale, True), fill=MUTED)
        frames.append(im.resize((width,height), Image.Resampling.LANCZOS).convert("P", palette=Image.Palette.ADAPTIVE, colors=192))

    frames[0].save(ASSETS/"contribution-anime.gif", save_all=True, append_images=frames[1:], duration=85, loop=0, optimize=True, disposal=2)


def make_seasonal_gif(now: datetime, season_info: tuple) -> None:
    season, season_label, accent, caption = season_info
    width, height, scale = 1100, 190, 2
    frames = []
    for frame in range(36):
        im = Image.new("RGB", (width*scale,height*scale), BG)
        d = ImageDraw.Draw(im)
        # Subtle gradient-ish vertical panels
        for x in range(width*scale):
            blend = x/(width*scale)
            c = tuple(int(BG[i]*(1-blend)+PANEL[i]*blend) for i in range(3))
            d.line((x,0,x,height*scale), fill=c)
        d.rounded_rectangle((18*scale,18*scale,(width-18)*scale,(height-18)*scale), radius=18*scale, outline=(50,43,68), width=scale)
        seasonal_particles(d,width*scale,height*scale,frame,season,97)
        d.text((54*scale,46*scale),season,font=font(26*scale,True),fill=accent)
        d.text((56*scale,87*scale),season_label,font=font(10*scale,True),fill=MUTED)
        d.text((56*scale,119*scale),caption,font=font(14*scale,False),fill=TEXT)
        d.text((850*scale,142*scale),"SEASONAL BUILD  /  ASIA-KOLKATA",font=font(9*scale,True),fill=MUTED)
        frames.append(im.resize((width,height),Image.Resampling.LANCZOS).convert("P",palette=Image.Palette.ADAPTIVE,colors=160))
    frames[0].save(ASSETS/"seasonal-atmosphere.gif",save_all=True,append_images=frames[1:],duration=120,loop=0,optimize=True,disposal=2)


def make_terminal_gif() -> None:
    width, height, scale = 1000, 330, 1
    scenes = [
        ("anurag@devbox ~ % whoami", "anurag — software engineer in progress"),
        ("anurag@devbox ~ % cat ~/.config/personality", "curious, mildly sarcastic, ships anyway."),
        ("anurag@devbox ~ % ls ~/projects", "DeployForge/  ScaleFlow/  NeuroNav/  LogicLab/  Tangent/"),
        ("anurag@devbox ~ % sudo make me productive", "permission denied: coffee required."),
    ]
    # Render progressive typing, then hold each completed terminal state.
    sequence: list[tuple[int,int]] = []
    for si, pair in enumerate(scenes):
        for li, line_text in enumerate(pair):
            for n in range(0,len(line_text)+1,2):
                sequence.append((si, li*1000+n))
        for _ in range(8):
            sequence.append((si, 9999))
    frames=[]
    f_title=font(12,True); f_body=font(15,True); f_small=font(11,True)
    for idx,(si,progress) in enumerate(sequence):
        im=Image.new("RGB",(width,height),(10,12,19))
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((1,1,width-2,height-2),radius=15,fill=(13,16,25),outline=(57,49,77),width=1)
        d.rounded_rectangle((2,2,width-3,38),radius=14,fill=(25,27,39))
        for cx,col in ((22,(255,95,86)),(42,(255,189,46)),(62,(39,201,63))):
            d.ellipse((cx-5,14,cx+5,24),fill=col)
        d.text((width//2-42,14),"anurag — zsh",font=f_title,fill=(157,164,180))
        d.text((28,58),"// interactive in spirit. legally a GIF.",font=f_small,fill=(104,111,132))
        y=94
        for old in range(si):
            d.text((28,y),scenes[old][0],font=f_body,fill=(187,154,247)); y+=25
            d.text((28,y),scenes[old][1],font=f_body,fill=(207,211,222)); y+=29
        command, result = scenes[si]
        if progress == 9999:
            shown_cmd, shown_res = command, result
        elif progress < 1000:
            shown_cmd, shown_res = command[:progress], ""
        else:
            shown_cmd, shown_res = command, result[:max(0,progress-1000)]
        d.text((28,y),shown_cmd,font=f_body,fill=(187,154,247))
        cursor_x=28+d.textlength(shown_cmd,font=f_body)+7
        if (idx//3)%2==0:
            d.rounded_rectangle((int(cursor_x),y+3,int(cursor_x+8),y+22),radius=2,fill=(187,154,247))
        y+=25
        if shown_res:
            d.text((28,y),shown_res,font=f_body,fill=(207,211,222))
        d.text((28,height-29),"EXIT 0   ·   NO WARRANTIES EXPRESSED OR IMPLIED",font=f_small,fill=(91,101,121))
        frames.append(im.convert("P",palette=Image.Palette.ADAPTIVE,colors=160))
    frames[0].save(ASSETS/"terminal.gif",save_all=True,append_images=frames[1:],duration=78,loop=0,optimize=True,disposal=2)


def main() -> None:
    now = datetime.now(IST)
    season_info = current_season(now)
    make_seasonal_gif(now,season_info)
    make_terminal_gif()
    if os.getenv("DEMO_MODE") == "1":
        weeks,total = demo_contributions()
        source_label = "SAMPLE DATA"
        print("Using deterministic demo contribution data (DEMO_MODE=1).")
    else:
        try:
            weeks,total = gql_contributions()
            source_label = "PUBLIC CALENDAR"
            print(f"Fetched {total:,} contributions for @{USERNAME}.")
        except Exception as exc:
            # Fail visibly, but still render an empty, honest grid so the workflow is debuggable.
            print(f"WARNING: Could not fetch contribution data: {exc}",file=sys.stderr)
            weeks,total = [[0]*7 for _ in range(53)],0
            source_label = "DATA UNAVAILABLE"
    make_contribution_gif(normalize_grid(weeks),total,now,season_info,source_label)
    print(f"Generated profile animations for {season_info[0]} in {ASSETS}.")

if __name__ == "__main__":
    main()
