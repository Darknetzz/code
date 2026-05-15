# Webbot

Human-like browser automation with Playwright. Click and type on web pages with curved mouse paths, variable delays, and a persistent browser profile.

## Install

```bash
cd Python/webbot
pip install -r requirements.txt
python -m playwright install chromium
```

## Web dashboard

```bash
python webbot.py ui
```

Opens `http://127.0.0.1:8765/` in your browser.

- **Run** — pick a scenario, set loops and pause between loops, Start / Stop, live log
- **Builder** — define steps (goto, click, fill, submit_form, delay, scroll), save as JSON, test run

JSON scenarios are stored in `%APPDATA%/webbot/scenarios/` (Windows) or `~/.config/webbot/scenarios/`.

**Security:** the UI binds to localhost by default. Do not expose the port to your network without adding auth.

## CLI

```bash
python webbot.py run example
python webbot.py run example_flow -n 5 --pause-between-loops 60
python webbot.py open https://example.com
python webbot.py scenarios
python webbot.py codegen https://yoursite.com
```

## Scenarios

| Name | Type | Description |
|------|------|-------------|
| `example` | Python | Demo on example.com |
| `example_flow` | JSON | Same flow via the step builder (seeded on first run) |

Add Python scenarios under `webbot/scenarios/` and register in `scenarios/__init__.py`, or create flows in the Builder UI.

## Form submission (GET and POST)

Use **`fill`** for a single field, or **`submit_form`** to fill multiple fields and submit in one step. The browser uses the form’s HTML `method` attribute (`get` or `post`); the step’s `method` field is checked against it before submit.

**GET search form example:**

```json
{
  "action": "submit_form",
  "method": "get",
  "form_selector": "#search-form",
  "fields": [
    { "by": "css", "selector": "input[name=q]", "value": "playwright automation" }
  ],
  "submit_by": "role",
  "submit_role": "button",
  "submit_name": "Search"
}
```

**POST login example:**

```json
{
  "action": "submit_form",
  "method": "post",
  "form_selector": "form.login",
  "fields": [
    { "by": "label", "label": "Email", "value": "user@example.com" },
    { "by": "label", "label": "Password", "value": "secret" }
  ],
  "submit_by": "css",
  "submit_selector": "button[type=submit]"
}
```

Set `"submit_by": "form"` and provide `form_selector` to call `form.submit()` instead of clicking a button (less human-like, but reliable).
