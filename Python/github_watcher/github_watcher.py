import requests, tabulate, json, os, sys
from bs4 import BeautifulSoup


from rich.console import Console
from rich.style import Style

console = Console(style = Style.parse("cyan"))

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
}

# Fetch from file to see if updated
current = {}
filepath= os.path.dirname(__file__)
file    = os.path.basename(__file__.split('.')[0])+'.json'
fullpath= os.path.join(f"{filepath}/{file}")
if os.path.isfile(fullpath):
    with open(fullpath, 'r') as fcontents:
        current = json.load(fcontents)

console.print(f"Checking file {fullpath}")

headers = ['Name', 'Current tag', 'Last tag', 'Date', 'New']
rows    = []
toadd   = {}
changes = False

for repo in repos:
    # Fetch latest release for this repo
    url     = repos[repo]
    
    # Remove trailing slash if any
    if url[-1] == '/':
        url = url[0:-1]
        
    # Get last segment of URL
    name    = url.split('/')[-1]
    latest  = url+'/releases/latest'
    
    if not name:
        print(f"[WARN] Name empty for {repo} @ {url}, skipping...")
        continue
    
    console.print(f"Fetching {name}...")
    req     = requests.get(latest)
    tag     = req.url.split('/')[-1]
    
    # No releases for this repo
    if tag == "releases":
        console.print(f"[WARNING] {name} has no release.")
        tag         = ""
        lasttag     = ""
        new         = ""
        toadd[repo] = ""
    else:
        # Check with file
        lasttag     = "None"
        new         = ""
        toadd[repo] = tag
        
        if repo in current:
            lasttag = current[repo]
        
        if lasttag != tag:
            new     = "NEW"
            changes = True
    
    # Init soup
    try:
        soup = BeautifulSoup(req.content, "html.parser")
        date = soup.find('relative-time').get_text()
    except Exception as e:
        console.print(f"[WARNING] No date for {name}.")
        date = ""
    
    # Append to table
    rows.append([repo, tag, lasttag, date, new])
    
console.print('\n\n'+tabulate.tabulate(rows, headers=headers))

if changes != True:
    console.print("No new releases, exiting...")
    exit()
    
save = input(f"Save these tags to {file}? [Y/n]")
if save.lower() != 'y' and save != '':
    console.print("Exiting...")
    exit()
    
with open(fullpath, 'w+') as fcontents:
    fcontents.write(json.dumps(toadd))
    console.print("File saved!")