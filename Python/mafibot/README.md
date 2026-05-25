# Mafibot

Human-like browser autopilot for [Mafiaspillet.no](https://mafiaspillet.no/), built on top of [webbot](../webbot/) (Playwright, curved mouse paths, variable delays, persistent Chrome profile).

The bot reads game state from the page DOM, chooses the next action (crime, travel, economy, messages, combat), and executes it through the same human-like input layer as webbot—not via the game API.

The live game runs at **`https://mafiaspillet.no/ms.php`** with Norwegian **tabs** (Kriminalitet, Flyplass, …) and a sidebar (Mine bedrifter, Mitt rederi). Navigation uses slow, human-paced clicks—typically **3+ seconds between clicks**, longer pauses after tab changes, and **30–130 s** jitter between action cycles.

## Terms of service

[Mafiaspillet section 7](https://mafiaspillet.no/?side=betingelser) forbids scripts, browser add-ons, and automation that performs or speeds up in-game actions (including automatic mouse movement). Using this tool can lead to **account bans**, loss of progress, or IP blocks.

Commands that start automation require `--accept-tos`. This project is for **personal / educational** use at your own risk.

## Requirements

- **Python 3.11 or 3.12** on Windows (required for reliable Playwright). Python 3.14 often breaks `greenlet` (`DLL load failed while importing _greenlet`). The package declares `requires-python <3.14`.
- Google Chrome (recommended; Playwright uses the `chrome` channel)
- Sibling package [Python/webbot](../webbot/) in this repo (imported automatically when you run `mafibot.py` from `Python/mafibot/`)

## Install

Use a **virtual environment** so `pip` and `python` refer to the same interpreter (and **not** broken packages under `%AppData%\Roaming\Python`):

```powershell
cd Python\mafibot
.\setup-windows.ps1
.\.venv\Scripts\Activate.ps1
python .\mafibot.py ui
```

Manual equivalent:

```powershell
cd Python\mafibot
py -3.12 -m venv .venv   # prefer 3.12, not 3.14
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install msvc-runtime
pip install -r requirements.txt
pip install -e .
python -m playwright install chromium
```

On Windows, install the official **[Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe)** if `greenlet` or Playwright fails with `DLL load failed`. Then reinstall with the **same** `python` you use for mafibot:

```powershell
python -m pip install --force-reinstall greenlet playwright
python -s -c "import greenlet; from playwright.async_api import Page; print('ok')"
```

Avoid the `msvc-runtime` pip package on Python 3.14 — it often fails the same way. Use Python 3.12 instead.

Optional credentials (auto-fill login): copy `.env.example` to `.env` and set `MAFIA_USER` / `MAFIA_PASS`. A saved session from `login` is usually enough; do not commit `.env`.

### Troubleshooting: `DLL load failed while importing _greenlet`

Your traceback shows `...\AppData\Roaming\Python\Python314\site-packages\` — that is a **per-user** install on **Python 3.14**. Global `python` will keep using it until you use a venv.

1. Install [VC++ Redistributable x64](https://aka.ms/vs/17/release/vc_redist.x64.exe) (one-time, system-wide).
2. **Do not use Python 3.14** — install [Python 3.12](https://www.python.org/downloads/), delete `.venv`, recreate with 3.12:
   `.\setup-windows.ps1 -PythonExe "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"`
3. Uninstall broken pip helper if present: `.\.venv\Scripts\python.exe -m pip uninstall -y msvc-runtime`
4. **Always** activate before mafibot: `.\.venv\Scripts\Activate.ps1` then `python .\mafibot.py …`
5. Manual check (must print `ok`): `.\.venv\Scripts\python.exe -s -c "import greenlet; from playwright.async_api import Page; print('ok')"`
6. Optional: `python -m pip uninstall -y greenlet playwright` on **global** Python only (Roaming user-site cleanup).

## Windows executable (single .exe)

Build a one-file `mafibot.exe` with PyInstaller (bundles Python, the bot, UI assets, default profiles, and Playwright Chromium). Expect **~200MB+** output and a slower first launch while the bundle extracts to `%TEMP%`.

**Build machine (Windows):**

```powershell
cd Python\mafibot
.\build.ps1
# → dist\mafibot.exe
```

`build.ps1` creates `.venv-build`, installs deps + webbot, installs Chromium into the bundle path, and runs `pyinstaller mafibot.spec`. Rebuild only the exe after the venv exists: `.\build.ps1 -SkipVenvSetup`. Skip re-downloading Chromium: `.\build.ps1 -SkipVenvSetup -SkipPlaywrightInstall`.

Manual equivalent (no script): activate `.venv-build`, `pip install -r requirements.txt pyinstaller msvc-runtime`, set `$env:PLAYWRIGHT_BROWSERS_PATH = "0"`, run `playwright install chromium`, then `pyinstaller mafibot.spec`. (`msvc-runtime` bundles VC++ DLLs that Playwright’s `greenlet` dependency needs inside the frozen `.exe`.)

**Do not use `pybin` for this project** — it does not apply the checked-in `mafibot.spec` (webbot path, UI static/profiles, Playwright browser bundle, runtime hook). Use `build.ps1` or `pyinstaller mafibot.spec` directly.

Config, login cookies, and custom profiles still live under `%APPDATA%\mafibot` (same as the Python install). The packaged build uses bundled Chromium by default; system Chrome is not required on the target PC.

**Smoke tests after build:**

```powershell
.\dist\mafibot.exe version
.\dist\mafibot.exe check
.\dist\mafibot.exe login
.\dist\mafibot.exe ui
.\dist\mafibot.exe run --accept-tos --dry-run -v
```

`codegen` is disabled in the `.exe` (use a dev Python install for Playwright codegen). GitHub Actions can produce the same artifact on demand — see `.github/workflows/mafibot-exe.yml`.

## Quick start

```bash
# 1. Log in once (session stored under %APPDATA%/mafibot/profile on Windows)
python mafibot.py login

# 2. Map real ?side= URLs and save HTML snapshots (while logged in)
python mafibot.py discover --accept-tos

# 3. Run autopilot (headed browser by default)
python mafibot.py run --accept-tos --profile ranker --max-minutes 120

# Dry-run: log decisions only, no clicks
python mafibot.py run --accept-tos --dry-run -v

# Web dashboard (localhost only)
python mafibot.py ui
# → http://127.0.0.1:8766/  (use --port to change)
```

After the first `discover`, page slugs are written to your config dir as `pages.json`. Refine button labels in `mafibot/selectors.py` if discovery misses controls.

## Web UI

```bash
python mafibot.py ui              # http://127.0.0.1:8766
python mafibot.py ui --port 8767
```

The dashboard has three tabs:

- **Run** — pick profile, start/stop autopilot, live status and log (WebSocket)
- **Config** — edit and save bot profile JSON under your config `profiles/` dir
- **User** — account info, `.env` credentials, sign-in browser, dashboard token

**Security:** the server binds to `127.0.0.1` by default. Do not expose port 8766 on your LAN or the public internet without authentication; anyone who can reach it can start the bot and read/write credentials on disk.

## CLI commands

| Command | Description |
|---------|-------------|
| `login` | Open the site; wait for manual (or `.env`) login; save cookies in the mafibot profile |
| `discover --accept-tos` | Collect `?side=` links, update `pages.json`, save HTML + screenshots per page |
| `run --accept-tos` | Autopilot loop for one session (`Ctrl+C` to stop) |
| `codegen` | Launch Playwright codegen on mafiaspillet.no |
| `install-webbot-scenario` | Copy `mafia_autopilot.py` into webbot’s scenarios folder |
| `ui` | Local web dashboard on `127.0.0.1:8766` (`--host`, `--port`) |
| `check` | Pre-flight: config dir, `pages.json`, latest discovery verification |
| `promote-fixtures` | Copy latest discovery HTML into `tests/fixtures/discovered/` |
| `version` | Print version and config directory |

Common `run` options:

- `--profile` / `-p` — `ranker`, `okonom`, or `angriper` (see [Profiles](#profiles))
- `--max-minutes` — session length (default 120)
- `--dry-run` — brain picks actions but does not click
- `--headless` — run without a visible window (not recommended)
- `-v` / `--verbose` — debug logging
- `--skip-preflight` — skip static pre-flight checks
- `--require-verification` — require passing `verify-pages` on latest discovery

## Config and data locations

| Path | Purpose |
|------|---------|
| `%APPDATA%/mafibot/` (Windows) or `~/.config/mafibot/` | Config root |
| `.../mafibot/profile/` | Persistent Chrome profile (cookies, login) |
| `.../mafibot/pages.json` | Logical action → `?side=` mapping (from discover) |
| `.../mafibot/profiles/*.json` | User overrides for bot profiles |
| `.../mafibot/discovery/<timestamp>/` | HTML, PNG, and manifest from discover |

Bundled defaults live in `mafibot/profiles/` in this repo.

## Profiles

Three built-in play styles (JSON). Copy into your config `profiles/` folder to customize.

| Profile | Focus | Combat |
|---------|--------|--------|
| `ranker` | Missions → crime → business → ship → travel → drugs | Off |
| `early_ranker` | Auto-progress missions 1–9, market supplies, minion train | Off |
| `okonom` | Business → ship → bank → crime → drugs | Off |
| `okonom_full` | Business, ship, bank, city-income scheduler, travel rotation | Off |
| `angriper` | Crime → murder → travel | On (retaliate-only default) |
| `wartime_angriper` | Retaliate murder, war/kidnap webhooks | On |
| `minion_ranker` | Minions + crime + business | Off |

Each profile sets economy action order, social check interval, health thresholds, play window (default 08:00–23:00), idle breaks, and cooldown jitter (15–90 s).

New profile fields (optional): `missions_mode` (`start_only` / `auto_progress`), `minions_action` (`train` / `collect_reports_only`), `murder_mode` (`static_targets` / `report_stream` / `retaliate_only`), `organized_crime_difficulty`, `travel_rotate_cities`, `scheduler_happy_hour_boost`, `assist_webhook_on_war` / `assist_webhook_on_kidnap`.

### Crime sections (Kriminalitet)

Profiles use `crime_actions` with section ids matching the in-game UI:

| Id | Section |
|----|---------|
| `enkel` | Enkel kriminalitet (Utfør) |
| `tung` | Tung kriminalitet (Utfør) |
| `stjel` | Stjel |

Optional per-section choice lists: `crime_enkel_choices`, `crime_tung_choices`, `crime_steal_items` (empty = any option in that section). Legacy `crime_kind` / `crime_perform_type` are migrated on load and stripped when saved.

Set `scheduler` to `soonest_ready` to prefer runnable actions by cooldown timing (still respects `economy_order` as a tiebreaker).

### Dashboard security and alerts

- Set `MAFIBOT_UI_TOKEN` in the environment before `mafibot.py ui`; the User tab can store the same token for API/WebSocket calls (`X-Mafibot-Token`).
- Non-loopback bind requires `mafibot.py ui --insecure-bind`.
- Optional `stop_webhook_url` in profile JSON posts to a Discord-compatible webhook when the session stops (captcha, ban, logout).
- Last session stats are written to `last_session.json` under your config dir and shown in the Run tab.
- The Run tab log is appended to `logs/mafibot.log` (rotating, ~2 MB × 5 files) and reloaded when you open the UI.

## How it works

```text
Session check → parse DOM (GameState) → brain picks action → human-like click/navigate → wait (jitter / cooldown)
```

- **Navigation** — `ms.php` tabs first (e.g. Kriminalitet, Flyplass); sidebar for bedrifter/rederi; legacy `?side=` as fallback.
- **Hotel-first (default)** — **Book** before each action, **leave** only for crime/travel/drugs/murder/bank, **book again** within **`max_seconds_before_book_hotel`** (default **2 s**) after each action. Long waits happen only *between* cycles. See [WHATIF.md](WHATIF.md).
- **Human pacing** — `human_click_paced()` enforces minimum gaps between clicks, reading pauses before each click, optional “thinking” delays, and disabled buttons are skipped.
- **Idle micro-activity** — Long cycle waits and AFK breaks use chunked sleeps with occasional mouse drift and scroll (not a frozen browser).
- **Mouse continuity** — Clicks move from the last cursor position via Bezier paths instead of teleporting from a random point.
- **Human selects** — Travel/drugs destinations open `<select>` elements with paced clicks when possible (fallback to `select_option` if needed).

### How wait times are chosen

All delays are **random floats in seconds** (via `random_wait_seconds()` / webbot’s `random.uniform` / `triangular` sampling)—never rounded to whole seconds before sleeping.

| When | How long |
|------|-----------|
| Between clicks | `min_seconds_between_clicks` (profile, e.g. 3.0) + extra **0.15–0.9** s |
| Before each click | **1.2–3.8** s reading + webbot Bezier move |
| After tab change | `min_seconds_after_tab_change` + **0–4** s + navigation pause |
| After one action (brain loop) | `cooldown_jitter` (**triangular**, e.g. 35–130 s) + `post_action_wait` (**8–25** s default) |
| Nothing to do | `cooldown_jitter` + `nothing_todo_wait` (**45–180** s default) |
| AFK idle break | **5.0–15.0** minutes as float × 60, with drift/scroll between chunks |
| Between cycles (idle) | Same chunked activity during cooldown waits |
| Distraction pause | Every ~8–15 actions, extra **10–45** s idle activity |
| Inside webbot | `human_delay` / `reading_pause` use triangular or uniform **float** samples |

Tune in profile JSON (`cooldown_jitter_min_sec`, `post_action_wait_min_sec`, etc.—decimals allowed, e.g. `35.5`).
- **Safety** — Stops on captcha, ban text, or logout; low health can trigger hotel; jail pauses the loop.
- **Social** — Messages and family are rate-limited to reduce spam-rule risk.
- **Combat** — Murder only when enabled in profile and aggression gates pass.

Automation uses [webbot/human.py](../webbot/webbot/human.py) (`human_click`, `reading_pause`, `idle_mouse_drift`, etc.), not raw `page.click()`.

## Webbot integration

Run from the webbot dashboard or CLI after installing the scenario:

```bash
python mafibot.py install-webbot-scenario
cd ../webbot
python webbot.py run mafia_autopilot
```

Complete `mafibot.py login` first. The installed scenario embeds the path to this repo; if you move the clone, run `install-webbot-scenario` again.

Set `MAFIBOT_PROFILE=okonom` in the environment to override the default profile when using webbot.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

## Discovery output

`discover` writes a timestamped folder under `discovery/` with `discovery_report.md`. Use `--compare-last` to print HTML diffs against the previous run:

- `links.json` — all unique `?side=` links found on the current page
- `<page>.html` / `<page>.png` — snapshots per logical page (crime, travel, messages, …)
- `manifest.json` — summary for tuning parsers

Use these files to update `mafibot/selectors.py` and re-run tests.

## Tests

```bash
cd Python/mafibot
pip install pytest pytest-asyncio
python -m pytest tests/ -q
```

Parser tests use HTML fixtures only (no live site).

## Project layout

```text
Python/mafibot/
  mafibot.py              # CLI entrypoint
  mafibot/
    auth.py               # Login / session
    brain.py              # Autopilot scheduler
    config.py             # Paths and BotProfile
    discover.py           # Discovery pass
    human_policy.py       # Delays and jitter
    navigation.py         # ?side= and link navigation
    selectors.py          # Norwegian labels and regex
    state.py              # GameState parser
    session.py            # Browser wrapper
    actions/              # crime, travel, economy, social, combat
    profiles/             # ranker, okonom, angriper
  webbot_scenario/        # Template for webbot
  tests/
```

## What this does not do

- No direct API access (`api_test.php`, etc.)
- No proxy / IP rotation
- No multi-account orchestration
- No 24/7 minimum-delay farming

## Related

- [WHATIF.md](WHATIF.md) — example session timeline, hotel behavior, rough timings
- [Webbot README](../webbot/README.md) — underlying automation library
- [Mafiaspillet help](http://hjelp.mafiaspillet.no/) — game mechanics reference
