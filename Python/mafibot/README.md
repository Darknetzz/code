# Mafibot

Human-like browser autopilot for [Mafiaspillet.no](https://mafiaspillet.no/), built on top of [webbot](../webbot/) (Playwright, curved mouse paths, variable delays, persistent Chrome profile).

The bot reads game state from the page DOM, chooses the next action (crime, travel, economy, messages, combat), and executes it through the same human-like input layer as webbot—not via the game API.

The live game runs at **`https://mafiaspillet.no/ms.php`** with Norwegian **tabs** (Kriminalitet, Flyplass, …) and a sidebar (Mine bedrifter, Mitt rederi). Navigation uses slow, human-paced clicks—typically **3+ seconds between clicks**, longer pauses after tab changes, and **30–130 s** jitter between action cycles.

## Terms of service

[Mafiaspillet section 7](https://mafiaspillet.no/?side=betingelser) forbids scripts, browser add-ons, and automation that performs or speeds up in-game actions (including automatic mouse movement). Using this tool can lead to **account bans**, loss of progress, or IP blocks.

Commands that start automation require `--accept-tos`. This project is for **personal / educational** use at your own risk.

## Requirements

- Python 3.10+
- Google Chrome (recommended; Playwright uses the `chrome` channel)
- Sibling package [Python/webbot](../webbot/) in this repo (imported automatically when you run `mafibot.py` from `Python/mafibot/`)

## Install

```bash
cd Python/mafibot
pip install -r requirements.txt
python -m playwright install chromium
```

Optional credentials (auto-fill login): copy `.env.example` to `.env` and set `MAFIA_USER` / `MAFIA_PASS`. A saved session from `login` is usually enough; do not commit `.env`.

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
```

After the first `discover`, page slugs are written to your config dir as `pages.json`. Refine button labels in `mafibot/selectors.py` if discovery misses controls.

## CLI commands

| Command | Description |
|---------|-------------|
| `login` | Open the site; wait for manual (or `.env`) login; save cookies in the mafibot profile |
| `discover --accept-tos` | Collect `?side=` links, update `pages.json`, save HTML + screenshots per page |
| `run --accept-tos` | Autopilot loop for one session (`Ctrl+C` to stop) |
| `codegen` | Launch Playwright codegen on mafiaspillet.no |
| `install-webbot-scenario` | Copy `mafia_autopilot.py` into webbot’s scenarios folder |
| `version` | Print version and config directory |

Common `run` options:

- `--profile` / `-p` — `ranker`, `okonom`, or `angriper` (see [Profiles](#profiles))
- `--max-minutes` — session length (default 120)
- `--dry-run` — brain picks actions but does not click
- `--headless` — run without a visible window (not recommended)
- `-v` / `--verbose` — debug logging

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
| `ranker` | Crime → travel → work → ship → drugs | Off |
| `okonom` | Work → bank → crime → ship | Off |
| `angriper` | Crime → murder → travel | On (high aggression) |

Each profile sets economy action order, social check interval, health thresholds, play window (default 08:00–23:00), idle breaks, and cooldown jitter (15–90 s).

## How it works

```text
Session check → parse DOM (GameState) → brain picks action → human-like click/navigate → wait (jitter / cooldown)
```

- **Navigation** — `ms.php` tabs first (e.g. Kriminalitet, Flyplass); sidebar for bedrifter/rederi; legacy `?side=` as fallback.
- **Hotel** — If the page shows *Forlat hotell for å utføre*, the bot runs **leave_hotel** before crime or travel.
- **Human pacing** — `human_click_paced()` enforces minimum gaps between clicks, reading pauses before each click, optional “thinking” delays, and disabled buttons are skipped.

### How wait times are chosen

All delays are **random floats in seconds** (via `random_wait_seconds()` / webbot’s `random.uniform` / `triangular` sampling)—never rounded to whole seconds before sleeping.

| When | How long |
|------|-----------|
| Between clicks | `min_seconds_between_clicks` (profile, e.g. 3.0) + extra **0.15–0.9** s |
| Before each click | **1.2–3.8** s reading + webbot Bezier move |
| After tab change | `min_seconds_after_tab_change` + **0–4** s + navigation pause |
| After one action (brain loop) | `cooldown_jitter` (**triangular**, e.g. 35–130 s) + `post_action_wait` (**8–25** s default) |
| Nothing to do | `cooldown_jitter` + `nothing_todo_wait` (**45–180** s default) |
| AFK idle break | **5.0–15.0** minutes as float × 60 (e.g. 7.38 min) |
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

## Discovery output

`discover` writes a timestamped folder under `discovery/`:

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

- [Webbot README](../webbot/README.md) — underlying automation library
- [Mafiaspillet help](http://hjelp.mafiaspillet.no/) — game mechanics reference
