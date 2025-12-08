# SnapBot - Snapchat API Integration

⚠️ **NOTE: This is a proof-of-concept/educational tool.** Snapchat does not provide an official public API for third-party access. This script demonstrates how one might structure API interactions but cannot authenticate due to Snapchat's closed ecosystem.

Simple Python script for interacting with Snapchat using REST API concepts. Send messages, manage friends, and explore API integration patterns.

## ⚠️ Important Limitations

**Snapchat does NOT have a public API**, so this tool:
- ❌ **Cannot authenticate** with real Snapchat accounts
- ❌ **Cannot send actual messages** 
- ❌ **Cannot access real friends lists**
- ✅ **CAN** demonstrate API patterns and structure
- ✅ **CAN** be used as a foundation for alternative approaches

## Real Alternatives

If you need to automate Snapchat:

### 1. **Snapchat Marketing API** (Official - Limited)
- Requires Snapchat Business Account
- Limited to marketing campaigns and ads
- Official support from Snapchat

### 2. **Lens Studio** (Official - Creative)
- Create custom Snapchat lenses
- Limited to lens development
- Official Snapchat tool

### 3. **Browser Automation** (Unofficial - Full Access)
- Use Selenium, Playwright, or Puppeteer
- Automate via browser like a real user
- Still violates ToS but more reliable
- Example: `from selenium import webdriver`

### 4. **Bitmoji API** (Official - Limited)
- Avatar/Bitmoji specific features
- Official but very limited scope

## Commands

### Login
Authenticate with your Snapchat account (if endpoint available):

```bash
# Interactive login
python snapbot.py login

# Login with credentials
python snapbot.py login -u username -p password

# Save credentials for future use
python snapbot.py login -u username -p password -s
```

**Status:** ❌ Non-functional - endpoint not accessible

### Send Message
Send a message or picture to a friend:

```bash
# Send text message
python snapbot.py send friend_username -m "Hello!"

# Send picture
python snapbot.py send friend_username -p /path/to/image.jpg

# Send both text and picture
python snapbot.py send friend_username -m "Check this out!" -p photo.png

# With explicit credentials
python snapbot.py send friend_username -m "Hi!" -u username -pw password
```

**Supported image formats:** JPG, JPEG, PNG, GIF, BMP

### List Friends
View your Snapchat friends:

```bash
# Show all friends
python snapbot.py friends

# Limit to 10 friends
python snapbot.py friends -l 10

# With explicit credentials
python snapbot.py friends -u username -p password
```

### Configuration
Manage SnapBot settings:

```bash
# Show current config
python snapbot.py config --show

# Enable auto-login
python snapbot.py config --auto-login

# Enable debug mode
python snapbot.py config --debug

# Disable features
python snapbot.py config --auto-login false --debug false
```

### Clear Cache
Remove saved credentials and configuration:

```bash
python snapbot.py clear-cache
```

### Version
Show version information:

```bash
python snapbot.py version
```

## Usage Examples

```bash
# Login and save credentials
python snapbot.py login -u myusername -p mypassword -s

# Send text message using saved credentials
python snapbot.py send bestfriend -m "Check out this cool thing!"

# Send a picture to a friend
python snapbot.py send bestfriend -p C:\Users\Pictures\photo.jpg

# Send picture with caption
python snapbot.py send bestfriend -m "Look at this!" -p photo.jpg

# Send both text and picture together
python snapbot.py send bestfriend -m "Epic moment!" -p screenshot.png

# List friends
python snapbot.py friends -l 15

# Enable debug mode for troubleshooting
python snapbot.py config --debug true --show

# Clear all saved data
python snapbot.py clear-cache
```

## Configuration Files

SnapBot creates two configuration files:

- **`snapchat_config.json`** - Application settings
  ```json
  {
    "version": "1.0.0",
    "auto_login": false,
    "timeout": 30,
    "debug": false
  }
  ```

- **`snapchat_credentials.json`** - Saved login credentials (restricted permissions)
  ```json
  {
    "username": "your_username",
    "password": "your_password",
    "last_login": "2025-12-08T10:30:45.123456"
  }
  ```

## Security Notes

⚠️ **Important Security Warnings:**

1. **Credentials File**: Saved credentials are stored with restricted file permissions (0600)
2. **Keep Private**: Never share your `snapchat_credentials.json` file
3. **API Limitations**: The unofficial API may have restrictions on automated messaging
4. **Account Risk**: Using unofficial APIs may violate Snapchat's ToS and risk account suspension
5. **Rate Limiting**: Be respectful with message frequency to avoid rate limiting

## Why This Doesn't Work (Yet)

Snapchat actively prevents third-party API access:

1. **No Official API** - Snapchat doesn't publish endpoints
2. **Reverse Engineering Required** - Must guess API structure
3. **Constant Changes** - Endpoints change frequently
4. **Rate Limiting** - Heavy anti-bot measures
5. **No Token Auth** - Credentials-only authentication isn't supported properly
6. **Server-Side Validation** - Even correct requests are rejected

## How to Make It Work

### Option A: Browser Automation (Most Reliable)
```python
from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://www.snapchat.com")
# Login via browser, then interact like a user
```

### Option B: Reverse Engineering (Complex)
1. Use Snapchat mobile app
2. Intercept HTTP requests with proxy (Charles, Burp)
3. Find actual API endpoints
4. Find authentication mechanism
5. Implement in this tool
6. Repeat whenever Snapchat changes

### Option C: Official API (Limited but Safe)
- Apply for Snapchat Business Account
- Use Marketing API
- Limited to business features only

## License

Feel free to modify and use as needed!
