# test123
try:
    import utils.importer as imp
except:
    exit("You need the utils.importer for this script to function. You can find it here: https://github.com/Darknetzz/code/tree/main/Python/utils")

packages = [
    "os", "getpass", "socket", "shutil", "shlex",
    "subprocess", "re", "pyperclip", "time",
]

for p in packages:
    globals()[p] = imp.importer_import_new(p)

tk = imp.importer_import_new("tkinter")


# import tkinter as tk
# import os, getpass, socket, shutil, shlex, subprocess, re, pyperclip, time

client = socket.gethostbyname_ex(socket.getfqdn())
ip = str(client[2])
fqdn = str(client[0])
whoami = getpass.getuser()
shell = "pwsh -Command"
lastcmd = []
currlast = 0
shell_log = "\n"

# ---------------------------------------------------------------------------- #
#                            Configuration variables                           #
# ---------------------------------------------------------------------------- #
cfg = {
    "bgcolor"      : "Black"   , # background
    "fgcolor"      : "Green"   , # foreground
    "hbgcolor"     : "Green"   , # cursor
    "font"         : "Consolas", # font
    "fontsize"     : "11"      , # font size
    "verbose"      : True      , # verbosity (prints to console, not terminal)
    "windowminsize": [700, 550],
    "windowsize"   : "800x600" , 
    "windowtitle"  : "Terminal", 
    "removeansi"   : True,
}

startupText = f"""

___________                  .__              .__   
\__    ___/__________  _____ |__| ____ _____  |  |  
  |    |_/ __ \_  __ \/     \|  |/    \\__  \ |  |  
  |    |\  ___/|  | \/  Y Y  \  |   |  \/ __ \|  |__
  |____| \___  >__|  |__|_|  /__|___|  (____  /____/
             \/            \/        \/     \/      
------------------------------------
Client: {fqdn} ({ip})
Current user: {whoami}
Shell: {shutil.which(shell.split(" ")[0])}
Verbose: {cfg['verbose']}

Type (h)alpmeplz for a list of useful commands.
------------------------------------

"""


creditsText = f"""
This cool little terminal was made by darknetzz (https://github.com/darknetzz).
Probably one of the most useless terminals you will ever encounter.
Have fun!
"""



# ---------------------------------------------------------------------------- #
#                                 Verbose print                                #
# ---------------------------------------------------------------------------- #
def vprint(txt):
    if cfg["verbose"] == True:
        print(txt)

# ---------------------------------------------------------------------------- #
#                    Highlight text (can be removed I think)                   #
# ---------------------------------------------------------------------------- #
# def highlighter():
#     highlightWords = {
#         f"[{shell}]": "Pink",
#     }

#     for k,v in highlightWords.items(): # iterate over dict
#         startIndex = "1.0"

#         while True:
#             startIndex = widgets["outputText"].search(k, startIndex, tk.END) # search for occurence of k
#             if startIndex:
#                 endIndex = widgets["outputText"].index('%s+%dc' % (startIndex, (len(k)))) # find end of k
#                 widgets["outputText"].tag_add(k, startIndex, endIndex) # add tag to k
#                 widgets["outputText"].tag_config(k, foreground=v)      # and color it with v
#                 startIndex = endIndex # reset startIndex to continue searching
#             else:
#                 break

# ---------------------------------------------------------------------------- #
#               Simple function to run and return shell commands               #
# ---------------------------------------------------------------------------- #
def runcmd(cmd, background=False):
    construct = shlex.split(f"{shell} {cmd}")

    if background == True:
        construct = subprocess.Popen(construct)
        return

    construct = subprocess.Popen(
        construct, 
        shell=True, 
        # encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate()

    stdout = construct[0].decode()
    stderr = construct[1].decode()

    if stderr != None and stderr != "":
        return stderr
    return stdout

# ---------------------------------------------------------------------------- #
#                          When a command is submitted                         #
# ---------------------------------------------------------------------------- #
def enter():
    global lastcmd
    global shell_log
    global currlast
    cmd = widgets["inputEntry"].get("1.0", tk.END).strip()
    setText(widgets["inputEntry"])
    lastcmd.append(cmd)
    currlast = len(lastcmd)-1 if len(lastcmd) > 0 else 0 # (this is useless because lastcmd will never be less than 0)
    shell_log += "\n"+cmd

    if cmd == "":
        return
    appendToOutput(f"> {cmd}")
    
    for customcmd in customCommands:
        aliases        = customcmd[0]
        functionToCall = customcmd[1]
        for alias in aliases:
            if cmd.split(" ", 1)[0] == alias:
                # call the related function and return
                # globals()[functionToCall](cmd)
                globals()["runCustomFunction"](cmd, functionToCall)
                return
        
    try:
        output = runcmd(cmd)
        if output == "":
            appendToOutput("[Empty response]")
            return
        appendToOutput(f"{output}")
        return
    except Exception as e:
        # vprint(f"Command: {cmd}")
        appendToOutput(f"[WARNING] Unknown command ({e})")
        return

def setText(e, text = ""):
    e.delete(1.0,tk.END)
    e.insert(1.0,text)
    return


def appendToOutput(text):
    if cfg["removeansi"] == True:
        ansi = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi.sub('', text)
    widgets["outputText"].config(state=tk.NORMAL)
    text = text.strip()
    widgets["outputText"].insert(tk.END, f"\n{text}")
    widgets["outputText"].see(tk.END)
    widgets["outputText"].config(state=tk.DISABLED)

def shellNotFound():
    global shell
    shell = ""
    appendToOutput(f"""
Your shell was not found, resetting to default.
Please choose your shell by typing \"cs [SHELL] [PARAM]\"
For example:
    cs pwsh -Command
    cs python -c
""")
    
# Arrow up
# To do arrow up, there must be a previously typed command
# It should fill the textbox, and set the currlast counter to -1
def getlastcmd():
    global currlast

    if len(lastcmd) < 1:
        vprint(f"lastcmd array empty")
        return
    
    vprint(f"getlastcmd | {currlast}/{len(lastcmd)}")

    if currlast < len(lastcmd):
        setText(widgets["inputEntry"], lastcmd[currlast])
        widgets["inputEntry"].focus()
        if currlast > 0:
            currlast-=1
    else:
        vprint(f"Attempting to get index {currlast} of lastcmd with {len(lastcmd)} indexes (which doesn't exist)")
        vprint(lastcmd)

# Arrow down
# It should show the next item in the lastcmd array, except if currlast is the last item in the array, then it should blank out
def getnextcmd():
    global currlast

    if len(lastcmd) < 1:
        vprint(f"lastcmd array empty")
        return

    vprint(f"getnextcmd | {currlast}/{len(lastcmd)}")

    if currlast < len(lastcmd):
        setText(widgets["inputEntry"], lastcmd[currlast])
        widgets["inputEntry"].focus()
        currlast+=1
    else:
        currlast=0
        setText(widgets["inputEntry"], "")

def copypaste():

    # Copy
    if window.focus_get() == widgets["outputText"]:
        selection = widgets["outputText"].selection_get()

        if selection != None:
            pyperclip.copy(selection)
            setText(widgets["inputEntry"], selection)
            vprint("Copied!")

    # Paste
    if window.focus_get() == widgets["inputEntry"]:
        if pyperclip.paste() != None:
            currentText = widgets["inputEntry"].get("1.0",tk.END)
            setText(widgets["inputEntry"], f"{currentText+pyperclip.paste()}")
            vprint(f"Pasted!")

# GUI update (runs every second)
def guiUpdate():
    x = window.winfo_width()
    y = window.winfo_height()
    now = time.strftime("%H:%M:%S")
    widgets["topText"].configure(text=f"[{os.getcwd()}] [{now}]")
    widgets["statusText"].configure(text=f"[{shell.split(' ')[0]}] [{cfg['font']} {cfg['fontsize']}px] [{x}x{y}]")
    window.after(1000, guiUpdate)

# # Clock update
# def update_toptext():
#     now = time.strftime("%H:%M:%S")
#     widgets["topText"].configure(text=f"[{os.getcwd()}] [{now}]")
#     window.after(1000, update_toptext)

# # Top update
# def update_statustext():
#     x = window.winfo_width()
#     y = window.winfo_height()
#     widgets["statusText"].configure(text=f"[{shell.split(' ')[0]}] [{cfg['font']} {cfg['fontsize']}px] [{x}x{y}]")
#     window.after(1000, update_statustext)

# ---------------------------------------------------------------------------- #
#                                Custom commands                               #
# ---------------------------------------------------------------------------- #

# Constructor/helper for custom functions
def runCustomFunction(cmd="", functionToRun=None):
    vprint(f"Attempting to run custom function {functionToRun}")
    setText(widgets["inputEntry"])
    widgets["inputEntry"].focus()
    if functionToRun != None:
        globals()[functionToRun](cmd)


def clearOutput(cmd=""):
    widgets["outputText"].config(state=tk.NORMAL)
    widgets["outputText"].delete(1.0,tk.END)
    widgets["outputText"].config(state=tk.DISABLED)

def startOver(cmd=""):
    clearOutput()
    appendToOutput(startupText)

def changeShell(cmd):
    global shell
    changeto = cmd[3:]
    changeto = changeto.split(" ")
    
    newshell = changeto[0]
    param    = changeto[1] if len(changeto) > 1 else None

    if newshell == "":
        appendToOutput("Usage: cs [SHELL] - Changes the current shell")
    elif shutil.which(newshell) != None:
        shell = f"{newshell} {param} "
        if newshell == "cmd":
            shell = ""
        appendToOutput(f"Shell changed to {newshell}")
    else:
        appendToOutput(f"Can't find shell {newshell}")

def log(cmd=""):
    appendToOutput(shell_log)

def clearhistory(cmd=""):
    global lastcmd
    global currlast
    lastcmd = []
    currlast = 0
    appendToOutput("History cleared!")

def dupe(cmd=""):
    if shutil.which("python"):
        thisScript = os.path.basename(__file__)
        runcmd(f"python {thisScript}", background=True)
    else:
        appendToOutput("Python not found in path. Not able to duplicate terminal.")

def showcredits(cmd=""):
    appendToOutput(creditsText)

def changecfg(cmd=""):
    appendToOutput("Coming soon!")

def exitterminal(cmd=""):
    window.destroy()
    exit()

def showCustomCommands(cmd):
    appendToOutput("""

  _          _       
 | |        | |      
 | |__   ___| |_ __  
 | '_ \ / _ \ | '_ \ 
 | | | |  __/ | |_) |
 |_| |_|\___|_| .__/ 
              | |    
              |_|    
""")
    for command in customCommands:
        aliases = command[0]
        function = command[1]
        desc = command[2]
        appendToOutput(f"{' / '.join(aliases)} - {desc}\n")

customCommands = [
    # Aliases                     # Function name                    # Description
    [["clear", "cls"]         , "clearOutput"                         , "Clear console output"]          , 
    [["init"]    , "startOver"   , "Start the console session over"]     , 
    [["cs"]      , "changeShell" , "Change the current shell"]           , 
    [["halpmeplz", "h"]          , "showCustomCommands"                  , "Show a list of custom commands"], 
    [["log"]     , "log"         , "Show shell history"]                 , 
    [["clh"]     , "clearhistory", "Clear shell history"]                , 
    [["cfg"]     , "changecfg"   , "Show config window"]                 , 
    [["dupe"]    , "dupe"        , "Spawn a new instance of terminal"]   , 
    [["credits"] , "showcredits" , "Show some uninteresting information"], 
    [["exit"     , "quit"]       , "exitterminal"                        , "Exits terminal"]                , 
]

# Window initialize
window   = tk.Tk()
# window.resizable(False, False)
window.title(cfg["windowtitle"])
window.geometry(cfg["windowsize"])
window.minsize(*cfg["windowminsize"])

frames = {}
widgets= {}

# ---------------------------------------------------------------------------- #
#                                 Frame system                                 #
# ---------------------------------------------------------------------------- #
frames["topFrame"] = tk.Frame(window, height=50, background=cfg["bgcolor"])
frames["topFrame"].pack(side=tk.TOP, fill=tk.X, expand=False)

frames["midFrame"] = tk.Frame(window, background=cfg["bgcolor"])
frames["midFrame"].pack(fill=tk.BOTH, expand=True)

frames["botFrame"] = tk.Frame(window, height=50, background=cfg["bgcolor"])
frames["botFrame"].pack(side=tk.BOTTOM, fill=tk.X, expand=False)

# ---------------------------------------------------------------------------- #
#                                   Top frame                                  #
# ---------------------------------------------------------------------------- #
widgets["topText"] = tk.Label(frames["topFrame"], font=cfg["font"])
# text=f"[{os.getcwd()}] []"
widgets["topText"].pack()

# ---------------------------------------------------------------------------- #
#                                 Middle frame                                 #
# ---------------------------------------------------------------------------- #
widgets["inputEntry"] = tk.Text(frames["midFrame"], height=2, width=40, background="Black", foreground="Green", insertbackground="Green", font=cfg["font"])
widgets["outputText"] = tk.Text(frames["midFrame"], background="Black", foreground="Green", highlightbackground="Green", font=cfg["font"])
widgets["outputText"].pack(fill=tk.BOTH, expand=True)
widgets["inputEntry"].pack(fill=tk.X, expand=False)

# ---------------------------------------------------------------------------- #
#                                 Bottom frame                                 #
# ---------------------------------------------------------------------------- #
widgets["statusText"] = tk.Label(frames["botFrame"], font=cfg["font"])
# text=f"[{shell.split(' ')[0]}] [{cfg['font']} {cfg['fontsize']}px] [{cfg['bgcolor']} on {cfg['fgcolor']}]"
widgets["statusText"].pack()

# Set config for all widgets
for widget in widgets:
    entity = widgets[widget]
    entity.config(background=cfg["bgcolor"], foreground=cfg["fgcolor"], highlightbackground=cfg["hbgcolor"])
    

# Show startup text
appendToOutput(startupText)


if shutil.which(shell.split(" ")[0]) == None or shell == "":
    shellNotFound()

window.bind('<Return>', lambda event: enter(), add="+")
window.bind('<Up>', lambda event: getlastcmd())
window.bind('<Down>', lambda event: getnextcmd())
window.bind('<ButtonRelease-3>', lambda event: copypaste())


widgets["inputEntry"].focus()
guiUpdate()

window.mainloop()