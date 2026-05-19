"""One-off patch for config panel HTML — run from repo root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "mafibot" / "static" / "index.html"

text = INDEX.read_text(encoding="utf-8")

# 1) Insert presets/summary/validation after profile toolbar
old1 = (
    "          </motion.div>\n"
    "        </motion.div>\n"
    "        <motion.div class=\"grid-2\">"
)
# fix - use real closing tags
old1 = (
    "          </div>\n"
    "        </div>\n"
    "        <div class=\"grid-2\">"
)
new1 = (
    "          </div>\n"
    "        </div>\n"
    "        <div id=\"cfg-validation-banner\" class=\"config-validation hidden\" role=\"alert\"></motion.div>\n"
    "        <pre id=\"cfg-summary\" class=\"config-summary muted\" aria-live=\"polite\">—</pre>\n"
    "        <div class=\"btn-row preset-row\">\n"
    "          <span class=\"field-label\">Load preset</span>\n"
    "          <button type=\"button\" data-preset=\"early_ranker\">Early game</button>\n"
    "          <button type=\"button\" data-preset=\"ranker\">Rank grind</button>\n"
    "          <button type=\"button\" data-preset=\"okonom_full\">Economy</button>\n"
    "          <button type=\"button\" data-preset=\"wartime_angriper\">War assist</button>\n"
    "        </motion.div>\n"
    "        <details class=\"config-section\" open>\n"
    "          <summary>Profile &amp; scheduler</summary>\n"
    "        <div class=\"grid-2\">"
)
# Still has motion.div typos in new1 - fix manually below

new1 = """          </div>
        </div>
        <div id="cfg-validation-banner" class="config-validation hidden" role="alert"></div>
        <pre id="cfg-summary" class="config-summary muted" aria-live="polite">—</pre>
        <div class="btn-row preset-row">
          <span class="field-label">Load preset</span>
          <button type="button" data-preset="early_ranker">Early game</button>
          <button type="button" data-preset="ranker">Rank grind</button>
          <button type="button" data-preset="okonom_full">Economy</button>
          <button type="button" data-preset="wartime_angriper">War assist</button>
        </div>
        <details class="config-section" open>
          <summary>Profile &amp; scheduler</summary>
        <motion.div class="grid-2">"""

new1 = new1.replace("<motion.div", "<div").replace("</motion.div>", "</div>")

if old1 not in text:
    raise SystemExit(f"anchor1 not found")
text = text.replace(old1, new1, 1)

# 2) After scheduler select, add aggression + scheduler boosts
old2 = """            <select id="cfg-scheduler">
              <option value="priority">priority (economy order)</option>
              <option value="soonest_ready">soonest_ready (cooldown-aware)</option>
            </select>
          </div>
        </div>
        <div>
          <label for="cfg-stop-webhook">Stop webhook URL (optional)</label>"""

new2 = """            <select id="cfg-scheduler">
              <option value="priority">priority (economy order)</option>
              <option value="soonest_ready">soonest_ready (cooldown-aware)</option>
            </select>
          </div>
        </div>
        <div>
          <label for="cfg-aggression">Aggression (0–1, murder gating)</label>
          <input type="range" id="cfg-aggression" min="0" max="1" step="0.05" value="0.3" />
          <span id="cfg-aggression-value" class="muted">0.30</span>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="cfg-scheduler-happy-hour" checked />
          <label for="cfg-scheduler-happy-hour">Boost actions during Happy Hour</label>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="cfg-scheduler-city-income" checked />
          <label for="cfg-scheduler-city-income">Boost business after city income windows</label>
        </div>
        </details>
        <details class="config-section">
          <summary>Session</summary>
        <div class="grid-2">
          <div>
            <label for="cfg-max-session-minutes">Max session (minutes)</label>
            <input type="number" id="cfg-max-session-minutes" min="1" value="120" />
          </div>
          <div>
            <label for="cfg-play-start">Play window start (hour 0–23)</label>
            <input type="number" id="cfg-play-start" min="0" max="23" value="8" />
          </div>
          <div>
            <label for="cfg-play-end">Play window end (hour 0–23)</label>
            <input type="number" id="cfg-play-end" min="0" max="23" value="23" />
          </div>
        </div>
        <div class="grid-2">
          <motion.div>
            <label for="cfg-idle-chance">Idle break chance (0–1)</label>
            <input type="number" id="cfg-idle-chance" min="0" max="1" step="0.05" value="0.1" />
          </div>
          <div>
            <label for="cfg-idle-min">Idle break min (minutes)</label>
            <input type="number" id="cfg-idle-min" min="1" step="0.5" value="5" />
          </div>
          <div>
            <label for="cfg-idle-max">Idle break max (minutes)</label>
            <input type="number" id="cfg-idle-max" min="1" step="0.5" value="15" />
          </div>
        </div>
        </details>
        <details class="config-section" open>
          <summary>Hotel &amp; safety</summary>
        <div>
          <label for="cfg-stop-webhook">Stop webhook URL (optional)</label>"""

new2 = new2.replace("<motion.div>", "<div>").replace("</motion.div>", "")

if old2 not in text:
    raise SystemExit("anchor2 not found")
text = text.replace(old2, new2, 1)

# 3) After min-health, close hotel section and add pacing before action list
old3 = """          <div>
            <label for="cfg-min-health">Min health %</label>
            <input type="number" id="cfg-min-health" min="1" max="100" value="35" />
          </div>
        </div>
        <div class="grid-2">
          <div>
            <label for="cfg-jitter-min">Cooldown jitter min (sec)</label>"""

new3 = """          <div>
            <label for="cfg-min-health">Min health %</label>
            <input type="number" id="cfg-min-health" min="1" max="100" value="35" />
          </div>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="cfg-pause-restricted" checked />
          <label for="cfg-pause-restricted">Pause when feriemodus, kidnapped, or startbeskyttelse</label>
        </div>
        </details>
        <details class="config-section" open>
          <summary>Human pacing</summary>
        <div class="grid-2">
          <div>
            <label for="cfg-jitter-min">Cooldown jitter min (sec)</label>"""

if old3 not in text:
    raise SystemExit("anchor3 not found")
text = text.replace(old3, new3, 1)

# 4) After tab-wait, close pacing and open actions section
old4 = """            <label for="cfg-tab-wait">Min seconds after tab change</label>
            <input type="number" id="cfg-tab-wait" step="0.1" value="3.5" />
          </div>
        </div>
        <div class="action-list-section">"""

new4 = """            <label for="cfg-tab-wait">Min seconds after tab change</label>
            <input type="number" id="cfg-tab-wait" step="0.1" value="3.5" />
          </div>
        </div>
        <div class="grid-2">
          <div>
            <label for="cfg-post-wait-min">Post-action wait min (sec)</label>
            <input type="number" id="cfg-post-wait-min" step="0.1" value="8" />
          </div>
          <div>
            <label for="cfg-post-wait-max">Post-action wait max (sec)</label>
            <input type="number" id="cfg-post-wait-max" step="0.1" value="25" />
          </div>
          <div>
            <label for="cfg-nothing-wait-min">Nothing-to-do wait min (sec)</label>
            <input type="number" id="cfg-nothing-wait-min" step="0.1" value="45" />
          </div>
          <div>
            <label for="cfg-nothing-wait-max">Nothing-to-do wait max (sec)</label>
            <input type="number" id="cfg-nothing-wait-max" step="0.1" value="180" />
          </div>
        </div>
        </details>
        <details class="config-section" open>
          <summary>Actions</summary>
        <div class="action-list-section">"""

if old4 not in text:
    raise SystemExit("anchor4 not found")
text = text.replace(old4, new4, 1)

# 5) Notifications + advanced before cfg-dir-hint
old5 = """        </div>
        <p class="health-meta" id="cfg-dir-hint"></p>
        <div class="btn-row">
          <button type="button" class="primary" id="btn-save-profile">Save profile</button>
        </div>"""

new5 = """        </details>
        <details class="config-section">
          <summary>Notifications</summary>
        <div>
          <label for="cfg-stop-webhook-notify">Stop / assist webhook URL</label>
          <input type="url" id="cfg-stop-webhook-notify" class="form-input" placeholder="https://discord.com/api/webhooks/..." />
          <p class="tos-note">Same as stop webhook above; edit either field. Assist alerts are notify-only (no auto-play).</p>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="cfg-assist-war" />
          <label for="cfg-assist-war">Webhook on familiekrig (assist)</label>
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="cfg-assist-kidnap" />
          <label for="cfg-assist-kidnap">Webhook when kidnapped (assist)</label>
        </div>
        </details>
        <details class="config-section">
          <summary>Advanced (JSON)</summary>
        <div class="btn-row">
          <button type="button" id="btn-export-profile">Export JSON</button>
          <button type="button" id="btn-import-profile">Import JSON</button>
        </div>
        <textarea id="cfg-json-preview" rows="8" class="json-preview" readonly placeholder="Export to see JSON"></textarea>
        </details>
        <p class="health-meta" id="cfg-dir-hint"></p>
        <div class="btn-row">
          <button type="button" class="primary" id="btn-save-profile">Save profile</button>
        </motion.div>"""

new5 = new5.replace("</motion.div>", "</div>")

if old5 not in text:
    raise SystemExit("anchor5 not found")
text = text.replace(old5, new5, 1)

# 6) Remove duplicate webhook at top OR sync - we moved webhook to notifications; remove first webhook block
old6 = """        <div>
          <label for="cfg-stop-webhook">Stop webhook URL (optional)</label>
          <input
            type="url"
            id="cfg-stop-webhook"
            class="form-input"
            placeholder="https://discord.com/api/webhooks/..."
          />
        </div>
        <div class="checkbox-row">
          <input type="checkbox" id="cfg-stay-in-hotel" checked />"""

new6 = """        <div class="checkbox-row">
          <input type="checkbox" id="cfg-stay-in-hotel" checked />"""

if old6 in text:
    text = text.replace(old6, new6, 1)

# 7) Minions panel - remove enable checkbox
text = text.replace(
    """          <details id="action-options-minions" class="action-options-panel hidden">
            <summary>Minions</summary>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-minions-enabled" />
              <label for="cfg-minions-enabled">Enable Undersåtter action</label>
            </div>
            <div>
              <label for="cfg-minions-action">Action</label>""",
    """          <details id="action-options-minions" class="action-options-panel hidden">
            <summary>Minions</summary>
            <p class="tos-note">Enable <strong>Minions</strong> in the action list above.</p>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-minions-train-when-ready" checked />
              <label for="cfg-minions-train-when-ready">Train only when ready</label>
            </div>
            <div>
              <label for="cfg-minions-action">Action</label>""",
    1,
)

# 8) Missions panel
text = text.replace(
    """          <details id="action-options-missions" class="action-options-panel hidden">
            <summary>Missions</summary>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-missions-enabled" />
              <label for="cfg-missions-enabled">Enable Oppdrag auto-start</label>
            </div>
            <div>
              <label for="cfg-missions-mode">Mode</label>""",
    """          <details id="action-options-missions" class="action-options-panel hidden">
            <summary>Missions</summary>
            <p class="tos-note">Enable <strong>Missions</strong> in the action list. Auto progress delegates to crime/market/minions by mission hint.</p>
            <motion.div class="checkbox-row">
              <input type="checkbox" id="cfg-missions-auto-start" checked />
              <label for="cfg-missions-auto-start">Auto-start new missions</label>
            </div>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-missions-prioritize" checked />
              <label for="cfg-missions-prioritize">Prioritize mission goals in scheduler</label>
            </div>
            <div>
              <label for="cfg-missions-mode">Mode</label>""",
    1,
)
text = text.replace("<motion.div class=\"checkbox-row\">", "<div class=\"checkbox-row\">").replace(
    "</motion.div>\n            <div class=\"checkbox-row\">", "</div>\n            <div class=\"checkbox-row\">"
)

# 9) Org crime
text = text.replace(
    """          <details id="action-options-organized-crime" class="action-options-panel hidden">
            <summary>Organized crime</summary>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-org-crime-enabled" />
              <label for="cfg-org-crime-enabled">Enable Organisert Kriminalitet</label>
            </div>
            <div>
              <label for="cfg-org-crime-difficulty">Difficulty</label>""",
    """          <details id="action-options-organized-crime" class="action-options-panel hidden">
            <summary>Organized crime</summary>
            <p class="tos-note">Enable <strong>Organized crime</strong> in the action list.</p>
            <div>
              <label for="cfg-org-crime-min-health">Min health % (optional)</label>
              <input type="number" id="cfg-org-crime-min-health" min="0" max="100" placeholder="profile default" />
            </div>
            <div>
              <label for="cfg-org-crime-difficulty">Difficulty</label>""",
    1,
)

# 10) Market
text = text.replace(
    """          <details id="action-options-market" class="action-options-panel hidden">
            <summary>Market</summary>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-market-enabled" />
              <label for="cfg-market-enabled">Enable Marked trading</label>
            </div>
            <div>
              <label for="cfg-market-mode">Mode</label>
              <select id="cfg-market-mode">
                <option value="none">Off</option>
                <option value="sell_junk">Sell junk</option>
                <option value="buy_supplies">Buy supplies</option>
              </select>
            </div>
          </details>""",
    """          <details id="action-options-market" class="action-options-panel hidden">
            <summary>Market</summary>
            <p class="tos-note">Enable <strong>Market</strong> in the action list.</p>
            <div>
              <label for="cfg-market-mode">Mode</label>
              <select id="cfg-market-mode">
                <option value="none">Off</option>
                <option value="sell_junk">Sell junk</option>
                <option value="buy_supplies">Buy supplies</option>
              </select>
            </div>
            <div>
              <label for="cfg-market-max-hour">Max trades per hour</label>
              <input type="number" id="cfg-market-max-hour" min="0" max="30" value="4" />
            </div>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-market-mission-buy" checked />
              <label for="cfg-market-mission-buy">Buy supplies when mission needs weapon/car</label>
            </div>
            <div>
              <span class="field-label">Buy items</span>
              <motion.div id="cfg-market-buy-items" class="city-checkbox-list"></div>
            </div>
            <div>
              <span class="field-label">Sell items</span>
              <div id="cfg-market-sell-items" class="city-checkbox-list"></div>
            </div>
          </details>""",
    1,
)
text = text.replace("<motion.div id=\"cfg-market-buy-items\"", "<div id=\"cfg-market-buy-items\"")

# 11) Travel rotation
text = text.replace(
    """          <details id="action-options-travel" class="action-options-panel hidden">
            <summary>Travel</summary>
            <div>
              <span class="field-label" id="cfg-travel-label">Preferred destinations</span>
              <div id="cfg-travel-destinations-list" class="city-checkbox-list" role="group" aria-labelledby="cfg-travel-label"></div>
            </div>
            <p class="tos-note">None checked = first available flight. Checked cities are tried in map order.</p>
          </details>""",
    """          <details id="action-options-travel" class="action-options-panel hidden">
            <summary>Travel</summary>
            <div>
              <span class="field-label" id="cfg-travel-label">Preferred destinations</span>
              <div id="cfg-travel-destinations-list" class="city-checkbox-list" role="group" aria-labelledby="cfg-travel-label"></div>
            </div>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-travel-rotate" />
              <label for="cfg-travel-rotate">Rotate cities (anti-surveillance)</label>
            </div>
            <div>
              <label for="cfg-travel-rotate-min">Min minutes between rotations</label>
              <input type="number" id="cfg-travel-rotate-min" min="5" value="45" />
            </div>
            <div>
              <span class="field-label" id="cfg-travel-rotate-label">Rotation city pool (empty = all cities)</span>
              <div id="cfg-travel-rotate-pool" class="city-checkbox-list" role="group"></div>
            </div>
            <p class="tos-note">None checked for destinations = first available flight. Rotation ignored when drugs needs a specific city.</p>
          </details>""",
    1,
)

# 12) Murder extras
text = text.replace(
    """            <motion.div id="cfg-murder-targets-wrap">
              <label for="cfg-murder-targets">Target usernames (one per line)</label>
              <textarea id="cfg-murder-targets" rows="3" placeholder="rival_player"></textarea>
            </div>""",
    "",
    1,
)
if "cfg-murder-targets-wrap" not in text:
    text = text.replace(
        """            <div>
              <label for="cfg-murder-targets">Target usernames (one per line)</label>
              <textarea id="cfg-murder-targets" rows="3" placeholder="rival_player"></textarea>
            </div>""",
        """            <div id="cfg-murder-targets-wrap">
              <label for="cfg-murder-targets">Target usernames (one per line)</label>
              <textarea id="cfg-murder-targets" rows="3" placeholder="rival_player"></textarea>
            </div>
            <div class="checkbox-row">
              <input type="checkbox" id="cfg-murder-travel" checked />
              <label for="cfg-murder-travel">Travel to target city before shoot</label>
            </div>
            <div>
              <label for="cfg-murder-attack-margin">Min attack margin vs target protection</label>
              <input type="number" id="cfg-murder-attack-margin" min="0" value="0" />
            </div>""",
        1,
    )

# 13) Run tab max minutes hint
text = text.replace(
    """            <label for="run-max-minutes">Max session (minutes)</label>
            <input type="number" id="run-max-minutes" min="1" value="120" />""",
    """            <label for="run-max-minutes">Max session (minutes)</label>
            <input type="number" id="run-max-minutes" min="1" placeholder="profile default" />
            <p class="tos-note" id="run-max-minutes-hint">Leave empty to use profile default.</p>""",
    1,
)

INDEX.write_text(text, encoding="utf-8")
print("patched", INDEX)
