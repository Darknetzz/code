"""Add 2-column layout to Config and Login panels."""
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "mafibot" / "static" / "index.html"
text = HTML.read_text(encoding="utf-8")

# --- Config ---
old = """    <section id="panel-config" class="tab-panel" role="tabpanel">
      <div class="card">
        <h2>Bot profile</h2>
        <div class="profile-toolbar">"""
new = """    <section id="panel-config" class="tab-panel" role="tabpanel">
      <motion.div class="ui-columns">
        <div class="ui-col-main">
      <div class="card">
        <h2>Bot profile</h2>
        <div class="profile-toolbar">"""
new = new.replace("<motion.div", "<div")
if old not in text:
    raise SystemExit("config open not found")
text = text.replace(old, new, 1)

sidebar = """        <div id="cfg-validation-banner" class="config-validation hidden" role="alert"></div>
        <pre id="cfg-summary" class="config-summary muted" aria-live="polite">—</pre>
        <div class="btn-row preset-row">
          <span class="field-label">Load preset</span>
          <button type="button" data-preset="early_ranker">Early game</button>
          <button type="button" data-preset="ranker">Rank grind</button>
          <button type="button" data-preset="okonom_full">Economy</button>
          <button type="button" data-preset="wartime_angriper">War assist</button>
        </div>
"""
if sidebar not in text:
    raise SystemExit("config sidebar block not found")
text = text.replace(sidebar, "", 1)

advanced = """        <details class="config-section">
          <summary>Advanced (JSON)</summary>
        <div class="btn-row">
          <button type="button" id="btn-export-profile">Export JSON</button>
          <button type="button" id="btn-import-profile">Import JSON</button>
        </div>
        <textarea id="cfg-json-preview" rows="8" class="json-preview" readonly placeholder="Export to see JSON"></textarea>
        </details>
"""
if advanced not in text:
    raise SystemExit("config advanced not found")
text = text.replace(advanced, "", 1)

aside = """        </motion.div>
        <aside class="ui-col-side" aria-label="Profile overview">
          <div class="card">
            <h2>Overview</h2>
            <div id="cfg-validation-banner" class="config-validation hidden" role="alert"></div>
            <pre id="cfg-summary" class="config-summary muted" aria-live="polite">—</pre>
            <div class="btn-row preset-row">
              <span class="field-label">Load preset</span>
              <button type="button" data-preset="early_ranker">Early game</button>
              <button type="button" data-preset="ranker">Rank grind</button>
              <button type="button" data-preset="okonom_full">Economy</button>
              <button type="button" data-preset="wartime_angriper">War assist</button>
            </div>
          </div>
          <div class="card">
            <h2>JSON</h2>
            <motion.div class="btn-row">
              <button type="button" id="btn-export-profile">Export JSON</button>
              <button type="button" id="btn-import-profile">Import JSON</button>
            </div>
            <textarea id="cfg-json-preview" rows="10" class="json-preview" readonly placeholder="Export to see JSON"></textarea>
          </div>
        </aside>
      </div>
    </section>"""
aside = aside.replace("<motion.div", "<motion.div").replace("<motion.div class", "<div class").replace("</motion.div>\n        <aside", "</motion.div>\n        <aside")
aside = """        </div>
        <aside class="ui-col-side" aria-label="Profile overview">
          <div class="card">
            <h2>Overview</h2>
            <div id="cfg-validation-banner" class="config-validation hidden" role="alert"></div>
            <pre id="cfg-summary" class="config-summary muted" aria-live="polite">—</pre>
            <div class="btn-row preset-row">
              <span class="field-label">Load preset</span>
              <button type="button" data-preset="early_ranker">Early game</button>
              <button type="button" data-preset="ranker">Rank grind</button>
              <button type="button" data-preset="okonom_full">Economy</button>
              <button type="button" data-preset="wartime_angriper">War assist</button>
            </div>
          </div>
          <div class="card">
            <h2>JSON</h2>
            <div class="btn-row">
              <button type="button" id="btn-export-profile">Export JSON</button>
              <button type="button" id="btn-import-profile">Import JSON</button>
            </div>
            <textarea id="cfg-json-preview" rows="10" class="json-preview" readonly placeholder="Export to see JSON"></textarea>
          </div>
        </aside>
      </div>
    </section>"""

close = """        <p class="health-meta" id="cfg-dir-hint"></p>
        <div class="btn-row">
          <button type="button" class="primary" id="btn-save-profile">Save profile</button>
        </div>
      </div>
    </section>"""
close_new = """        <p class="health-meta" id="cfg-dir-hint"></p>
        <div class="btn-row">
          <button type="button" class="primary" id="btn-save-profile">Save profile</button>
        </div>
      </div>
        </div>
""" + aside.split("</div>\n        <aside", 1)[1]
close_new = """        <p class="health-meta" id="cfg-dir-hint"></p>
        <motion.div class="btn-row">
          <button type="button" class="primary" id="btn-save-profile">Save profile</button>
        </div>
      </div>
        </div>
        <aside class="ui-col-side" aria-label="Profile overview">
          <div class="card">
            <h2>Overview</h2>
            <div id="cfg-validation-banner" class="config-validation hidden" role="alert"></div>
            <pre id="cfg-summary" class="config-summary muted" aria-live="polite">—</pre>
            <div class="btn-row preset-row">
              <span class="field-label">Load preset</span>
              <button type="button" data-preset="early_ranker">Early game</button>
              <button type="button" data-preset="ranker">Rank grind</button>
              <button type="button" data-preset="okonom_full">Economy</button>
              <button type="button" data-preset="wartime_angriper">War assist</button>
            </div>
          </div>
          <div class="card">
            <h2>JSON</h2>
            <div class="btn-row">
              <button type="button" id="btn-export-profile">Export JSON</button>
              <button type="button" id="btn-import-profile">Import JSON</button>
            </div>
            <textarea id="cfg-json-preview" rows="10" class="json-preview" readonly placeholder="Export to see JSON"></textarea>
          </div>
        </aside>
      </div>
    </section>"""
close_new = close_new.replace("<motion.div class", "<div class")

if close not in text:
    raise SystemExit("config close not found")
text = text.replace(close, close_new, 1)

# --- Login ---
old = """    <section id="panel-login" class="tab-panel" role="tabpanel">
      <div class="card">"""
new = """    <section id="panel-login" class="tab-panel" role="tabpanel">
      <div class="ui-columns">
        <div class="ui-col-main">
      <div class="card">"""
if old not in text:
    raise SystemExit("login open not found")
text = text.replace(old, new, 1)

browser = """
      <div class="card">
        <h2>Browser session</h2>
        <p>Logged in: <strong id="session-logged-in">unknown</strong></p>
        <div class="btn-row">
          <button type="button" class="primary" id="btn-open-login">Open login browser</button>
          <button type="button" id="btn-login-done">Done (close browser)</button>
          <button type="button" id="btn-refresh-session">Refresh session</button>
        </div>
      </div>
"""
if browser not in text:
    raise SystemExit("browser card not found")
text = text.replace(browser, "", 1)

login_end = """        <motion.div class="btn-row">
          <button type="button" id="btn-save-ui-token">Save UI token</button>
        </div>
      </div>

    </section>"""
login_end = """        <motion.div class="btn-row">
          <button type="button" id="btn-save-ui-token">Save UI token</button>
        </div>
      </div>

    </section>"""
login_end = """        <div class="btn-row">
          <button type="button" id="btn-save-ui-token">Save UI token</button>
        </div>
      </div>

    </section>"""
login_end_new = """        <div class="btn-row">
          <button type="button" id="btn-save-ui-token">Save UI token</button>
        </div>
      </div>
        </div>
        <aside class="ui-col-side" aria-label="Browser session">
      <div class="card">
        <h2>Browser session</h2>
        <p>Logged in: <strong id="session-logged-in">unknown</strong></p>
        <div class="btn-row">
          <button type="button" class="primary" id="btn-open-login">Open login browser</button>
          <button type="button" id="btn-login-done">Done (close browser)</button>
          <button type="button" id="btn-refresh-session">Refresh session</button>
        </div>
      </div>
        </aside>
      </div>
    </section>"""
if login_end not in text:
    raise SystemExit("login end not found")
text = text.replace(login_end, login_end_new, 1)

HTML.write_text(text, encoding="utf-8")
print("ok")
