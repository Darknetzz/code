# SnapBot - Snapchat Browser Automation

**Version 2.0.0** - Selenium-based browser automation for Snapchat Web

## Overview

SnapBot uses [Selenium](https://www.selenium.dev/) to automate Snapchat Web, providing a programmatic way to interact with Snapchat through a real browser session.

Rather than trying to reverse-engineer Snapchat's private APIs, this tool automates the official Snapchat Web interface (`web.snapchat.com`) where official support exists.

## Why Selenium Instead of API?

- ✅ **Official Support** - Uses Snapchat's official web interface
- ✅ **Reliable** - No fragile API reverse-engineering
- ✅ **Real Browser** - Handles 2FA, reCAPTCHA, and other security features
- ✅ **Sustainable** - Works as long as Snapchat Web exists
- ✅ **Self-Contained** - Auto-downloads portable Chromium (no manual install needed)

## Installation

```bash
pip install -r requirements.txt
```

**Dependencies:**
- `typer>=0.9.0` - CLI framework
- `rich>=13.0.0` - Terminal formatting
- `selenium>=4.0.0` - Browser automation
- `webdriver-manager>=4.0.0` - Automatic ChromeDriver management

**Note:** Chrome/Chromium is NOT required to be pre-installed! The script will automatically download a portable version (~150 MB one-time download) on first run.

## Quick Start

### Login to Snapchat

```bash
python snapbot.py login
```

This opens a Chrome browser where you log in manually. Once logged in, press Enter to verify the session.

### Open Interactive Browser Session

```bash
python snapbot.py browser
```

Opens Snapchat Web in a persistent browser window. Close the browser to exit.

### Check Installation

```bash
python snapbot.py version
```

Shows version and Selenium availability status.

## Commands

### `login` - Authenticate with Snapchat

Opens a browser and guides you through manual login.

```bash
python snapbot.py login              # Interactive
python snapbot.py login -h           # Show help
```

**Options:**
- `-s, --save` - Save username for future sessions
- `-h, --headless` - Run browser in headless mode (experimental)

### `browser` - Open Interactive Session

Opens Snapchat Web in a browser window for manual interaction.

```bash
python snapbot.py browser
python snapbot.py browser -h         # Headless mode
```

### `config` - Manage Configuration

View and modify bot settings.

```bash
python snapbot.py config --show      # Display current settings
python snapbot.py config -h true     # Enable headless mode
python snapbot.py config -d true     # Enable debug mode
```

### `version` - Show Version Info

```bash
python snapbot.py version
```

Shows SnapBot version, Selenium status, and whether portable Chromium is installed.

### `update-chromium` - Update Portable Browser

```bash
python snapbot.py update-chromium        # Update if installed
python snapbot.py update-chromium -f     # Force re-download
```

Updates the portable Chromium to the latest stable version. This automatically:
- Fetches the latest Chrome from Google's official API (currently 143.x)
- Downloads matching ChromeDriver
- Replaces the old installation

### `clear-cache` - Remove Saved Data

Deletes credentials and configuration files.

```bash
python snapbot.py clear-cache
```

## Status & Roadmap

### Currently Implemented ✅
- Browser initialization with ChromeDriver
- Manual login via Snapchat Web
- Session persistence
- Configuration management
- Credentials storage (secure)

### Planned for Future ✅
- Automated message sending via XPath selectors
- Friend list extraction
- Status updates
- Snap capture and sending
- Story management

## Configuration

SnapBot stores configuration in `snapchat_config.json`:

```json
{
  "version": "2.0.0",
  "headless": false,
  "timeout": 30,
  "debug": false
}
```

Credentials are stored separately in `snapchat_credentials.json` with file permissions `0o600` (read/write by owner only).

## Technical Details

### Browser Initialization

Uses Chrome with the following optimizations:
- Disables automation detection flags
- Spoofs user agent as legitimate client
- Handles sandbox restrictions
- Automatic ChromeDriver installation via webdriver-manager

### Session Management

- Waits for user to complete manual login
- Verifies successful authentication by checking for UI elements
- Maintains persistent browser session for automation

### Security

- Credentials stored with `chmod 0o600` (owner only)
- No plain text passwords in logs
- Respects 2FA and security challenges

## Troubleshooting

### Chrome/ChromeDriver Issues

**Error:** "chromedriver not found"

```bash
pip install webdriver-manager  # Auto-installs correct ChromeDriver
```

### Selenium Not Installed

**Error:** "ImportError: No module named 'selenium'"

```bash
pip install selenium>=4.0.0 webdriver-manager>=4.0.0
```

### Browser Won't Open

- Check if Chrome is installed (`google-chrome`, `chromium`, or `chrome.exe`)
- Disable headless mode (not fully tested)
- Run with debug: `python snapbot.py config -d true`

### 2FA/Login Issues

If Snapchat requires 2FA:
1. Complete it manually in the browser
2. Press Enter when the verification is done
3. Script will detect successful login

## Comparison: Before vs After

| Feature | REST API (v1) | Selenium (v2) |
|---------|---------------|---------------|
| Public API Available | ❌ No | ✅ Yes (Web) |
| Official Support | ❌ No | ✅ Yes |
| 2FA/Security | ❌ No | ✅ Yes |
| Browser Control | ❌ No | ✅ Yes |
| Reliability | ❌ Very Low | ✅ High |

## Alternative Approaches

If Selenium doesn't work for your use case:

### **Snapchat Marketing API** (Official - Business)
- Requires Snapchat Business Account
- Limited to marketing/advertising
- [Official Docs](https://marketingapi.snapchat.com/)

### **Snapchat Lens Studio** (Official - Creative)
- Create custom AR lenses
- Limited to lens/filter features
- [Lens Studio](https://www.snapchat.com/lens-studio)

### **Playwright** (Alternative Browser Automation)
- Similar to Selenium
- Smaller footprint
- Better debugging tools

## License

MIT

## Disclaimer

This tool is for educational purposes and personal automation only. Use responsibly and in accordance with Snapchat's Terms of Service.
