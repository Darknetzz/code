#!/usr/bin/env python3
"""
SnapBot - Snapchat Browser Automation
Uses Selenium to automate Snapchat via browser (more reliable than API)
"""

import os
import json
import sys
import time
import zipfile
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from urllib.request import urlretrieve

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

console = Console()
app = typer.Typer(rich_markup_mode="rich")

# ─────────────────────────────────────────────────────────────────────── #
#                              CONSTANTS                                  #
# ─────────────────────────────────────────────────────────────────────── #

SCRIPT_VERSION = "2.0.0"
CONFIG_FILE = "snapchat_config.json"
CREDENTIALS_FILE = "snapchat_credentials.json"
SNAPCHAT_WEB_URL = "https://web.snapchat.com"

# Chrome for Testing API endpoint
CHROME_VERSION_API = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"

# Fallback URLs if API fails (updated regularly)
FALLBACK_CHROME_VERSION = "143.0.7499.40"  # Latest stable as of Dec 2025


# ─────────────────────────────────────────────────────────────────────── #
#                         CHROMIUM MANAGEMENT                             #
# ─────────────────────────────────────────────────────────────────────── #

def get_chromium_dir() -> Path:
    """Get the directory where portable Chromium is stored."""
    return Path(__file__).parent / "chromium"


def get_chrome_binary_path() -> Optional[Path]:
    """Get the path to Chrome/Chromium binary."""
    chromium_dir = get_chromium_dir()
    
    # Check for portable Chromium
    portable_paths = [
        chromium_dir / "chrome-win64" / "chrome.exe",
        chromium_dir / "chrome-win32" / "chrome.exe",
        chromium_dir / "chrome.exe",
    ]
    
    for path in portable_paths:
        if path.exists():
            return path
    
    return None


def get_profile_dir() -> Path:
    """Path to persistent Chromium profile (cookies, sessions)."""
    return get_chromium_dir() / "profile"


def get_chrome_version() -> str:
    """Read stored Chromium version or fall back."""
    version_file = get_chromium_dir() / "version.txt"
    if version_file.exists():
        try:
            return version_file.read_text(encoding="utf-8").strip() or FALLBACK_CHROME_VERSION
        except Exception:
            return FALLBACK_CHROME_VERSION
    return FALLBACK_CHROME_VERSION


def get_chromedriver_path() -> Optional[Path]:
    """Get the path to ChromeDriver binary."""
    chromium_dir = get_chromium_dir()
    
    # Check for portable ChromeDriver
    driver_paths = [
        chromium_dir / "chromedriver-win64" / "chromedriver.exe",
        chromium_dir / "chromedriver-win32" / "chromedriver.exe",
        chromium_dir / "chromedriver.exe",
    ]
    
    for path in driver_paths:
        if path.exists():
            return path
    
    return None


def get_latest_chrome_urls(arch: str) -> tuple[Optional[str], Optional[str], str]:
    """Fetch the latest Chrome/Driver URLs from Chrome for Testing API and return version."""
    import urllib.request
    
    try:
        # Try to fetch latest version from API
        with urllib.request.urlopen(CHROME_VERSION_API, timeout=10) as response:
            data = json.loads(response.read().decode())
            stable = data['channels']['Stable']
            version = stable['version']
            
            # Find the correct platform downloads
            chrome_url = None
            driver_url = None
            
            for download in stable['downloads']['chrome']:
                if download['platform'] == f'win{arch[-2:]}':
                    chrome_url = download['url']
                    break
            
            for download in stable['downloads']['chromedriver']:
                if download['platform'] == f'win{arch[-2:]}':
                    driver_url = download['url']
                    break
            
            if chrome_url and driver_url:
                console.print(f"[dim]Using Chrome version: {version}[/dim]")
                return chrome_url, driver_url, version
    except Exception as e:
        console.print(f"[dim]Could not fetch latest version: {e}[/dim]")
    
    # Fallback to hardcoded URLs
    console.print(f"[dim]Using fallback Chrome version: {FALLBACK_CHROME_VERSION}[/dim]")
    base_url = f"https://storage.googleapis.com/chrome-for-testing-public/{FALLBACK_CHROME_VERSION}"
    return (
        f"{base_url}/{arch}/chrome-{arch}.zip",
        f"{base_url}/{arch}/chromedriver-{arch}.zip",
        FALLBACK_CHROME_VERSION,
    )


def download_chromium() -> bool:
    """Download and extract portable Chromium and ChromeDriver."""
    import platform
    
    arch = "win64" if platform.machine().endswith("64") else "win32"
    chrome_url, driver_url, version = get_latest_chrome_urls(arch)
    
    if not chrome_url or not driver_url:
        console.print(f"[bold red]No Chromium build available for: {arch}[/bold red]")
        return False
    
    chromium_dir = get_chromium_dir()
    chromium_dir.mkdir(exist_ok=True)
    
    chrome_zip = chromium_dir / "chromium.zip"
    driver_zip = chromium_dir / "chromedriver.zip"
    version_file = chromium_dir / "version.txt"
    
    try:
        # Download Chrome
        console.print(f"[bold]Downloading latest portable Chromium ({arch})...[/bold]")
        console.print(f"[dim]This is a one-time download (~150 MB)[/dim]")
        
        def reporthook(blocknum, blocksize, totalsize):
            downloaded = blocknum * blocksize
            percent = min(100, (downloaded / totalsize) * 100) if totalsize > 0 else 0
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = totalsize / (1024 * 1024)
            print(f"\r[{percent:3.0f}%] {mb_downloaded:.1f} MB / {mb_total:.1f} MB", end="")
        
        urlretrieve(chrome_url, chrome_zip, reporthook=reporthook)
        print()
        
        console.print("[bold]Extracting Chromium...[/bold]")
        with zipfile.ZipFile(chrome_zip, 'r') as zip_ref:
            zip_ref.extractall(chromium_dir)
        chrome_zip.unlink()
        
        # Download ChromeDriver
        console.print(f"[bold]Downloading ChromeDriver ({arch})...[/bold]")
        urlretrieve(driver_url, driver_zip)
        
        console.print("[bold]Extracting ChromeDriver...[/bold]")
        with zipfile.ZipFile(driver_zip, 'r') as zip_ref:
            zip_ref.extractall(chromium_dir)
        driver_zip.unlink()

        # Persist the version we downloaded so UA can match
        version_file.write_text(f"{version}\n", encoding="utf-8")
        
        console.print("[bold green]✅ Chromium and ChromeDriver installed successfully![/bold green]")
        return True
        
    except Exception as e:
        console.print(f"[bold red]Error downloading Chromium: {e}[/bold red]")
        for zip_file in [chrome_zip, driver_zip]:
            if zip_file.exists():
                zip_file.unlink()
        return False


# ─────────────────────────────────────────────────────────────────────── #
#                              CONFIG MANAGEMENT                          #
# ─────────────────────────────────────────────────────────────────────── #

def load_credentials() -> Optional[Dict]:
    """Load credentials from config file."""
    if not Path(CREDENTIALS_FILE).exists():
        return None
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        console.print(f"[bold red]Error loading credentials: {e}[/bold red]")
        return None


def save_credentials(username: str, password: str) -> None:
    """Save credentials to config file."""
    try:
        credentials = {
            "username": username,
            "password": password,
            "last_login": datetime.now().isoformat()
        }
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=2)
        # Restrict file permissions for security
        os.chmod(CREDENTIALS_FILE, 0o600)
        console.print("[bold green]✅ Credentials saved[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error saving credentials: {e}[/bold red]")


def load_config() -> Dict:
    """Load or create configuration file."""
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[bold yellow]Error loading config: {e}[/bold yellow]")
            return get_default_config()
    
    return get_default_config()


def get_default_config() -> Dict:
    """Get default configuration."""
    return {
        "version": SCRIPT_VERSION,
        "headless": False,
        "timeout": 30,
        "debug": False
    }


def save_config(config: Dict) -> None:
    """Save configuration file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        console.print(f"[bold red]Error saving config: {e}[/bold red]")


# ─────────────────────────────────────────────────────────────────────── #
#                              SNAPCHAT BROWSER BOT                       #
# ─────────────────────────────────────────────────────────────────────── #

class SnapchatBrowserBot:
    """Browser-based Snapchat automation using Selenium."""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self.authenticated = False
        self.wait_timeout = 30
    
    def initialize_driver(self) -> bool:
        """Initialize Chrome WebDriver."""
        if not SELENIUM_AVAILABLE:
            console.print("[bold red]Error: Selenium not installed[/bold red]")
            console.print("[dim]Install with: pip install selenium webdriver-manager[/dim]")
            return False
        
        try:
            options = Options()
            ua_version = get_chrome_version()
            profile_dir = get_profile_dir()
            profile_dir.mkdir(parents=True, exist_ok=True)
            
            # Check for portable Chromium first
            chrome_binary = get_chrome_binary_path()
            chromedriver_path = get_chromedriver_path()
            
            if not chrome_binary or not chromedriver_path:
                console.print("[bold yellow]Portable Chromium not found[/bold yellow]")
                if Confirm.ask("Download portable Chromium (~150 MB)?", default=True):
                    if not download_chromium():
                        return False
                    chrome_binary = get_chrome_binary_path()
                    chromedriver_path = get_chromedriver_path()
                else:
                    console.print("\n[bold yellow]Chrome Browser Not Found[/bold yellow]")
                    console.print("[dim]SnapBot requires Chrome. Options:[/dim]\n")
                    console.print("[dim]1. Install Google Chrome: https://www.google.com/chrome/[/dim]")
                    console.print("[dim]2. Install Chromium: https://www.chromium.org/[/dim]")
                    console.print("[dim]3. Run this script again to download portable Chromium[/dim]")
                    return False
            
            # Set Chrome binary path
            if chrome_binary:
                options.binary_location = str(chrome_binary)
                console.print(f"[dim]Using Chromium: {chrome_binary.name}[/dim]")
            
            if self.headless:
                options.add_argument("--headless=new")
            
            # Additional options for stability
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-data-dir={profile_dir}")
            options.add_argument(f"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ua_version} Safari/537.36")
            
            with console.status("[bold]Initializing Chrome browser..."):
                # Use portable ChromeDriver if available
                if chromedriver_path:
                    service = Service(executable_path=str(chromedriver_path))
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    # Try using webdriver-manager as fallback
                    try:
                        from webdriver_manager.chrome import ChromeDriverManager
                        service = Service(ChromeDriverManager().install())
                        self.driver = webdriver.Chrome(service=service, options=options)
                    except ImportError:
                        # Last resort: system ChromeDriver
                        self.driver = webdriver.Chrome(options=options)
                
                console.print("[bold green]✅ Browser initialized[/bold green]")
                return True
                
        except Exception as e:
            console.print(f"[bold red]Error initializing browser: {e}[/bold red]")
            console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
            console.print("[dim]1. Make sure webdriver-manager is installed:[/dim]")
            console.print("[dim]   pip install webdriver-manager[/dim]")
            console.print("[dim]2. If portable Chromium failed, try installing Chrome:[/dim]")
            console.print("[dim]   https://www.google.com/chrome/[/dim]")
            return False
    
    def authenticate(self) -> bool:
        """Authenticate with Snapchat via browser."""
        if not self.driver:
            console.print("[bold red]Browser not initialized[/bold red]")
            return False
        
        try:
            with console.status("[bold]Loading Snapchat Web..."):
                self.driver.get(SNAPCHAT_WEB_URL)
                time.sleep(3)
            
            console.print("[bold blue]📱 Snapchat Web loaded[/bold blue]")
            console.print("[dim]Please log in manually in the browser window...[/dim]")
            console.print("[dim]Once you've logged in and can see your chats, press Enter here[/dim]")
            
            # Wait for user to manually login
            input("[bold]Press Enter once logged in:[/bold] ")
            
            # Check if we're logged in by looking for the chat interface
            with console.status("[bold]Verifying authentication..."):
                time.sleep(2)

                # Try a handful of stable UI markers to reduce false negatives
                markers = [
                    (By.CSS_SELECTOR, "[data-test-id='conversation-input']"),
                    (By.CSS_SELECTOR, "[data-testid='conversation-input']"),
                    (By.CSS_SELECTOR, "[aria-label='Send a Chat']"),
                    (By.CSS_SELECTOR, "[aria-label='Send a chat']"),
                    (By.CSS_SELECTOR, "main"),
                    (By.XPATH, "//*[contains(text(), 'Chat')]")
                ]

                found = None
                for by, selector in markers:
                    try:
                        WebDriverWait(self.driver, self.wait_timeout).until(
                            EC.presence_of_element_located((by, selector))
                        )
                        found = f"{by} {selector}"
                        break
                    except Exception:
                        continue

                if found:
                    self.authenticated = True
                    console.print(f"[bold green]✅ Successfully authenticated![/bold green] [dim]Detected: {found}[/dim]")
                    return True

                # Fallback: if URL looks like chat, trust the session
                if "web.snapchat.com" in (self.driver.current_url or ""):
                    self.authenticated = True
                    console.print("[bold green]✅ Logged in (URL check) — could not find a known marker[/bold green]")
                    console.print("[dim]If anything looks off, re-run login and wait a bit longer after 2FA.[/dim]")
                    return True

                console.print("[bold yellow]⚠️  Could not verify login[/bold yellow]")
                console.print("[dim]You may have encountered a 2FA prompt or page layout changed[/dim]")
                return False
                    
        except Exception as e:
            console.print(f"[bold red]Authentication error: {e}[/bold red]")
            return False
    
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            console.print("[bold green]Browser closed[/bold green]")


# ─────────────────────────────────────────────────────────────────────── #
#                              CLI COMMANDS                               #
# ─────────────────────────────────────────────────────────────────────── #

@app.command()
def login(
    save: bool = typer.Option(False, "-s", "--save", help="Save username for future use"),
    headless: bool = typer.Option(False, "-h", "--headless", help="Run browser in headless mode"),
):
    """Authenticate with Snapchat via browser."""
    
    console.print("[dim]This command will open a Chrome browser to log into Snapchat[/dim]")
    console.print("[dim]You'll complete the login manually, then this script will verify the session[/dim]")
    
    # Create bot and authenticate
    bot = SnapchatBrowserBot(headless=headless)
    
    if bot.initialize_driver():
        if bot.authenticate():
            if save:
                confirm = Confirm.ask("Save username for future use?", default=False)
                if confirm:
                    save_username = Prompt.ask("Username to save")
                    save_credentials(save_username, "")
            
            console.print("\n[bold green]🎉 Login successful![/bold green]")
            console.print("[dim]Browser will close in 5 seconds...[/dim]")
            time.sleep(5)
            bot.close()
        else:
            bot.close()
            raise typer.Exit(code=1)
    else:
        raise typer.Exit(code=1)


@app.command()
def browser(
    headless: bool = typer.Option(False, "-h", "--headless", help="Run in headless mode"),
):
    """Open interactive Snapchat Web browser session."""
    
    console.print("[dim]Opening Snapchat Web in browser...[/dim]")
    console.print("[dim]Log in manually and interact as needed[/dim]")
    console.print("[dim]Close the browser window to exit[/dim]")
    
    # Create bot and open browser
    bot = SnapchatBrowserBot(headless=headless)
    
    if bot.initialize_driver():
        try:
            with console.status("[bold]Loading Snapchat Web..."):
                bot.driver.get(SNAPCHAT_WEB_URL)
                time.sleep(3)
            
            console.print("[bold green]✅ Browser is open[/bold green]")
            console.print("[dim]Keep this window open while you use Snapchat Web[/dim]")
            console.print("[dim]Press Ctrl+C or close the browser to exit[/dim]")
            
            # Keep browser open
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[dim]Closing browser...[/dim]")
                bot.close()
        except Exception as e:
            console.print(f"[bold red]Error: {e}[/bold red]")
            bot.close()
            raise typer.Exit(code=1)
    else:
        raise typer.Exit(code=1)


@app.command()
def config(
    show: bool = typer.Option(False, "-s", "--show", help="Show current config"),
    headless: Optional[bool] = typer.Option(None, "-h", "--headless", help="Set headless mode"),
    debug: Optional[bool] = typer.Option(None, "-d", "--debug", help="Enable debug mode"),
):
    """Manage SnapBot configuration."""
    
    cfg = load_config()
    
    if show:
        console.print("[bold]Current Configuration:[/bold]")
        for key, value in cfg.items():
            console.print(f"  {key}: {value}")
        return
    
    if headless is not None:
        cfg['headless'] = headless
        console.print(f"[bold]Headless mode:[/bold] {headless}")
    
    if debug is not None:
        cfg['debug'] = debug
        console.print(f"[bold]Debug mode:[/bold] {debug}")
    
    if headless is not None or debug is not None:
        save_config(cfg)
        console.print("[bold green]✅ Configuration updated[/bold green]")


@app.command()
def clear_cache():
    """Clear saved credentials and configuration."""
    
    files_to_clear = [CREDENTIALS_FILE, CONFIG_FILE]
    cleared = []
    
    for file in files_to_clear:
        if Path(file).exists():
            try:
                Path(file).unlink()
                cleared.append(file)
            except Exception as e:
                console.print(f"[bold red]Error clearing {file}: {e}[/bold red]")
    
    if cleared:
        console.print(f"[bold green]✅ Cleared:[/bold green] {', '.join(cleared)}")
    else:
        console.print("[bold yellow]Nothing to clear[/bold yellow]")


@app.command()
def logout(
    force: bool = typer.Option(False, "-f", "--force", help="Do not prompt before deleting the saved browser session"),
):
    """Log out by deleting the persistent Chromium profile (cookies/session)."""

    profile_dir = get_profile_dir()

    if not profile_dir.exists():
        console.print("[bold yellow]No saved session found[/bold yellow]")
        return

    if not force:
        if not Confirm.ask("Delete the saved browser session (cookies, profile)?", default=False):
            console.print("[dim]Logout cancelled[/dim]")
            return

    try:
        import shutil
        shutil.rmtree(profile_dir)
        console.print("[bold green]✅ Session cleared[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error deleting profile: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def update_chromium(
    force: bool = typer.Option(False, "-f", "--force", help="Force re-download even if already installed"),
):
    """Update portable Chromium to the latest version."""
    
    chromium_dir = get_chromium_dir()
    
    if chromium_dir.exists() and not force:
        console.print("[bold yellow]Chromium already installed[/bold yellow]")
        if not Confirm.ask("Re-download and update to latest version?", default=True):
            console.print("[dim]Update cancelled[/dim]")
            return
    
    # Remove old installation
    if chromium_dir.exists():
        console.print("[dim]Removing old Chromium installation...[/dim]")
        import shutil
        shutil.rmtree(chromium_dir)
    
    # Download latest version
    if download_chromium():
        console.print("[bold green]✅ Chromium updated successfully![/bold green]")
    else:
        console.print("[bold red]❌ Update failed[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def version():
    """Show version information."""
    console.print(f"[bold]SnapBot[/bold] v{SCRIPT_VERSION}")
    console.print("Snapchat Browser Automation Tool (Selenium)")
    if SELENIUM_AVAILABLE:
        console.print("[bold green]✅[/bold green] [dim]Selenium installed[/dim]")
    else:
        console.print("[bold red]⚠️ [/bold red] [dim]Selenium not installed (pip install selenium webdriver-manager)[/dim]")
    
    # Show Chromium version if installed
    chrome_binary = get_chrome_binary_path()
    if chrome_binary:
        console.print(f"[bold green]✅[/bold green] [dim]Portable Chromium installed[/dim]")


if __name__ == "__main__":
    # Allow global --version/-V to route to the version command
    if any(arg in ("--version", "-V") for arg in sys.argv[1:]):
        sys.argv = [sys.argv[0], "version"]
    elif len(sys.argv) == 1:
        sys.argv.extend(["--help"])
    elif len(sys.argv) == 2 and sys.argv[1] == "config":
        sys.argv.append("--help")
    app()
