import tkinter as tk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter import font
import random, os, importlib

# Window initialize
window   = tk.Tk()
# window.resizable(False, False)
window.title("Text editor")

# Settings
CONFIG_FILE = "textEditor.cfg"
if os.path.exists(CONFIG_FILE):
    f = open(CONFIG_FILE, 'r')
    exec(f.read())
    f.close()
else:
    cfg            = {
        'font'           : 'Consolas', 
        'fontSize'       : '17'      , 
        'fontDeco'       : 'normal'  , 
        'bgColor'        : 'Black'   , 
        'fgColor'        : 'Green'   , 
        'cuColor'        : 'Red'     , 
        'disco'          : 'false'   , 
        'syntax'         : 'Text'    , 
        "color_Keywords" : "Pink"    , 
        "color_Symbols"  : "Cyan"    , 
        "color_Operators": "Grey"    , 
        "color_Variables": "Red"     , 
        "color_Comments" : "Darkgrey",
    }
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
    "Cyan",
    "Brown",
    "Yellow",
    "Orange",
]

AVAILABLE_FONTS = list(font.families())

AVAILABLE_LANGS = [
    "Text",
    "PHP",
    "JavaScript",
    "Python"
]

FILETYPES = {
    ".py": "Python",
    ".php": "PHP",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".txt": "Text",
}

SYNTAX = {}

SYNTAX["PHP"] = {
    # TYPE: [COLOR, [SEARCHFOR]]
    "Keywords": [cfg["color_Keywords"], ["if", "else", "while", "foreach", "for", "echo", "function"]],
    "Symbols": [cfg["color_Symbols"], ["<?php", "?>", "{", "}", "[", "]", "(", ")", ";", ",", "."]],
    "Operators": [cfg["color_Operators"], ["==", ">", ">=", "<=", "<", "!=", "===", "!==", "="]],
    "Variables": [cfg["color_Variables"], ["$"]],
    "Comments": [cfg["color_Comments"], ["//", "#"]]
}

SYNTAX["Python"] = {
    # TYPE: [COLOR, [SEARCHFOR]]
    "Keywords": [cfg["color_Keywords"], ["if", "else", "elif", "while", "for", "print", "True", "False", "def"]],
    "Symbols": [cfg["color_Symbols"], [":", "?>", "{", "}", "[", "]", "(", ")", ";", "\""]],
    "Operators": [cfg["color_Operators"], ["==", ">", ">=", "<=", "<", "!=", "="]],
    "Variables": [cfg["color_Variables"], []],
    "Comments": [cfg["color_Comments"], ["#"]]
}

# ---------------------------------------------------------------------------- #
#                              SYNTAX HIGHLIGHTER                              #
# ---------------------------------------------------------------------------- #
def highlight(textarea):
    if cfg["syntax"] != "Text":
        try:
            syntax = SYNTAX[cfg["syntax"]]
            highlightWords = {}
            for type in syntax:
                color     = syntax[type][0]
                searchfor = syntax[type][1]

                for search in searchfor:
                    highlightWords[search] = color

            '''the highlight function, called when a Key-press event occurs'''
            for k,v in highlightWords.items(): # iterate over dict
                startIndex = "1.0"

                while True:
                    startIndex = textarea.search(k, startIndex, tk.END) # search for occurence of k
                    if startIndex:
                        endIndex = textarea.index('%s+%dc' % (startIndex, (len(k)))) # find end of k
                        textarea.tag_add(k, startIndex, endIndex) # add tag to k
                        textarea.tag_config(k, foreground=v)      # and color it with v
                        startIndex = endIndex # reset startIndex to continue searching
                    else:
                        break
        except:
            """Syntax is probably set to text, or something"""
            textarea.config(background=cfg['bgColor'], foreground=cfg['fgColor'], insertbackground=cfg['cuColor'], font=(cfg['font'], cfg['fontSize'], cfg['fontDeco']))
        
# ---------------------------------------------------------------------------- #
#                                   OPEN FILE                                  #
# ---------------------------------------------------------------------------- #
def open_file():
    """Open a file for editing."""
    filepath = askopenfilename(
        filetypes=[("All Files", "*.*"), ("Text Files", "*.txt")]
    )
    if not filepath:
        return
    textarea.delete("1.0", tk.END)
    with open(filepath, mode="r", encoding="utf-8") as input_file:
        text = input_file.read()
        textarea.insert(tk.END, text)
    fileName.config(text=filepath)

    # Update syntax highlight
    for extension in FILETYPES:
        if filepath.endswith(extension):
            cfg["syntax"] = FILETYPES[extension]

    updateSettingsOverview()
    status.config(text=f"[FILE OPENED]", foreground="Green")

# ---------------------------------------------------------------------------- #
#                                   SAVE FILE                                  #
# ---------------------------------------------------------------------------- #
def save_file(fn = None):
    """Save the current file as a new file."""
    if fn == None or fn == "No file opened.":
        fileType = list(FILETYPES.keys())[list(FILETYPES.values()).index(cfg["syntax"])] or "*.txt"

        filepath = asksaveasfilename(
            defaultextension=fileType,
            filetypes=[(f"{cfg['syntax']} file", f"*{fileType}"), ("All Files", "*.*")],
        )
    else:
        filepath = fn

    if not filepath:
        return
    with open(filepath, mode="w", encoding="utf-8") as output_file:
        text = textarea.get("1.0", tk.END)
        output_file.write(text)
    fileName.config(text=filepath)

    # Update syntax highlight
    for extension in FILETYPES:
        if filepath.endswith(extension):
            cfg["syntax"] = FILETYPES[extension]

    updateSettingsOverview()
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
#                            UPDATE SETTINGSOVERVIEW                           #
# ---------------------------------------------------------------------------- #
def updateSettingsOverview():
    settingsOverviewText = f"[{cfg['syntax']}] [{cfg['font']}] [{cfg['fontSize']}px] [{cfg['fontDeco']}]"
    settingsOverview.config(text = settingsOverviewText)
    highlight(textarea)

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
        configFile = open(CONFIG_FILE, "w+")
        configFile.write("cfg = {}\n")

        for settingName in savecfg:
            if len(savecfg[settingName].get()) > 0:
                cfg[settingName] = savecfg[settingName].get()
                configFile.write(f"cfg[\"{settingName}\"] = \"{cfg[settingName]}\"\n")
                print(f"Setting {settingName} = {cfg[settingName]}")
        configFile.close()
        textarea.config(background=cfg['bgColor'], foreground=cfg['fgColor'], insertbackground=cfg['cuColor'], font=(cfg['font'], cfg['fontSize'], cfg['fontDeco']))
        status.config(text="[SETTINGS SAVED]", foreground="Green")
        updateSettingsOverview()



        # retoggle highlight
        highlight(textarea)
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
        ["Font"            , "font"           , AVAILABLE_FONTS] , 
        ["Font size"       , "fontSize"       , "str"]           , 
        ["Font decoration" , "fontDeco"       , "str"]           , 
        ["Background color", "bgColor"        , AVAILABLE_COLORS], 
        ["Text color"      , "fgColor"        , AVAILABLE_COLORS], 
        ["Cursor color"    , "cuColor"        , AVAILABLE_COLORS], 
        ["Syntax highlight", "syntax"         , AVAILABLE_LANGS] , 
        ["Disco mode"      , "disco"          , "bool"]          , 
        ["Code Keywords"  , "color_Keywords" , AVAILABLE_COLORS],
        ["Code Symbols"   , "color_Symbols"  , AVAILABLE_COLORS],
        ["Code Operators" , "color_Operators", AVAILABLE_COLORS],
        ["Code Variables" , "color_Variables", AVAILABLE_COLORS],
        ["Code Comments"  , "color_Comments" , AVAILABLE_COLORS],
    ]
    savecfg = {} # the temp for storing about to be saved cfg
    showcfg = {} # only for display

    # Settings window initialize
    settingsWindow = tk.Toplevel(window)
    settingsWindow.grab_set()
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

        elif type(cfgType) == list:
            savecfg[cfgName].set(cfg[cfgName])
            showcfg[cfgName] = tk.OptionMenu(settingsWindow, savecfg[cfgName], cfg[cfgName], *cfgType)
            showcfg[cfgName].config(indicatoron=0, compound=tk.RIGHT, image=img_down, width=120)

        showcfg[cfgName].grid(column=1,row=i)

    settingsWindow.bind("<Return>", lambda event: saveSettings(savecfg, settingsWindow))
    tk.Button(settingsWindow, text="💾 Save", command=lambda: saveSettings(savecfg, settingsWindow)).grid(column=1,row=i+1)

# ---------------------------------------------------------------------------- #
#                                  HELP WINDOW                                 #
# ---------------------------------------------------------------------------- #
def help():
    helpWindow = tk.Toplevel(window)
    helpWindow.grab_set()
    helpWindow.resizable(False, False)
    helpWindow.geometry('700x500')
    helpWindow.title("Help")

    helpText = tk.Text(helpWindow)
    text = """
    
    ████████╗███████╗██╗░░██╗████████╗███████╗██████╗░██╗████████╗░█████╗░██████╗░
    ╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝██╔════╝██╔══██╗██║╚══██╔══╝██╔══██╗██╔══██╗
    ░░░██║░░░█████╗░░░╚███╔╝░░░░██║░░░█████╗░░██║░░██║██║░░░██║░░░██║░░██║██████╔╝
    ░░░██║░░░██╔══╝░░░██╔██╗░░░░██║░░░██╔══╝░░██║░░██║██║░░░██║░░░██║░░██║██╔══██╗
    ░░░██║░░░███████╗██╔╝╚██╗░░░██║░░░███████╗██████╔╝██║░░░██║░░░╚█████╔╝██║░░██║
    ░░░╚═╝░░░╚══════╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═════╝░╚═╝░░░╚═╝░░░░╚════╝░╚═╝░░╚═╝
    Version 0.0.0.0.0.0.1b

    KEYBINDS
        CTRL+S - Save
        CTRL+D - Toggle dark mode
        CTRL+H - Bring up this help menu
        CTRL+P - Settings/preferences
    """
    helpText.insert(tk.END,text)
    helpText.config(state=tk.DISABLED, background=cfg['bgColor'], foreground=cfg['fgColor'])
    helpText.pack(expand=True,fill=tk.BOTH)

# ---------------------------------------------------------------------------- #
#                                     DISCO                                    #
# ---------------------------------------------------------------------------- #
def disco():
    if cfg['disco'] == 'true':
        bg = random.choice(AVAILABLE_COLORS)
        fg = random.choice([i for i in AVAILABLE_COLORS if i != bg])
        textarea.config(background=bg, foreground=fg, insertbackground=fg)
    window.after(500, disco)

# Images
img_down_code = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x0e\x00\x00\x00\x07\x08\x06\x00\x00\x008G|\x19\x00\x00\x00\tpHYs\x00\x00\x10\x9b\x00\x00\x10\x9b\x01t\x89\x9cK\x00\x00\x00\x19tEXtSoftware\x00www.inkscape.org\x9b\xee<\x1a\x00\x00\x00OIDAT\x18\x95\x95\xce\xb1\x0e@P\x0cF\xe1\xefzI\x8fc$\x12\x111\x19\xec\x9e\x12\xcb\x95 A\x9d\xa4K\xff\x9e\xb6\t\x13J\xffX \xa1\xc7\x16\xac\x19\xc5\xb1!*\x8fy\xf6BB\xf7"\r_\xff77a\xcd\xbd\x10\xedI\xaa\xa3\xd2\xf9r\xf5\x14\xee^N&\x14\xab\xef\xa9\'\x00\x00\x00\x00IEND\xaeB`\x82'
img_down = tk.PhotoImage(master=window, data=img_down_code)

# Frames/Containers
top    = tk.Frame(window)
top.pack( side = tk.TOP )
middle = tk.Frame(window)
middle.pack( expand=True, fill=tk.BOTH )
bottom = tk.Frame(window)
bottom.pack( side = tk.BOTTOM )

# Widgets
fileName         = tk.Label(text = "No file opened.")#   , background = cfg['bgColor'], foreground = cfg['fgColor'])
status           = tk.Label(text = "[IDLE]"         )#   , background = cfg['bgColor'], foreground = cfg['fgColor'])
settingsOverview = tk.Label(text = f"[{cfg['syntax']}] [{cfg['font']}] [{cfg['fontSize']}px] [{cfg['fontDeco']}]", background="Black", foreground="Grey")
textarea = tk.Text(background=cfg['bgColor'], foreground=cfg['fgColor'], insertbackground=cfg['cuColor'], font=(cfg['font'], cfg['fontSize'], cfg['fontDeco']))

# Buttons
saveBtn       = tk.Button(text = "💾 Save"        , command = lambda: save_file(fileName.cget("text")))
saveAsBtn     = tk.Button(text = "💾 Save as..."  , command = save_file)
openBtn       = tk.Button(text = "📂 Open file...", command = open_file)
toggleDarkBtn = tk.Button(text = "🌞 Light mode", command=toggleDark)
settingsBtn   = tk.Button(text = "⚙️ Settings", command=settings)
helpBtn       = tk.Button(text = "❔ Help", command=help)

# Grids
settingsOverview.pack(in_=bottom, side=tk.LEFT, padx=10)
saveBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
saveAsBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
settingsBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
helpBtn.pack(in_=bottom, side=tk.LEFT, padx=10)
status.pack(in_=bottom, side=tk.LEFT, padx=10)
fileName.pack(in_=top, padx=10)
toggleDarkBtn.pack(in_=top, side=tk.LEFT, padx=10)
openBtn.pack(in_=top, side=tk.LEFT, padx=10)
textarea.pack(in_=middle, expand=True, fill=tk.BOTH)

window.after(1000, disco)

window.bind('<Control-s>', lambda event: save_file(fileName.cget("text")))
window.bind('<Control-d>', lambda event: toggleDark())
window.bind('<Control-h>', lambda event: help())
window.bind('<Control-p>', lambda event: settings())
window.bind('<Key>', lambda event: highlight(textarea))
window.mainloop()