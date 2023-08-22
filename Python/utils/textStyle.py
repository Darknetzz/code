# ---------------------------------------------------------------------------- #
#                                   Constants                                  #
# ---------------------------------------------------------------------------- #
START_C = "\033"
END_C = f"{START_C}[00m"

COLORS = {
    "default": f"{END_C}",       # nathin
    "green"  : f"{START_C}[92m", # green [OK]
    "red"    : f"{START_C}[91m", # red   [ERROR]
    "yellow" : f"{START_C}[93m", # yellow [WARNING]
    "cyan"   : f"{START_C}[96m", # cyan  [INPUT, INFO etc.]
    "grey"   : f"{START_C}[1;30m", # grey
}

STYLES = {
    "default"  : COLORS["default"],# nathin
    "success"  : COLORS["green"] , # green [OK]
    "danger"   : COLORS["red"]   , # red   [ERROR]
    "warning"  : COLORS["yellow"], # yellow [WARNING]
    "primary"  : COLORS["cyan"]  , # cyan  [INPUT, INFO etc.]
    "secondary": COLORS["grey"]  , # grey
}



# ---------------------------------------------------------------------------- #
#                               Text style functions                           #
# ---------------------------------------------------------------------------- #
def style(text, style = 'primary'):
    return f"{STYLES[style]}{text}{END_C}"

def color(text, color = 'cyan'):
    return f"{COLORS[color]}{text}{END_C}"

def inputs(text):
    prompt = input(style(text, "primary"))
    return prompt

def warning(txt, forceReturn = "", forceExit = False):
    if forceExit == True:
        exit(f"❌ [FATAL] {txt}")
    if forceReturn != "":
        print(f"⚠️ [WARNING] {txt}")
        return forceReturn

    reply = input(f"⚠️ [WARNING] {txt} [Y/n]")
    
    if reply.upper() == "Y" or reply == "":
        return True
    return False

def info(txt, type="info"):
    types = {
        "default": "❔ [INFO]",
        "skip": "⏩ [SKIPPING]",
        "info": "ℹ️ [INFO]",
    }

    if type in types:
        prepend = types[type]
    else:
        prepend = type["default"]

    print(f"{prepend} {txt}")