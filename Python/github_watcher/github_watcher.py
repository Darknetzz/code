import requests, json, os, sys
from bs4 import BeautifulSoup


from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich import print

console = Console()

# def print(txt):
#     return console.print(txt)

def warn(txt):
    print(f"[bold red][WARNING][/bold red] {txt}")
    
def succ(txt):
    print(f"[bold green][OK][/bold green] {txt}")
    
def info(txt):
    print(f"[cyan][INFO][/cyan] {txt}")

# Github repos to watch
repos = {
    'Grocy'                         : 'https://github.com/grocy/grocy',
    'wallpanel.xyz'                 : 'https://github.com/TheTimeWalker/wallpanel-android',
    'Home Assistant: Variables'     : 'https://github.com/snarky-snark/home-assistant-variables',
    'Home Assistant: Birthdays'     : 'https://github.com/Miicroo/ha-birthdays',
    'Home Assistant: browser-mod'   : 'https://github.com/thomasloven/hass-browser_mod',
    'php-api'                       : 'https://github.com/Darknetzz/php-api',
    'php-rand'                      : 'https://github.com/Darknetzz/php-rand',
    'JS.Wiki'                       : 'https://github.com/Requarks/wiki',
    'Python Flask'                  : 'https://github.com/pallets/flask',
    'Python Rich'                   : 'https://github.com/Textualize/rich',
    'Windows Terminal'              : 'https://github.com/microsoft/terminal/',
    'Spiderfoot'                    : 'https://github.com/smicallef/spiderfoot/',
    'PHPMyAdmin'                    : 'https://github.com/phpmyadmin/phpmyadmin',
    'DokuWiki'                      : 'https://github.com/dokuwiki/dokuwiki',
    'Pi-Hole DNS'                   : 'https://github.com/pi-hole/pi-hole/',
    'Pi-Hole FTL'                   : 'https://github.com/pi-hole/FTL/',
    'Pi-Hole Web'                   : 'https://github.com/pi-hole/web',
    'Bootstrap'                     : 'https://github.com/twbs/bootstrap',
    'Obsidian.md'                   : 'https://github.com/obsidianmd/obsidian-releases',
    'OPNSense Core'                 : 'https://github.com/opnsense/core',
    'Apache2'                       : 'https://github.com/apache/httpd',
    'Nginx'                         : 'https://github.com/nginx/nginx',
}

# Fetch from file to see if updated
current = {}
filepath= os.path.dirname(__file__)
file    = os.path.basename(__file__.split('.')[0])+'.json'
fullpath= os.path.join(f"{filepath}/{file}")
if os.path.isfile(fullpath):
    with open(fullpath, 'r') as fcontents:
        current = json.load(fcontents)

info(f"Checking file {fullpath}")

headers = ['Name', 'Current tag', 'Last tag', 'Date', 'New']
rows    = []
toadd   = {}
changes = False
count   = len(repos)

for i, repo in enumerate(repos):
    # Fetch latest release for this repo
    url     = repos[repo]
    counter = f"({i}/{count})"
    print(counter, end=' ')
    
    # Remove trailing slash if any
    if url[-1] == '/':
        url = url[0:-1]
        
    # Get last segment of URL
    name    = url.split('/')[-1]
    latest  = url+'/releases/latest'
    
    if not name:
        warn(f"Name empty for {repo} @ {url}, skipping...")
        continue
    
    req     = requests.get(latest)
    tag     = f"{req.url.split('/')[-1]}"
    
    # No releases for this repo
    if tag == "releases":
        warn(f"{name} has no release.")
        tag         = "[grey]None[/grey]"
        lasttag     = "[grey]None[/grey]"
        new         = ""
        toadd[repo] = tag
    else:
        # Check with file
        lasttag     = "None"
        new         = ""
        toadd[repo] = tag
        
        if repo in current:
            lasttag = f"{current[repo]}"
            print(f"Fetching {name}...")
            
        
        if lasttag != tag:
            new     = "[bold green]NEW[/bold green]"
            changes = True
            succ(f"Changes detected for {repo}!")
    
    # Init soup
    try:
        soup = BeautifulSoup(req.content, "html.parser")
        date = soup.find('relative-time').get_text()
    except Exception as e:
        warn(f"No date for {name}.")
        date = ""
    
    # Append to table
    values = [
        f"[link={url}]{repo}[/link]",
        f"{tag}",
        f"{lasttag}",
        f"{date}",
        f"{new}",
    ]
    values = list(map(str.strip, values))
    rows.append(values)

print('\n\n')

table = Table(title="GitHub Repo Overview")

for header in headers:
    table.add_column(header)
    
for row in rows:
        table.add_row(*row)
    
print(table)

if changes != True:
    info("No new releases, exiting...")
    exit()
    
save = input(f"Save these tags to {file}? [Y/n]")
if save.lower() != 'y' and save != '':
    info("Exiting...")
    exit()
    
with open(fullpath, 'w+') as fcontents:
    fcontents.write(json.dumps(toadd))
    succ("File saved!")