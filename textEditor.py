import tkinter as tk
from tkinter.filedialog import askopenfilename, asksaveasfilename
import random

# ---------------------------------------------------------------------------- #
#                                   Constants                                  #
# ---------------------------------------------------------------------------- #
AVAILABLE_COLORS = [
    "Red",
    "Green",
    "Blue",
    "Black",
    "White",
    "Grey",
]

AVAILABLE_FONTS = [
    "Times New Roman",
    "Consolas",
    "Helvetica",
    "Arial",
    "Verdana",
    "Tahoma",
    "Trebuchet",
    "Impact",
    "Gill Sans",
]

# ---------------------------------------------------------------------------- #
#                                   OPEN FILE                                  #
# ---------------------------------------------------------------------------- #
def open_file():
    """Open a file for editing."""
    filepath = askopenfilename(
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if not filepath:
        return
    textarea.delete("1.0", tk.END)
    with open(filepath, mode="r", encoding="utf-8") as input_file:
        text = input_file.read()
        textarea.insert(tk.END, text)
    fileName.config(text=filepath)
    status.config(text=f"[FILE OPENED]", foreground="Green")

# ---------------------------------------------------------------------------- #
#                                   SAVE FILE                                  #
# ---------------------------------------------------------------------------- #
def save_file(fn = None):
    """Save the current file as a new file."""
    if fn == None or fn == "No file opened.":
        filepath = asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
    else:
        filepath = fn

    if not filepath:
        return
    with open(filepath, mode="w", encoding="utf-8") as output_file:
        text = textarea.get("1.0", tk.END)
        output_file.write(text)
    fileName.config(text=filepath)
    status.config(text=f"[FILE SAVED]", foreground="Green")

# ---------------------------------------------------------------------------- #
#                               TOGGLE DARK MODE                               #
# ---------------------------------------------------------------------------- #
def toggleDark():
    global cfg

    if cfg["bgColor"] == "Black":
        cfg["bgColor"] = "White"
        cfg['fgColor'] = "Black"
        textarea.config(background=cfg["bgColor"], foreground=cfg["fgColor"])
        toggleDarkBtn.config(text="🌚 Dark mode")
    elif cfg["bgColor"] == "White":
        cfg["bgColor"] = "Black"
        cfg['fgColor'] = "Green"
        textarea.config(background=cfg["bgColor"], foreground=cfg["fgColor"])
        toggleDarkBtn.config(text="🌞 Light mode")
    else:
        cfg["bgColor"] = "Black"
        cfg['fgColor'] = "Green"
        textarea.config(background=cfg["bgColor"], foreground=cfg["fgColor"])
        toggleDarkBtn.config(text="🌞 Light mode")
    status.config(text="[DARK MODE TOGGLED]", foreground="Green")

# ---------------------------------------------------------------------------- #
#                                 SAVE SETTINGS                                #
# ---------------------------------------------------------------------------- #
def saveSettings(savecfg, windowReference = None):
    global settingsStatus
    try:
        settingsStatus
    except:
        print("settingsStatus not set yet")
    else:
        settingsStatus.destroy()

    try:
        for settingName in savecfg:
            if len(savecfg[settingName].get()) > 0:
                cfg[settingName] = savecfg[settingName].get()
                print(f"Setting {settingName} = {cfg[settingName]}")
        textarea.config(background=cfg['bgColor'], foreground=cfg['fgColor'], insertbackground=cfg['cuColor'], font=(cfg['font'], cfg['fontSize'], cfg['fontDeco']))
        status.config(text="[SETTINGS SAVED]", foreground="Green")
        settingsOverviewText = f"[{cfg['font']}] [{cfg['fontSize']}px] [{cfg['fontDeco']}]"
        settingsOverview.config(text = settingsOverviewText)

        windowReference.destroy()
    except Exception as e:
        settingsStatus = tk.Label(windowReference, text=f"Error: {e}", foreground="Red")
        settingsStatus.pack()

# ---------------------------------------------------------------------------- #
#                                SETTINGS WINDOW                               #
# ---------------------------------------------------------------------------- #
def settings():
    global cfg
    availableSettings = [
        ["Font"            , "font"    , "font"] , 
        ["Font size"       , "fontSize", "str"]  , 
        ["Font decoration" , "fontDeco", "str"]  , 
        ["Background color", "bgColor" , "color"], 
        ["Text color"      , "fgColor" , "color"], 
        ["Cursor color"    , "cuColor" , "color"], 
        ["Disco mode"      , "disco"   , "bool"],
    ]
    savecfg = {} # the temp for storing about to be saved cfg
    showcfg = {} # only for display

    # Settings window initialize
    settingsWindow = tk.Toplevel(window)
    settingsWindow.resizable(False, False)
    # settingsWindow.geometry('500x500')
    settingsWindow.title("Settings")
    
    for i, setting in enumerate(availableSettings):
        cfgFormalName = setting[0]
        cfgName = setting[1]
        cfgType = setting[2]
        currentVal = cfg[cfgName]

        tk.Label(settingsWindow, text=cfgFormalName).grid(column=0, row=i)
        savecfg[cfgName] = tk.StringVar(settingsWindow)

        if cfgType == "str":
            savecfg[cfgName] = tk.Entry(settingsWindow)
            savecfg[cfgName].insert(0, currentVal)
            showcfg[cfgName] = savecfg[cfgName]
        
        elif cfgType == "bool":
            savecfg[cfgName].set(cfg[cfgName])
            showcfg[cfgName] = tk.Checkbutton(settingsWindow, text=cfgFormalName,variable=savecfg[cfgName], onvalue='true', offvalue='false')

        elif cfgType == "color":
            savecfg[cfgName].set(cfg[cfgName])
            showcfg[cfgName] = tk.OptionMenu(settingsWindow, savecfg[cfgName], cfg[cfgName], *AVAILABLE_COLORS)
            showcfg[cfgName].config(indicatoron=0, compound=tk.RIGHT, image=img_down, width=120)

        elif cfgType == "font":
            savecfg[cfgName].set(cfg[cfgName])
            showcfg[cfgName] = tk.OptionMenu(settingsWindow, savecfg[cfgName], cfg[cfgName], *AVAILABLE_FONTS)
            showcfg[cfgName].config(indicatoron=0, compound=tk.RIGHT, image=img_down, width=120)

        showcfg[cfgName].grid(column=1,row=i)

    settingsWindow.bind("<Return>", lambda event: saveSettings(savecfg, settingsWindow))
    tk.Button(settingsWindow, text="💾 Save", command=lambda: saveSettings(savecfg, settingsWindow)).grid(column=1,row=i+1)

# ---------------------------------------------------------------------------- #
#                                  HELP WINDOW                                 #
# ---------------------------------------------------------------------------- #
def help():
    helpWindow = tk.Toplevel(window)
    helpWindow.resizable(False, False)
    # helpWindow.geometry('500x500')
    helpWindow.title("Help")

    helpText = tk.Text(helpWindow)
    text = """
    KEYBINDS
        CTRL+S - Save
        CTRL+D - Toggle dark mode
    """
    helpText.insert(tk.END,text)
    helpText.config(state=tk.DISABLED, background=cfg['bgColor'], foreground=cfg['fgColor'])
    helpText.pack()

# ---------------------------------------------------------------------------- #
#                                     DISCO                                    #
# ---------------------------------------------------------------------------- #
def disco():
    if cfg['disco'] == 'true':
        textarea.config(background=random.choice(AVAILABLE_COLORS), foreground=random.choice(AVAILABLE_COLORS), insertbackground=random.choice(AVAILABLE_COLORS))
    window.after(500, disco)

# Settings
cfg            = {
    'font'    : 'Consolas', 
    'fontSize': '17'      , 
    'fontDeco': 'bold'    , 
    'bgColor' : 'Black'   , 
    'fgColor' : 'Green'   , 
    'cuColor' : 'Red'     , 
    'disco'   : 'false'   , 
}

settingsOverviewText = f"[{cfg['font']}] [{cfg['fontSize']}px] [{cfg['fontDeco']}]"

# Window initialize
window   = tk.Tk()
# window.resizable(False, False)
window.title("Text editor")

# Images
img_down_code = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x0e\x00\x00\x00\x07\x08\x06\x00\x00\x008G|\x19\x00\x00\x00\tpHYs\x00\x00\x10\x9b\x00\x00\x10\x9b\x01t\x89\x9cK\x00\x00\x00\x19tEXtSoftware\x00www.inkscape.org\x9b\xee<\x1a\x00\x00\x00OIDAT\x18\x95\x95\xce\xb1\x0e@P\x0cF\xe1\xefzI\x8fc$\x12\x111\x19\xec\x9e\x12\xcb\x95 A\x9d\xa4K\xff\x9e\xb6\t\x13J\xffX \xa1\xc7\x16\xac\x19\xc5\xb1!*\x8fy\xf6BB\xf7"\r_\xff77a\xcd\xbd\x10\xedI\xaa\xa3\xd2\xf9r\xf5\x14\xee^N&\x14\xab\xef\xa9\'\x00\x00\x00\x00IEND\xaeB`\x82'
img_down = tk.PhotoImage(master=window, data=img_down_code)

# Frames/Containers
top    = tk.Frame(window)
top.pack( side = tk.TOP )
middle = tk.Frame(window)
middle.pack(  )
bottom = tk.Frame(window)
bottom.pack( side = tk.BOTTOM )

# Widgets
fileName         = tk.Label(text = "No file opened.")#   , background = cfg['bgColor'], foreground = cfg['fgColor'])
status           = tk.Label(text = "[IDLE]"         )#   , background = cfg['bgColor'], foreground = cfg['fgColor'])
settingsOverview = tk.Label(text = settingsOverviewText)#, background = cfg['bgColor'], foreground = cfg['fgColor'])
textarea = tk.Text(background=cfg['bgColor'], foreground=cfg['fgColor'], insertbackground=cfg['cuColor'], font=(cfg['font'], cfg['fontSize'], cfg['fontDeco']))

# Buttons
saveBtn       = tk.Button(text = "💾 Save"        , command = lambda: save_file(fileName.cget("text")))
saveAsBtn     = tk.Button(text = "💾 Save as..."  , command = save_file)
openBtn       = tk.Button(text = "📂 Open file...", command = open_file)
toggleDarkBtn = tk.Button(text = "🌞 Light mode", command=toggleDark)
settingsBtn   = tk.Button(text = "⚙️ Settings", command=settings)
helpBtn       = tk.Button(text = "❔ Help", command=help)

# Grids
fileName.pack(in_=top, padx=10)
toggleDarkBtn.pack(in_=top, side=tk.LEFT, padx=10)
openBtn.pack(in_=top, side=tk.LEFT, padx=10)
textarea.pack(in_=middle)
settingsOverview.pack(in_=bottom, side=tk.LEFT, padx=10)
saveBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
saveAsBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
settingsBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
helpBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
status.pack(in_=bottom, side=tk.LEFT, padx=10)

window.after(1000, disco)

window.bind('<Control-s>', lambda event: save_file(fileName.cget("text")))
window.bind('<Control-d>', lambda event: toggleDark())
window.mainloop()