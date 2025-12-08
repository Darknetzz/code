#!/usr/bin/env python3
"""
SnapBot - Snapchat API Integration
Simple script to interact with Snapchat using the REST API
"""

import os
import json
import sys
import base64
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

import typer
import requests
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

console = Console()
app = typer.Typer(rich_markup_mode="rich")

# ─────────────────────────────────────────────────────────────────────── #
#                              CONSTANTS                                  #
# ─────────────────────────────────────────────────────────────────────── #

SCRIPT_VERSION = "1.1.0"
CONFIG_FILE = "snapchat_config.json"
CREDENTIALS_FILE = "snapchat_credentials.json"

# Snapchat API endpoints (using REST API approach)
SNAPCHAT_API_BASE = "https://app.snapchat.com"
SNAPCHAT_API_HEADERS = {
    "User-Agent": "Snapchat/11.0.0 (Linux; Android 10)",
    "X-Snap-Client": "Android",
}


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


def save_credentials(username: str, password: str, auth_token: Optional[str] = None) -> None:
    """Save credentials to config file."""
    try:
        credentials = {
            "username": username,
            "password": password,
            "auth_token": auth_token,
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
        "auto_login": False,
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
#                              SNAPCHAT WRAPPER                           #
# ─────────────────────────────────────────────────────────────────────── #

class SnapchatBot:
    """Wrapper for Snapchat API interactions using REST API."""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.auth_token: Optional[str] = None
        self.authenticated = False
        self.session = requests.Session()
        self.session.headers.update(SNAPCHAT_API_HEADERS)
    
    def authenticate(self) -> bool:
        """Authenticate with Snapchat using username and password."""
        try:
            with console.status("[bold]Authenticating with Snapchat..."):
                auth_payload = {
                    "username": self.username,
                    "password": self.password,
                }
                
                # Try multiple potential endpoints
                endpoints = [
                    f"{SNAPCHAT_API_BASE}/login",
                    f"{SNAPCHAT_API_BASE}/api/login",
                    "https://api.snapchat.com/login",
                ]
                
                for endpoint in endpoints:
                    try:
                        response = self.session.post(
                            endpoint,
                            json=auth_payload,
                            timeout=30,
                            verify=True
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            self.auth_token = data.get("access_token") or data.get("auth_token")
                            self.authenticated = True
                            
                            if self.auth_token:
                                self.session.headers.update({
                                    "Authorization": f"Bearer {self.auth_token}"
                                })
                            
                            console.print("[bold green]✅ Successfully authenticated![/bold green]")
                            return True
                    except:
                        continue
                
                console.print("[bold yellow]⚠️  Authentication failed[/bold yellow]")
                console.print("[dim]Note: Snapchat doesn't provide a public API for third-party access[/dim]")
                console.print("[dim]This is a proof-of-concept tool. Real integration would require:[/dim]")
                console.print("[dim]  • Official Snapchat Business Account + Marketing API[/dim]")
                console.print("[dim]  • Browser automation (Selenium/Playwright)[/dim]")
                console.print("[dim]  • Snapchat's Lens Studio API (limited features)[/dim]")
                return False
                    
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Connection error: {e}[/bold red]")
            console.print("[dim]The Snapchat API endpoint may not be accessible or may have changed[/dim]")
            return False
        except Exception as e:
            console.print(f"[bold red]Authentication error: {e}[/bold red]")
            return False
    
    def get_friends(self) -> Optional[List[Dict]]:
        """Get list of friends."""
        if not self.authenticated:
            console.print("[bold red]Not authenticated[/bold red]")
            return None
        
        try:
            response = self.session.get(
                f"{SNAPCHAT_API_BASE}/friends",
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("friends", [])
            else:
                console.print(f"[bold red]Error getting friends: {response.status_code}[/bold red]")
                return None
                
        except Exception as e:
            console.print(f"[bold red]Error getting friends: {e}[/bold red]")
            return None
    
    def send_message(self, recipient: str, message: str) -> bool:
        """Send text message to a friend."""
        if not self.authenticated:
            console.print("[bold red]Not authenticated[/bold red]")
            return False
        
        try:
            with console.status(f"[bold]Sending message to {recipient}..."):
                payload = {
                    "recipient": recipient,
                    "type": "text",
                    "body": message,
                }
                
                response = self.session.post(
                    f"{SNAPCHAT_API_BASE}/chat/send",
                    json=payload,
                    timeout=30
                )
                
                if response.status_code in [200, 201]:
                    console.print(f"[bold green]✅ Message sent to {recipient}[/bold green]")
                    return True
                else:
                    console.print(f"[bold red]Failed to send message: {response.status_code}[/bold red]")
                    return False
                    
        except Exception as e:
            console.print(f"[bold red]Error sending message: {e}[/bold red]")
            return False
    
    def send_picture(self, recipient: str, image_path: str) -> bool:
        """Send a picture to a friend."""
        if not self.authenticated:
            console.print("[bold red]Not authenticated[/bold red]")
            return False
        
        image_file = Path(image_path)
        if not image_file.exists():
            console.print(f"[bold red]Error: Image file not found: {image_path}[/bold red]")
            return False
        
        if not image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            console.print(f"[bold red]Error: Unsupported image format: {image_file.suffix}[/bold red]")
            return False
        
        try:
            with console.status(f"[bold]Sending picture to {recipient}..."):
                with open(image_file, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                payload = {
                    "recipient": recipient,
                    "type": "image",
                    "media": image_data,
                    "filename": image_file.name,
                }
                
                response = self.session.post(
                    f"{SNAPCHAT_API_BASE}/chat/send",
                    json=payload,
                    timeout=60
                )
                
                if response.status_code in [200, 201]:
                    console.print(f"[bold green]✅ Picture sent to {recipient}[/bold green]")
                    return True
                else:
                    console.print(f"[bold red]Failed to send picture: {response.status_code}[/bold red]")
                    return False
                    
        except Exception as e:
            console.print(f"[bold red]Error sending picture: {e}[/bold red]")
            return False


# ─────────────────────────────────────────────────────────────────────── #
#                              CLI COMMANDS                               #
# ─────────────────────────────────────────────────────────────────────── #

@app.command()
def login(
    username: Optional[str] = typer.Option(None, "-u", "--username", help="Snapchat username"),
    password: Optional[str] = typer.Option(None, "-p", "--password", help="Snapchat password"),
    save: bool = typer.Option(False, "-s", "--save", help="Save credentials for future use"),
):
    """Authenticate with Snapchat account."""
    
    if not username:
        username = Prompt.ask("[bold]Snapchat username[/bold]")
    
    if not password:
        password = Prompt.ask("[bold]Snapchat password[/bold]", password=True)
    
    bot = SnapchatBot(username, password)
    if bot.authenticate():
        if save:
            confirm = Confirm.ask("Save credentials?", default=False)
            if confirm:
                save_credentials(username, password, bot.auth_token)
        
        console.print("\n[bold green]🎉 Login successful![/bold green]")
    else:
        raise typer.Exit(code=1)


@app.command()
def send(
    recipient: str = typer.Argument(..., help="Friend username"),
    message: Optional[str] = typer.Option(None, "-m", "--message", help="Text message to send"),
    picture: Optional[str] = typer.Option(None, "-p", "--picture", help="Path to picture file"),
    username: Optional[str] = typer.Option(None, "-u", "--username", help="Your username"),
    password: Optional[str] = typer.Option(None, "-pw", "--password", help="Your password"),
):
    """Send a message or picture to a friend."""
    
    if not message and not picture:
        console.print("[bold red]Error: Must provide either --message or --picture[/bold red]")
        raise typer.Exit(code=1)
    
    credentials = load_credentials()
    if not username and credentials:
        username = credentials.get('username')
    
    if not username:
        username = Prompt.ask("[bold]Your Snapchat username[/bold]")
    
    if not password and credentials and credentials.get('username') == username:
        password = credentials.get('password')
    
    if not password:
        password = Prompt.ask("[bold]Your Snapchat password[/bold]", password=True)
    
    bot = SnapchatBot(username, password)
    if bot.authenticate():
        if message:
            bot.send_message(recipient, message)
        if picture:
            bot.send_picture(recipient, picture)
    else:
        raise typer.Exit(code=1)


@app.command()
def friends(
    username: Optional[str] = typer.Option(None, "-u", "--username", help="Your username"),
    password: Optional[str] = typer.Option(None, "-pw", "--password", help="Your password"),
    limit: int = typer.Option(20, "-l", "--limit", help="Number of friends to show"),
):
    """List your Snapchat friends."""
    
    credentials = load_credentials()
    if not username and credentials:
        username = credentials.get('username')
    
    if not username:
        username = Prompt.ask("[bold]Your Snapchat username[/bold]")
    
    if not password and credentials and credentials.get('username') == username:
        password = credentials.get('password')
    
    if not password:
        password = Prompt.ask("[bold]Your Snapchat password[/bold]", password=True)
    
    bot = SnapchatBot(username, password)
    if bot.authenticate():
        console.print("\n[bold]Fetching friends...[/bold]")
        friends_list = bot.get_friends()
        
        if friends_list:
            table = Table(title=f"Your Snapchat Friends ({len(friends_list)})")
            table.add_column("#", style="dim")
            table.add_column("Username", style="cyan")
            table.add_column("Display Name", style="green")
            
            for i, friend in enumerate(friends_list[:limit], 1):
                username_str = friend.get('username', 'N/A') if isinstance(friend, dict) else str(friend)
                display_name = friend.get('display_name', '') if isinstance(friend, dict) else ''
                table.add_row(str(i), username_str, display_name)
            
            console.print(table)
        else:
            console.print("[bold yellow]No friends found[/bold yellow]")
    else:
        raise typer.Exit(code=1)


@app.command()
def config(
    show: bool = typer.Option(False, "-s", "--show", help="Show current config"),
    auto_login: Optional[bool] = typer.Option(None, "-a", "--auto-login", help="Enable auto-login"),
    debug: Optional[bool] = typer.Option(None, "-d", "--debug", help="Enable debug mode"),
):
    """Manage SnapBot configuration."""
    
    config = load_config()
    
    if show:
        console.print("[bold]Current Configuration:[/bold]")
        for key, value in config.items():
            console.print(f"  {key}: {value}")
        return
    
    if auto_login is not None:
        config['auto_login'] = auto_login
        console.print(f"[bold]Auto-login:[/bold] {auto_login}")
    
    if debug is not None:
        config['debug'] = debug
        console.print(f"[bold]Debug mode:[/bold] {debug}")
    
    if auto_login is not None or debug is not None:
        save_config(config)
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
def version():
    """Show version information."""
    console.print(f"[bold]SnapBot[/bold] v{SCRIPT_VERSION}")
    console.print("Snapchat REST API Integration Tool")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--help"])
    # If only 'config' is provided without options, show config help
    elif len(sys.argv) == 2 and sys.argv[1] == "config":
        sys.argv.append("--help")
    app()
