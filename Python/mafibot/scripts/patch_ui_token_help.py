"""One-off patch: add MAFIBOT_UI_TOKEN help text on Login tab."""
from pathlib import Path

D = "d" + "i" + "v"
p = Path(__file__).resolve().parents[1] / "mafibot/static/index.html"
text = p.read_text(encoding="utf-8")
old = (
    f'        <{D} class="grid-2" style="margin-top: 1rem;">\n'
    f"          <{D}>\n"
    '            <label for="ui-token">UI token</label>'
)
new = (
    f'        <{D} class="login-subsection">\n'
    '          <h3 class="subsection-title">Dashboard access token</h3>\n'
    '          <p class="tos-note">\n'
    "            Optional shared secret that protects the dashboard API (start/stop bot, profiles, credentials).\n"
    "            This is <strong>not</strong> your Mafiaspillet username or password.\n"
    "          </p>\n"
    '          <p class="tos-note">\n'
    "            On the server, set the environment variable <strong>MAFIBOT_UI_TOKEN</strong> before running\n"
    "            <strong>mafibot.py ui</strong>. Enter the same value below and click Save — it is kept only in this\n"
    "            browser tab and sent on API calls (<strong>X-Mafibot-Token</strong>) and the live log WebSocket\n"
    "            (<strong>?token=</strong>).\n"
    "          </p>\n"
    '          <p class="tos-note">\n'
    "            Leave empty when you only open the dashboard at <strong>127.0.0.1</strong> (default). Use a long random\n"
    "            token if you bind to another host or expose port 8766 on your network.\n"
    "          </p>\n"
    f'          <{D} class="grid-2">\n'
    f"            <{D}>\n"
    '              <label for="ui-token">UI token</label>'
)
if old not in text:
    raise SystemExit("marker not found")
text = text.replace(old, new, 1)
close_old = (
    f'        <{D} class="btn-row">\n'
    '          <button type="button" id="btn-save-ui-token">Save UI token</button>\n'
    f"        </{D}>\n"
    f"      </{D}>\n"
    f"        </{D}>\n"
    '        <aside class="ui-col-side" aria-label="Browser session">'
)
close_new = (
    f'        <{D} class="btn-row">\n'
    '          <button type="button" id="btn-save-ui-token">Save UI token</button>\n'
    f"        </{D}>\n"
    f"        </{D}>\n"
    f"      </{D}>\n"
    f"        </{D}>\n"
    '        <aside class="ui-col-side" aria-label="Browser session">'
)
if close_old not in text:
    raise SystemExit("close marker not found")
text = text.replace(close_old, close_new, 1)
p.write_text(text, encoding="utf-8")
print("patched")
