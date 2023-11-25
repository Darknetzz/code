def github_watcher(stream=False):
    import requests, json, os, time, sys
    from bs4 import BeautifulSoup

    from rich.console import Console
    from rich.style import Style
    from rich.table import Table
    # from rich import print
    import rich

    cwd = os.path.dirname(__file__)
    print(f"Changing cwd to {cwd}")
    os.chdir(cwd)
    print("Initializing rich console...")

    complete    = False
    outputfile  = "templates/output.html"
    
    with open(outputfile, "w+", encoding="UTF-8") as f:
        console     = Console(record=True)
        console.log(f"Initializing github_watcher...")

        def stream(output: str):
            if complete == False and stream == True:
                yield output
            else:
                return output
       
       # Write to console as well
        def write_output():
           return
           try:
                # UnicodeEncodeError: 'charmap' codec can't encode character '\u280b' in position 313: character maps to <undefined>
                html = console.export_html(inline_styles=True, clear=False)#.encode(errors="ignore")
                console.save_html()
                f.write(f"{str(html)}\n")
           except Exception as e:
               exit(f"Error in write_output: {e}")
           
        def log(txt: str):
           console.print(txt)
           write_output()
           
        def warn(txt: str):
           log(f"[bold red]{txt}[/bold red]")

        def succ(txt: str):
           log(f"[bold green]{txt}[/bold green]")

        def info(txt: str):
           log(f"[cyan]{txt}[/cyan]")

        def fetch(url: str):
           req = requests.get(url)
           return req
           return {
               'content': req.content.decode(errors='ignore'),
               'url':     req.url
           }

        def find(req: requests.Response, tagname: str, attributes: dict = {}):
           # Init soup
           try:
               soup = BeautifulSoup(req.content, "html.parser")
               res  = soup.find(name=tagname, attrs=attributes)

               # No results
               if not res:
                   # warn(f"No results for tag {tagname} with attributes {attributes} in {req.url}")
                   return False

               res = res.get_text(strip=True)
               # succ(f"Found {res} in {req.url}")
               return res
           except Exception as e:
               # warn(f"find: Exception {e}")
               return False

        # Github repos to watch
        repos = {
            'Grocy'                         : 'https://github.com/grocy/grocy',
            'wallpanel.xyz'                 : 'https://github.com/TheTimeWalker/wallpanel-android',
            'Home Assistant: Core'          : 'https://github.com/home-assistant/core',
            'Home Assistant: Supervisor'    : 'https://github.com/home-assistant/supervisor',
            'Home Assistant: OS'            : 'https://github.com/home-assistant/operating-system',
            'Home Assistant: Variables'     : 'https://github.com/snarky-snark/home-assistant-variables',
            'Home Assistant: Birthdays'     : 'https://github.com/Miicroo/ha-birthdays',
            'Home Assistant: browser-mod'   : 'https://github.com/thomasloven/hass-browser_mod',
            'php-api'                       : 'https://github.com/Darknetzz/php-api',
            'php-rand'                      : 'https://github.com/Darknetzz/php-rand',
            'JS.Wiki'                       : 'https://github.com/Requarks/wiki',
            'Python Flask'                  : 'https://github.com/pallets/flask',
            'Python Rich'                   : 'https://github.com/Textualize/rich',
            'Windows Terminal'              : 'https://github.com/microsoft/terminal/',
            'PowerShell 7'                  : 'https://github.com/PowerShell/PowerShell',
            'Spiderfoot'                    : 'https://github.com/smicallef/spiderfoot/',
            'PHPMyAdmin'                    : 'https://github.com/phpmyadmin/phpmyadmin',
            'DokuWiki'                      : 'https://github.com/dokuwiki/dokuwiki',
            'Pi-Hole DNS'                   : 'https://github.com/pi-hole/pi-hole/',
            'Pi-Hole FTL'                   : 'https://github.com/pi-hole/FTL/',
            'Pi-Hole Web'                   : 'https://github.com/pi-hole/web',
            'Bootstrap'                     : 'https://github.com/twbs/bootstrap',
            'Bootstrap-Icons'               : 'https://github.com/twbs/icons',
            'jQuery'                        : 'https://github.com/jquery/jquery',
            'Obsidian.md'                   : 'https://github.com/obsidianmd/obsidian-releases',
            'OPNSense Core'                 : 'https://github.com/opnsense/core',
            'Apache2'                       : 'https://github.com/apache/httpd',
            'Nginx'                         : 'https://github.com/nginx/nginx',
            'Quasar RAT'                    : 'https://github.com/quasar/Quasar',
            'Explorer Patcher'              : 'https://github.com/valinet/ExplorerPatcher/',
            'VSCode'                        : 'https://github.com/microsoft/vscode',
            'Flipper Zero RougeMaster FW'   : 'https://github.com/RogueMaster/flipperzero-firmware-wPlugins',
            'Ventoy'                        : 'https://github.com/ventoy/Ventoy',
            'SnipeIT Asset Management'      : 'https://github.com/snipe/snipe-it',
            'Pterodactyl Panel'             : 'https://github.com/pterodactyl/panel',
            'Pterodactyl Wings'             : 'https://github.com/pterodactyl/wings',
            'Microsoft-Activation-Scripts'  : 'https://github.com/massgravel/Microsoft-Activation-Scripts',
            'Canonical Subiquity'           : 'https://github.com/canonical/subiquity',
        }
        
        # Check for duplicates
        duplicates = [key for key, values in repos.items() if len(values) > 1]

        # Fetch from file to see if updated
        current = {}
        file    = os.path.basename(__file__.split('.')[0])+'.json'
        fullpath= os.path.join(f"{cwd}/{file}")
        if os.path.isfile(fullpath):
            with open(fullpath, 'r') as fcontents:
                current = json.load(fcontents)

        info(f"Checking file {fullpath}")

        headers = ['Name', 'Current tag', 'Last tag', 'Date', 'New']
        rows    = []
        toadd   = {}
        changes = False
        count   = len(repos)

        with console.status("[bold]Fetching repos...") as status:
           for i, repo in enumerate(repos):
               # Fetch latest release for this repo
               url     = repos[repo]
               counter = f"({i}/{count})"

               # Remove trailing slash if any
               if url[-1] == '/':
                   url = url[0:-1]

               # Get last segment of URL
               name         = url.split('/')[-1]
               author       = url.split('/')[-2]
               latestUrl    = url+'/releases/latest'
               latestTagUrl = url+'/tags'
               repoInfo     = f"[{author}/{repo}]"

               if not name:
                   warn(f"{counter} Name empty for {repo} @ {url}, skipping...")
                   continue
               
               # Get latest release
               req     = fetch(latestUrl)
               tag     = f"{req.url.split('/')[-1]}"

               # No releases for this repo, check tags
               if tag == "releases":
                   req = fetch(latestTagUrl)
                   tag = find(req, "a", {"class" : "Link--primary Link"})

               # No tag for this repo
               if not tag:
                   warn(f"Found no release or tag for {author}/{name}")
                   tag         = "None"
                   lasttag     = "None"
                   new         = ""
               else:
                   # Check with file
                   lasttag     = "None"
                   new         = ""

                    
                   if repo in current:
                       lasttag = f"{current[repo]}"

                   if lasttag != tag:
                       new     = "[bold green]NEW[/bold green]"
                       changes = True
                       succ(f"{counter} Changes detected for {repo}!")
                   else:
                       info(f"{counter} No changes {repo}")
                        

                   # NOTE: Shorten code, put common variables here
                   # (variables that are the same regardless of conditions)
                   toadd[repo] = tag

                   # Find date (this should be the same regardless of release/tag)
                   date = find(req, "relative-time")

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
               time.sleep(0.5)

        log('\n\n')

        table = Table(title="GitHub Repo Overview")

        for header in headers:
            table.add_column(header)

        for row in rows:
                table.add_row(*row)

        console.print(table)

        if changes != True:
            info("No new releases, exiting...")
            return

        save = input(f"Save these tags to {file}? [Y/n]")
        if save.lower() != 'y' and save != '':
            info("Exiting...")
            return

        with open(fullpath, 'w+') as fcontents:
           fcontents.write(json.dumps(toadd))
           succ("File saved!")
        
if __name__ == "__main__":
    try:
        print("Starting github_watcher...")
        github_watcher()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        print(f"Oh no! Something went wrong: {e}")