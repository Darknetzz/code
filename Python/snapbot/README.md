# SnapBot - Snapchat API Integration

Simple Python script for interacting with Snapchat using the unofficial API. Send messages, manage friends, and automate Snapchat interactions.

## Features

- 🔐 **Account Authentication** - Secure login with credential storage
- 💬 **Send Messages** - Text messaging to Snapchat friends
- 👥 **Friend Management** - View and manage your friend list
- 🎯 **Configuration** - Persistent config for preferences
- 🔒 **Secure Credentials** - Encrypted credential storage with file permissions
- 📊 **Rich CLI** - Beautiful terminal output with tables and formatting

## Installation

```bash
pip install -r requirements.txt
```

**Note:** The script uses `snapchat-unofficial` which requires:
- Python 3.7+
- Working internet connection
- Valid Snapchat account

## Commands

### Login
Authenticate with your Snapchat account:

```bash
# Interactive login
python snapbot.py login

# Login with credentials
python snapbot.py login -u username -p password

# Save credentials for future use
python snapbot.py login -u username -p password -s
```

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

## Troubleshooting

### "snapchat-unofficial not installed"
```bash
pip install snapchat-unofficial
```

### Authentication Failed
- Verify username and password are correct
- Check internet connection
- Try logging in on official Snapchat app to confirm credentials work
- Account may have 2FA enabled (not supported by unofficial API)

### Import Errors
Ensure all requirements are installed:
```bash
pip install -r requirements.txt
```

## API Limitations

The unofficial Snapchat API has some limitations:

- May not support all Snapchat features
- Text-only messaging (no photos/videos)
- Subject to rate limiting
- No official support from Snapchat
- May break if Snapchat changes their API

## Disclaimer

This script uses an unofficial Snapchat API. Use at your own risk. Snapchat does not officially support third-party API access and may restrict or block access at any time.

## License

Feel free to modify and use as needed!
