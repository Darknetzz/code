# ---------------------------------------------------------------------------- #
#                                   Constants                                  #
# ---------------------------------------------------------------------------- #
COLORS = {
    "success"  : "92m"  , # green [OK]
    "danger"   : "91m"  , # red   [ERROR]
    "warning"  : "93m"  , # yellow [WARNING]
    "primary"  : "96m"  , # cyan  [INPUT, INFO etc.]
    "secondary": "1;30m", # grey
    "end"      : "[00m",  # end
}

# ---------------------------------------------------------------------------- #
#                               Text style functions                           #
# ---------------------------------------------------------------------------- #
def style(text, style = 'primary'):
    return f"\033[{COLORS[style]}{text}\033{COLORS['end']}"

def inputs(text):
    prompt = input(style(text, "primary"))
    return prompt