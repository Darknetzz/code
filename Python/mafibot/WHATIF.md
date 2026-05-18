# What-if: a typical mafibot run

This describes behavior based on the **current code** (default `ranker` profile, `--max-minutes 120`) and a starting state like: logged in on `ms.php`, **in hotel** (Kabul), “Inntekt kan hentes!”, “Skip står i havn!”, 100% health.

## How long out of hotel?

**The bot does not schedule “go back to hotel after X minutes.”**

| Event | Hotel behavior |
|--------|----------------|
| Start in hotel with *“Forlat hotell for å utføre”* | First real action is **`leave_hotel`** (clicks leave/checkout if it finds it). |
| After a successful leave | You stay **out of hotel** for the rest of the session while the bot grinds—**up to ~120 minutes** by default. |
| Bot books hotel again | Only if **`HotelAction`** runs: health **< 40%** or parser thinks you’re in hospital—not because time passed. |
| 100% health | Realistically **~full run length out of hotel** (often **1–2 hours**), unless you drop below 40% HP or stop the bot. |

So: **not “out for 5 minutes then back in”**—it’s **“leave once, then play outside until low HP or you stop.”** The game’s own **“Sjekk ut (82 t …)”** timer is separate; the bot doesn’t model “stay in hotel for 82 hours.”

If `leave_hotel` **fails** (wrong button), you can get stuck: crime stays blocked, brain keeps trying `leave_hotel` / waiting—still **in** hotel until that click works.

---

## What-if timeline (example session)

Assume: logged in on `ms.php`, in hotel, ranker profile, play window OK (08:00–23:00).

### T+0:00 — Session starts

- Opens / stays on `ms.php`.
- Parses: in hotel, crimes blocked, maybe “Inntekt kan hentes!”, “Skip står i havn!”.

### T+0:00–1:30 — Cycle 1: `leave_hotel` (priority)

- Go to **Kriminalitet** tab (slow tab click + ~4–8 s reading).
- Try **Forlat hotell** / **Sjekk ut** (only if button enabled; ~3+ s between clicks).
- Maybe try Hotell tab / sidebar if first attempt fails.
- **~30–90 s** of UI time, then **~2–5 s** “between actions” pause.

### T+1:30–3:30 — Wait

- Sleep **`cooldown_jitter` + `post_action_wait`** ≈ **43–155 s** typical (ranker: 35–130 + 8–25), often **~60–90 s**.

### T+3:30–6:00 — Cycle 2: `crime` (if leave worked)

- If page no longer says *“Forlat hotell for å utføre”*: open **Kriminalitet**, read page, click **Utfør!** / **Stjel!** if enabled.
- If still blocked: `crime` skipped next cycle; **`leave_hotel`** again.

### T+6:00–8:00 — Wait

~60–90 s again.

### T+8:00–11:00 — Cycle 3: `business` (if “Inntekt kan hentes!”)

- Sidebar **Mine bedrifter** → **hent** / inntekt button.
- Wait again.

### T+11:00–14:00 — Cycle 4: `ship` (if “Skip står i havn!”)

- **Mitt rederi** → send/avreise-type button.
- Wait again.

### T+14:00–17:00 — Cycle 5: `travel`

- Tab **Flyplass** if “ready” / no cooldown text.
- Wait again.

Then **`drugs`** (Narkotika link), **`bank`** (if in profile order and page matches)—each with the same pattern: **~1–3 min acting + ~1–2.5 min waiting**.

### Every ~50 min (ranker): `messages` / `family`

- If social interval elapsed or unread messages; rate-limited replies.

### ~10% of loops: AFK idle

- **5–15 minutes** (float minutes) doing nothing—browser open, no clicks.

### If nothing is ready (all on cooldown, in jail, etc.)

- Wait **`cooldown_jitter` + `nothing_todo_wait`** ≈ **80–310 s** (35–130 + 45–180), log *“waiting … (nothing to do)”*.

### T+120:00 — Session ends

- Stops after `max_session_minutes` (unless you Ctrl+C).
- Account likely **still out of hotel** unless HP dropped and bot booked hotel.

---

## One loop in plain terms

```text
Parse page → pick ONE action → human clicks (slow) → read page → wait ~1–2.5 min → repeat
```

Priority when you’re in hotel:

```text
leave_hotel → (wait) → crime → business → ship → travel → drugs → bank → social…
```

**Not in one burst:** one action per loop, then a long random wait—by design so it doesn’t look like machine-gun play.

---

## Rough counts (ranker, 2 h, everything works)

| Metric | Ballpark |
|--------|----------|
| Actions per hour | ~15–25 (depends on waits + cooldowns) |
| Time **out of hotel** after successful leave | **~95–120 min** of session (almost all of it at 100% HP) |
| Time **in hotel** during run | Only **start** (until leave succeeds) + maybe **end** if HP < 40% |

---

## Gaps vs real Mafiaspillet (worth knowing)

1. **No auto check-in** after grinding—you may stay out of hotel a long time (more exposure in-game).
2. **Doesn’t read the 82 h timer**—only text like *“Forlat hotell for å utføre”*.
3. **Won’t re-enter hotel** for “safe sleep” unless low HP logic fires.
4. **`--dry-run`** only logs choices; no clicks, no hotel leave.

---

## Not implemented (possible future rule)

**“Leave hotel → grind 20 min → book hotel again”** is not in the brain today. That would need an explicit profile option and `HotelAction` / timer logic.

See also [README.md](README.md) for install, CLI, and wait-time tuning.
