# Setup

## 1. Copy the files into your profile repo (`anuragdevcode/anuragdevcode`)

Copy `README.md`, `assets/`, `scripts/`, `.github/` and `.gitignore`, then delete the files this version replaces:

```bash
git rm -f assets/header.svg assets/seasonal-atmosphere.gif assets/contribution-anime.gif assets/terminal.gif
```

Keep `assets/anime-desk-loop.gif` (your original art). `desk-200.gif` and `desk-96.gif` are resized copies the README uses on desktop and phones. No other GIFs are needed.

## 2. Let the workflow write to the repo

Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save.

## 3. Push

Pushing `scripts/generate_profile.py` triggers the first run. You can also start it manually:
Actions → **Refresh profile animations** → Run workflow. After that it runs every 3 hours and
commits only when something visible changed (season, weather type, day/night, a 3°C temperature
shift, or new contributions).

## What the scene follows

| Dehradun right now | Particles |
|---|---|
| Clear / cloudy | The season's own: autumn leaves, monsoon rain, winter snow, spring petals, summer fireflies |
| Drizzle / rain | Rain with ripples |
| Thunderstorm | Heavy rain plus lightning flashes |
| Snow | Snowfall |
| Fog | Drifting mist |
| Night | Darker hero with twinkling stars |

Seasons by month: Mar-Apr spring, May-Jun summer, Jul-Sep monsoon, Oct-Nov autumn, Dec-Feb winter.
If the weather API can't be reached the badge says `season mode` and the month decides. If the
contribution calendar can't be fetched the card says `data unavailable`. It never shows made-up numbers.

## Preview other weather locally

```bash
python3 scripts/generate_profile.py        # real data into ./assets
WEATHER_JSON='{"temp":22,"code":95,"is_day":false}' FORCE_SEASON=monsoon \
  OUT_DIR=/tmp/preview python3 scripts/generate_profile.py
```

Weather codes are Open-Meteo's WMO codes (0 clear, 3 cloudy, 45 fog, 61 rain, 71 snow, 95 thunderstorm).
Other overrides: `CONTRIB_HTML=saved.html` (offline calendar), `DEMO_MODE=1` (sample data, clearly labelled).

## Side rails

`README.md` puts a narrow particle rail on each side of the about, terminal, projects, runner and contact sections.
On screens under 700px wide the rails swap to empty margins so phone layouts stay readable. GitHub draws thin
borders around HTML table cells, so the rails sit in a bordered frame. If it looks wrong on your profile, use the
rail-free version (bands only):

```bash
mv README.no-rails.md README.md
```

## Good to know

- **Optional token.** The workflow tries the GraphQL API first and falls back to your public contribution page.
  Add a `PROFILE_TOKEN` repo secret (a classic token with `read:user`) only if you want private contributions counted.
- **Scheduled runs pause** after 60 days without repo activity on public repos. Re-enable under the Actions tab.
- **Stale images?** GitHub caches README images. Hard-refresh if a new scene doesn't show up.
- **Reduced motion:** with that OS setting on, falling particles are hidden. The typing animations still play.
- Weather data by [Open-Meteo.com](https://open-meteo.com/).
