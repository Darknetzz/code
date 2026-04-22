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


class C:
    """Named ANSI escape codes.

    Centralized so every script in this repo can share one set of color
    constants instead of redefining its own ``class c: HEADER = ...`` block.
    """
    HEADER    = f"{START_C}[95m"
    OKBLUE    = f"{START_C}[94m"
    OKCYAN    = f"{START_C}[96m"
    OKGREEN   = f"{START_C}[92m"
    WARNING   = f"{START_C}[93m"
    FAIL      = f"{START_C}[91m"
    GREY      = f"{START_C}[1;30m"
    ENDC      = f"{START_C}[0m"
    BOLD      = f"{START_C}[1m"
    UNDERLINE = f"{START_C}[4m"
    BLINK     = f"{START_C}[5m"
    NEGATIVE  = f"{START_C}[7m"
    CROSSED   = f"{START_C}[9m"


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
        prepend = types["default"]

    print(f"{prepend} {txt}")


# ---------------------------------------------------------------------------- #
#                           Colored print helpers                              #
# ---------------------------------------------------------------------------- #
# Shared equivalents of the ``printGreen`` / ``printRed`` / ... helpers that
# used to be duplicated in individual scripts. Each wraps text in an ANSI
# escape and a reset so call sites like
#   print(f"{printGreen('hello')} world")
# keep working as-is after the switch.
def printGreen(text):    return color(text, "green")
def printRed(text):      return color(text, "red")
def printYellow(text):   return color(text, "yellow")
def printCyan(text):     return color(text, "cyan")
def printGrey(text):     return color(text, "grey")
def printBlinking(text): return f"{C.BLINK}{text}{C.ENDC}"
def printNegative(text): return f"{C.NEGATIVE}{text}{C.ENDC}"
def printCrossed(text):  return f"{C.CROSSED}{text}{C.ENDC}"
