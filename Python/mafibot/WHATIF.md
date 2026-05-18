# What-if: hotel-first mafibot run

Default strategy: **stay in hotel as much as possible**. Book/check in before and after every gameplay action. Only **leave briefly** for actions that are blocked in-hotel (crime, travel, drugs, murder, bank).

Configured in profile JSON:

```json
"stay_in_hotel": true,
"book_hotel_before_action": true,
"book_hotel_after_every_action": true,
"book_hotel_when_idle": true
```

## Per-action cycle (ranker profile)

```text
book hotel (if not already in)
  → leave hotel (only if this action needs it, e.g. crime)
  → do ONE action (crime / business / ship / …)
  → wait ≤ 2 s (random float, default max_seconds_before_book_hotel)
  → book hotel again (quick path: shorter pauses)
  → wait ~43–155 s (random floats) — long human idle between cycles only here
  → repeat
```

**Out of hotel:** only the short window while leaving + performing a blocked action (often **~1–3 minutes** per crime/travel cycle), then back in hotel for the wait until the next action.

**In hotel:** most of the session—between actions, during AFK idle breaks, and when doing sidebar actions (Mine bedrifter, Mitt rederi) that work from the hotel UI.

## Example timeline (start in hotel, Kabul, income + ship ready)

| Time | What happens |
|------|----------------|
| T+0 | Session start → **book hotel** (already in → skip) |
| T+0–2 min | Pick **business** (okonom: business before crime; ranker: crime first if cooldown clear) |
| | If **crime**: book → **leave** → Utfør/Stjel → **book** |
| | If **business**: book → hent inntekt (no leave) → **book** |
| T+2–4 min | Wait ~60–90 s (still in hotel) |
| T+4–7 min | **ship** (sidebar, usually no leave) → **book** → wait |
| T+7+ | **travel** / **drugs** / **bank** each: leave if needed → act → book → wait |
| Every ~50 min | messages / family (usually no leave) → book |
| T+120 | Session end → **book hotel** once more |

## Actions and hotel

| Action | Leave hotel first? | Book after? |
|--------|-------------------|-------------|
| crime | Yes | Yes |
| travel | Yes | Yes |
| drugs | Yes | Yes |
| murder | Yes | Yes |
| bank | Yes | Yes |
| business / ship | No (sidebar) | Yes |
| messages / family | No | Yes |

## Rough timing

| Metric | Ballpark |
|--------|----------|
| % of session **in hotel** | **~85–95%** (most waits + sidebar actions) |
| **Out of hotel** per crime/travel cycle | **~1–3 min** |
| Actions per hour | ~12–20 (extra book/leave steps + waits) |

## Disable hotel-first

In your profile JSON:

```json
"stay_in_hotel": false
```

That restores the old behavior (leave and grind outside hotel).

## Gaps

- Booking UI selectors may need tuning via `discover` (Sjekk inn / Hotell tab).
- Re-booking when already in hotel is a no-op (parser sees *Forlat hotell for å utføre*).
- Game costs / room availability are not modeled.

See [README.md](README.md) for install and CLI.
