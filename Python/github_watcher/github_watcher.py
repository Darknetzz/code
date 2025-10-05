# ─────────────────────────────────────────────────────────────────────── #
#                                 Imports                                 #
# ─────────────────────────────────────────────────────────────────────── #
import requests, json, os, time, sys
from bs4 import BeautifulSoup
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.columns import Columns
import rich
import argparse
import re

# ─────────────────────────────────────────────────────────────────────── #
#                                                                         #
#                               SCRIPT START                              #
#                                                                         #
# ─────────────────────────────────────────────────────────────────────── #
def github_watcher(stream=False):
    import requests, json, os, time, sys
    from bs4 import BeautifulSoup
    from pathlib import Path

    # ─────────────────────────────────────────────────────────────────────── #
    #                                Variables                                #
    # ─────────────────────────────────────────────────────────────────────── #

    # Start timer
    start = time.time()

    # Rich table
    headers      = ['#', 'Repo', 'Current release', 'Date', 'Current tag', 'Date'] # , 'Last tag', 'Last release']
    rows         = []
    toadd        = {}

    print("Initializing rich console...")

    complete    = False
    outputfile  = os.path.dirname(__file__) + os.sep + "templates" + os.sep + "output.html"

    if not os.path.isfile(outputfile):
        print(f"Output file {outputfile} does not exist, creating...")
        Path(outputfile).touch(exist_ok=True)

    with open(outputfile, "w+", encoding="UTF-8") as f:
        console     = Console(record=True)
        console.log(f"Initializing github_watcher...")

    # JSON files
    versionsFile = "github_watcher.json"
    reposFile    = "repos.json"
    with open(reposFile, 'r') as f: 
        repos = json.load(f)

    # Set working directory to script directory
    cwd = os.path.dirname(__file__)
    print(f"Changing cwd to {cwd}")
    os.chdir(cwd)

    # Init rich console
    print("Initializing rich console...")
    console = Console(record=True)

    # ─────────────────────────────────────────────────────────────────────── #
    #                               Script info                               #
    # ─────────────────────────────────────────────────────────────────────── #
    script_name    = "github_watcher"
    script_file    = os.path.basename(__file__)
    script_author  = "Kristian Røste"
    script_version = "1.0.1"
    script_date    = time.strftime("%d.%m.%Y")
    script_desc    = f"Monitors github repos found in the JSON repos file `{reposFile}` file for new releases."
    script_usage   = "python github_watcher.py -o -s -f \"templates/output.html\""
    script_epilog  = "Made with ❤️ by Kristian Røste"

    # ─────────────────────────────────────────────────────────────────────── #
    #                                 Argparse                                #
    # ─────────────────────────────────────────────────────────────────────── #
    parser = argparse.ArgumentParser(
        prog=script_name,
        description=script_desc,
        epilog=script_epilog,
    )

    # ─────────────────────────────────────────────────────────────────────── #
    #                                Functions                                #
    # ─────────────────────────────────────────────────────────────────────── #
    
    
    # ─────────────────────────────── writeLog ────────────────────────────── #
    # Write to console and file if args.output is True
    def writeLog(txt: str):

        # Write to file if args.output is True
        if args.output:
            
            outputfile = "templates/output.html"
            if args.outputfile:
                outputfile = args.outputfile

            with open(outputfile, "w+", encoding="UTF-8") as f:
                f.write(txt)
        
        # Yield to console if args.stream is True
        if args.stream:
            yield console.print(txt)
            
        return txt # Add a return statement to fix the "Expression value is unused" problem


    # ──────────────────────────────── Styles ─────────────────────────────── #
    def warn(txt: str):
        text = f"[bold yellow]{txt}[/bold yellow]"
        console.print(text)
        writeLog(text)

    def err(txt: str):
        text = f"[bold red]{txt}[/bold red]"
        console.print(text)
        writeLog(text)

    def succ(txt: str):
        text = f"[bold green]{txt}[/bold green]"
        console.print(text)
        writeLog(text)

    def info(txt: str):
        text = f"[bold blue]{txt}[/bold blue]"
        console.print(text)
        writeLog(text)    
    
    # ──────────────────────────────── Fetch ──────────────────────────────── #
    def fetch(url: str):
        req  = requests.get(url)
        
        if not req:
            data = {
                'data': req,
                'content': "",
                'url': ""
            }
        else:
            content = req.content.decode(errors='ignore')
            url     = req.url
            
            data = {
                'data': req,
                'content': content,
                'url': url
            }
        
        return data

    
    # ───────────────────────────────── Find ──────────────────────────────── #
    def find(req: requests.Response, tagname: str, attributes: dict = {}):
        try:
            soup = BeautifulSoup(req.content, "html.parser")
            res  = soup.find(name=tagname, attrs=attributes)

            # No results
            if not res:
                # warn(f"No results for tag {tagname} with attributes {attributes} in {req.url}")
                return False

            res = res.get_text(strip=True)
            printv(f"Found {res} in {req.url}")
            return res
        except Exception as e:
            printv(f"[bold]find():[/bold] [red]{e}[/red]")
            return False


    # ──────────────────────────────── printv ─────────────────────────────── #
    def printv(txt: str):
        write = f"[yellow][DEBUG][/yellow] {txt}"
        if verbose == True:
            console.log(write)

    # ──────────────────────────────── addRepo ────────────────────────────── #
    def addRepo(url = None):
        print(f"Add a new repo to {reposFile}:")

        while url == None or url == "":
            url   = input("Enter the URL of the repo: ")

        # Add a trailing slash to URL
        if url[-1] != '/':
            url += '/'

        url         = os.path.dirname(url) # Remove trailing slash
        url_split   = url.split('/')
        user        = url_split[-2]
        repo        = url_split[-1]
        defaultName = f"{user}/{repo}"

        if not user or not repo:
            print("Invalid URL provided!")
            exit(1)

        name = input(f"[optional] Enter the name of the repo (default: {defaultName}): ")
        if name == None or name == "":
            name = defaultName
        
        if url in repos.values() or name in repos.keys():
            print("The provided URL is already in the reposFile!")
            exit(1)

        repos[name] = url
        with open(reposFile, 'w') as w:
            json.dump(repos, w, indent=4)
        print(f"Added repo {name} ({reposFile})!")

    # ────────────────────────────── deleteRepo ───────────────────────────── #
    def deleteRepo(name = None):
        print(f"Delete a repo from {reposFile}:")

        while name == None or name == "":
            name = input("Enter the name of the repo to delete: ")

        if name == None or name == "" or name not in repos.keys():
            print(f"The repo {name} is not in the reposFile!")
            exit(1)

        del repos[name]
        with open(reposFile, 'w') as w:
            json.dump(repos, w, indent=4)
        print(f"Deleted repo {name} ({reposFile})!")


    # ─────────────────────────────────────────────────────────────────────── #
    #                                ARGUMENTS                                #
    # ─────────────────────────────────────────────────────────────────────── #
    # Output options
    parser.add_argument('-w', '--wait', type=int, default='1', help='Seconds to wait between each request (default 1)')
    parser.add_argument('-o', '--output', action='store_true', help='Output to file')
    parser.add_argument('-f', '--outputfile', type=str, help='Output filepath')
    parser.add_argument('-s', '--stream', action='store_true', help='Stream output to console')
    parser.add_argument('-l', '--list', action='store_true', help='List all repos in the repos.json file (no checking is done)')

    # Misc
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {script_version}')
    parser.add_argument('--verbose', action='store_true', help='Verbose mode')

    # New stuff
    parser.add_argument('-d', '--delete', action='store_true', help='Delete a repo from the list')
    parser.add_argument('-n', '--new', action='store_true', help='Add a new repo to the list')
    parser.add_argument('-u', '--url', type=str, help='URL of the repo to add')
    parser.add_argument('-r', '--repo', type=str, help='Name of the repo to add')
    
    
    args = parser.parse_args()
    
    stream  = args.stream
    verbose = args.verbose
    new     = args.new
    delete  = args.delete
    url     = args.url
    repo    = args.repo

    if args.list:
        print("Repos in repos.json:")
        rows = []
        headers = ['Name', 'URL']
        for key, value in repos.items():
            rows.append([key, value])
        table = Table(title="Repos in repos.json")
        for header in headers:
            table.add_column(header)
        for row in rows:
            table.add_row(*row)
        console.print(table)
        exit(0)
        
    if verbose == True:
        console.print(f"[bold]DEBUG MODE ACTIVE! (args.verbose == {verbose})[/bold]")
        
    if stream == True:
        console.print(f"[bold]STREAM MODE ACTIVE! (args.stream == {stream})[/bold]")

    # NOTE: ADD
    if new:
        addRepo()
    
    # NOTE: DELETE
    if delete: 
        deleteRepo()



    # ─────────────────────────────────────────────────────────────────────── #
    #                               Start script                              #
    # ─────────────────────────────────────────────────────────────────────── #    
    
    # Read the reposFile file
    with open(reposFile, 'r') as file:
        repos = json.load(file)

    count        = len(repos)
        
    printv(f"Found {count} repos in {reposFile}")
    printv(f"JSON file {reposFile}")
    printv(f"JSON file contents:\n{repos}")

    # Check for duplicates
    duplicates = [key for key, values in repos.items() if len(values) > 1]

    # Fetch from github_watcher.json file to see if updated
    current = {}
    file    = os.path.basename(__file__.split('.')[0])+'.json'
    fullpath= os.path.join(f"{cwd}/{file}")
    if os.path.isfile(fullpath):
        with open(fullpath, 'r') as fcontents:
            current = json.load(fcontents)

    info(f"Checking file {fullpath}")
    printv(f"JSON file contents:\n{current}")

    changesCount = 0
    with console.status("[bold]Fetching repos...") as status:
        for i, repo in enumerate(repos):
            # Fetch latest release for this repo
            url          = repos[repo]
            counter      = f"({i}/{count})"
            changes      = False

            # Remove trailing slash if any
            if url[-1] == '/':
                url = url[0:-1]

            # Get last segment of URL
            name         = url.split('/')[-1]
            author       = url.split('/')[-2]
            latestUrl    = url+'/releases/latest'
            latestTagUrl = url+'/tags'
            repoInfo     = f"[{author}/{repo}]"

            # This repo doesn't have a name, skip it.
            if not name:
                warn(f"{counter} Name empty for {repo} @ {url}, skipping...")
                continue
            
            # Get latest release
            req_rel = fetch(latestUrl)
            req_tag = fetch(latestTagUrl)
            
            if not req_rel and not req_tag:
                err(f"Failed to fetch latest release/tag for {repo}")
                exit(1)
            
            # tag = f"{req['url'].split('/')[-1]}"
            tag_rel = find(req_rel['data'], "h1", {"class" : "d-inline mr-3"})
            tag_tag = find(req_tag['data'], "a", {"class" : "Link--primary Link"})
            # No releases for this repo, check tags
            # if tag == "releases":
            #     tag = find(req_rel['data'], "a", {"class" : "Link--primary Link"})
            # else:
            #     req = fetch(latestTagUrl)
            #     tag = find(req['data'], "a", {"class" : "Link--primary Link"})
                
            # No tag for this repo
            if not tag_rel and not tag_tag:
                warn(f"{counter} - Found no release or tag for {repo}")
                tag_rel     = "None"
                tag_tag     = "None"
                lastrel     = "None"
                lasttag     = "None"
                date_rel    = "None"
                date_tag    = "None"
            # Check with file
            else:
                lastrel = "None"
                lasttag = "None"

                # Check if repo is in current
                if repo in current:
                    lastrel = f"{current[repo]['release']}"
                    lasttag = f"{current[repo]['tag']}"

                # Check if tag is different from last tag
                if lasttag != tag_tag:
                    changes = True
                    succ(f"{counter} - [bold green]Changes detected for [link={url}]{repo}[/link]![/bold green]")
                else:
                    info(f"{counter} - No changes for [link={url}]{repo}[/link]")

                date_rel = find(req_rel["data"], "relative-time")
                date_tag = find(req_tag["data"], "relative-time")

                # NOTE: Shorten code, put common variables here
                # (variables that are the same regardless of conditions)
                toadd[repo] = {
                    'release': tag_rel,
                    'tag': tag_tag,
                    'date_rel': date_rel,
                    'date_req': date_tag,
                    'last_tag': lasttag,
                    'last_rel': lastrel,
                }
                printv(f"Repo: {repo}")
                printv(f"URL: {url}")
                printv(f"Tag (release): {tag_rel}")
                printv(f"Tag: {tag_tag}")
                printv(f"Last tag: {lasttag}")
                printv(f"Date (release): {date_rel}")
                printv(f"Date (tag): {date_tag}")

            # Set table_* variables
            table_new      = ""
            table_rel      = f"{tag_rel}"
            table_tag      = f"{tag_tag}"
            table_lastrel  = f"{lastrel}"
            table_lasttag  = f"{lasttag}"
            table_date_rel = f"{date_rel}"
            table_date_tag = f"{date_tag}"
            
            # Format values if changes == True
            if changes == True:
                    table_new      = "[bold green]NEW[/bold green]"
                    table_rel      = f"[bold green]{tag_rel}[/bold green] [strike]{lastrel}[/strike]"
                    table_tag      = f"[bold green]{tag_tag}[/bold green] [strike]{lasttag}[/strike]"
                    # table_lastrel  = f"[strike]{lastrel}[/strike]"
                    # table_lasttag  = f"[strike]{lasttag}[/strike]"
                    table_date_tag = f"[bold green]{date_tag}[/bold green]"
                    table_date_rel = f"[bold green]{date_rel}[/bold green]"
                    changesCount += 1
            
            # Append to table
            values = [
                f"#{i}",
                f"[link={url}]{repo}[/link] {table_new}",
                f"{table_rel}",
                f"{table_date_rel}",
                f"{table_tag}",
                f"{table_date_tag}",
                # f"{table_lasttag}",
                # f"{table_lastrel}",
            ]
            values = list(map(str.strip, values))
            rows.append(values)
            time.sleep(args.wait)

    writeLog('\n\n')

    table = Table(title="GitHub Repo Overview")

    for header in headers:
        table.add_column(header)

    for row in rows:
        table.add_row(*row)

    console.print(table)
    end = time.time()
    printv(f"Script took {end-start} seconds to complete")
    
    print(f"{changesCount} new releases found!")
    
    if changesCount == 0:
        info("No new releases, exiting...")
        return

    # TODO: This isn't working...
    printv(f"Adding JSON:\n {toadd}")
    save = input(f"Save these tags to {file}? [Y/n]")
    if save.lower() != 'y' and save != '':
        info("Exiting...")
        return

    with open(fullpath, 'w+') as fcontents:
        fcontents.write(json.dumps(toadd))
        succ("File saved!")
# ─────────────────────────────────────────────────────────────────────── #


if __name__ == "__main__":   
    print("Initializing github_watcher...")
    try:
        github_watcher()
    except KeyboardInterrupt:
        print("Exiting...")
    except Exception as e:
        import traceback
        print(f"Oh no! Something went wrong: {e}")
        print(f"Traceback:\n{traceback.print_exc()}")