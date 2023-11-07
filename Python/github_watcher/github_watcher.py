import requests, tabulate, json, os, sys
from bs4 import BeautifulSoup

# Github repos to watch
repos = {
    'Grocy'                    : 'https://github.com/grocy/grocy',
    'wallpanel.xyz'            : 'https://github.com/TheTimeWalker/wallpanel-android',
    'Home Assistant: Variables': 'https://github.com/snarky-snark/home-assistant-variables',
    'Home Assistant: Birthdays': 'https://github.com/Miicroo/ha-birthdays',
    'php-api'                  : 'https://github.com/Darknetzz/php-api',
    'php-rand'                 : 'https://github.com/Darknetzz/php-rand',
    'JS.Wiki'                  : 'https://github.com/Requarks/wiki',
    'Python Flask'             : 'https://github.com/pallets/flask',
    'Python Rich'              : 'https://github.com/Textualize/rich',
    'Windows Terminal'         : 'https://github.com/microsoft/terminal/',
    'Spiderfoot'               : 'https://github.com/smicallef/spiderfoot/',
    'PHPMyAdmin'               : 'https://github.com/phpmyadmin/phpmyadmin',
    'DokuWiki'                 : 'https://github.com/dokuwiki/dokuwiki',
    'Pi-Hole'                  : 'https://github.com/pi-hole/pi-hole/',
}

# Fetch from file to see if updated
current = {}
file    = os.path.basename(__file__.split('.')[0])+'.json'
if os.path.isfile(file):
    with open(file, 'r') as fcontents:
        current = json.load(fcontents)

print(f"Checking file {file}")

headers = ['Name', 'Current tag', 'Last tag', 'Date', 'New']
rows    = []
toadd   = {}
changes = False

for repo in repos:
    # Fetch latest release for this repo
    url     = repos[repo]
    name    = url.split('/')[-1]
    latest  = url+'/releases/latest'
    
    print(f"Fetching {name}...")
    req     = requests.get(latest)
    tag     = req.url.split('/')[-1]
    
    # No releases for this repo
    if tag == "releases":
        print(f"[WARNING] {name} has no release.")
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
        print(f"[WARNING] No date for {name}.")
        date = ""
    
    # Append to table
    rows.append([repo, tag, lasttag, date, new])
    
print('\n\n'+tabulate.tabulate(rows, headers=headers))

if changes != True:
    print("No new releases, exiting...")
    exit()
    
save = input(f"Save these tags to {file}? [Y/n]")
if save.lower() != 'y' and save != '':
    print("Exiting...")
    exit()
    
with open(file, 'w+') as fcontents:
    fcontents.write(json.dumps(toadd))
    print("File saved!")