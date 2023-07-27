# This is the ultimate script to handle files in bulk
# Especially if you want to prefix/suffix all files in a folder

import os, re

os.system('cls')

# ---------------------------------------------------------------------------- #
#                                   Functions                                  #
# ---------------------------------------------------------------------------- #
def printGreen(text):
    return f"\033[92m{text}\033[00m"

def printRed(text):
    return f"\033[91m{text}\033[00m"

def printYellow(text):
    return f"\033[93m{text}\033[00m"

def printCyan(text):
    return f"\033[96m{text}\033[00m"

def printGrey(text):
    return f"\033[1;30m{text}\033[0m"

def printBlinking(text):
    return f"\033[5m{text}\033[0m"

def printNegative(text):
    return f"\033[7m{text}\033[0m"

def printCrossed(text):
    return f"\033[9m{text}\033[0m"

def recursiveFileList(cwd):
    fileList = []
    for root, dirnames, filenames in os.walk(cwd):
        fileList.append(filenames)
    return fileList[0]
# ---------------------------------------------------------------------------- #






# ███╗░░░███╗░█████╗░██████╗░██╗░░░██╗██╗░░░░░███████╗░██████╗
# ████╗░████║██╔══██╗██╔══██╗██║░░░██║██║░░░░░██╔════╝██╔════╝
# ██╔████╔██║██║░░██║██║░░██║██║░░░██║██║░░░░░█████╗░░╚█████╗░
# ██║╚██╔╝██║██║░░██║██║░░██║██║░░░██║██║░░░░░██╔══╝░░░╚═══██╗
# ██║░╚═╝░██║╚█████╔╝██████╔╝╚██████╔╝███████╗███████╗██████╔╝
# ╚═╝░░░░░╚═╝░╚════╝░╚═════╝░░╚═════╝░╚══════╝╚══════╝╚═════╝░


# ---------------------------------------------------------------------------- #
#                        Suffix all files in this folder                       #
# ---------------------------------------------------------------------------- #
def suffix():
    suffix = input(printYellow("Specify suffix (ex. _SUFFIX): "))
    confirm = input(printYellow(f"A total of {printYellow(len(filesToSearch))} files will be renamed to have the suffix {printYellow(suffix)}. Continue [Y/N]?"))
    if confirm.upper() == "Y":
        for fileName in filesToSearch:
            split = os.path.splitext(fileName)
            os.rename(fileName, f"{split[0]}{suffix}{split[1]}")
        exit(printGreen("Done!"))
    else:
        exit("Operation cancelled. Exiting...")
# ---------------------------------------------------------------------------- #




# ---------------------------------------------------------------------------- #
#                        Prefix all files in this folder                       #
# ---------------------------------------------------------------------------- #
def prefix():
    prefix = input(printYellow("Specify prefix (ex. PREFIX_): "))
    confirm = input(printYellow(f"A total of {printYellow(len(filesToSearch))} files will be renamed to have the prefix {printYellow(prefix)}. Continue [Y/N]?"))
    if confirm.upper() == "Y":
        for fileName in filesToSearch:
            os.rename(fileName, f"{prefix}{fileName}")
        exit(printGreen("Done!"))
    else:
        exit("Operation cancelled. Exiting...")
# ---------------------------------------------------------------------------- #




# ---------------------------------------------------------------------------- #
#                                Search for text                               #
# ---------------------------------------------------------------------------- #
def search():
    """Search for text"""
    search = input(printYellow("Search for: "))
    matchesFound = 0

    for fileName in filesToSearch:
            # print(f"Searching in {printCyan(fileName)}")
            with open(fileName) as file:
                for n, line in enumerate(file):
                    if search in line:
                        matchesFound += 1
                        print(f"[{fileName}:{n+1}] {line}".replace(search, printGreen(search)))
    print(f"A total of {printCyan(matchesFound)} matches were found in {printCyan(cwd)}")
# ---------------------------------------------------------------------------- #


# ---------------------------------------------------------------------------- #
#                            SEARCH AND REPLACE TEXT                           #
# ---------------------------------------------------------------------------- #
def searchreplace():
    search  = input(printYellow("Search for: "))
    replace = input(printYellow("Replace with: "))
    matchesFound = 0

    for fileName in filesToSearch:
            # print(f"Searching in {printCyan(fileName)}")
            with open(fileName) as file:
                for n, line in enumerate(file):
                    if search in line:
                        matchesFound += 1
                currentContent = file.read()
                newContent     = re.sub(search, replace)

    if matchesFound > 0:
        confirm = input(f"A total of {printCyan(matchesFound)} matches were found in {printCyan(cwd)} are you sure you want to replace them [Y/N]?")
        if confirm.upper() == "Y":
            print(f"Performing {matchesFound} replacements...")
        else:
            exit("Not making any changes... Exiting")
    else:
        exit(printRed("No matches found... Exiting"))
# ---------------------------------------------------------------------------- #


# ---------------------------------------------------------------------------- #
#                               SEARCH FILENAMES                               #
# ---------------------------------------------------------------------------- #
def searchfilenames():
    search = input(printYellow("Search for: "))
    matchesFound = 0
    for fileName in filesToSearch:
        if search.lower() in fileName.lower():
            matchesFound += 1
            print(fileName.replace(search, printGreen(search)))
# ---------------------------------------------------------------------------- #

modules = [
    # Name of module                                   Category        Shortname (function call)
    ["Suffix all files in this folder"               , "FILENAMES"   , "suffix"]                , 
    ["Prefix all files in this folder"               , "FILENAMES"   , "prefix"]                , 
    ["Change/Remove prefix from files in this folder", "FILENAMES"   , "crprefix"]              , 
    ["Change/Remove suffix from files in this folder", "FILENAMES"   , "crsuffix"]              , 
    ["Search filenames"                              , "FILENAMES"   , "searchfilenames"]       , 
    ["Search and replace filenames"                  , "FILENAMES"   , "searchreplacefilenames"], 
    ["Search for text in files"                      , "FILE CONTENT", "search"]                , 
    ["Search and replace text in files"              , "FILE CONTENT", "searchreplace"]         , 
    ["Move files/folders to different location"      , "LOCATION"    , "move"]                  , 
    ["Copy files/folders to different location"      , "LOCATION"    , "copy"]                  , 
]

cwd = input("Specify a folder: ")

if os.path.isdir(cwd) != True:
    exit(printRed("The folder you have specified does not exist. Unable to continue. Exiting..."))

os.chdir(cwd)

askRecursive = False
for file in os.listdir(cwd):
    if os.path.isdir(file):
        askRecursive = True

# -------------------------------- Helper text ------------------------------- #
print(f"""
Current script           : {printCyan(__file__)}
Current working directory: {printCyan(os.getcwd())}

{printGreen("Green = Available function")}
{printGrey("Grey")} or {printRed("Red")} = Unavailable function
""")
currentCategory = ""
caller          = {}
moduleName      = {}
moduleCat       = {}

for n, module in enumerate(modules):
    moduleName[n+1]     = thisModuleName = module[0]
    moduleCat[n+1]      = thisCatName    = module[1]
    caller[n+1]         = module[2] # this will assign the operation number to a function
    thisFunctionPointer = None if module[2] not in globals() else globals()[module[2]]

    # Category name
    if thisCatName != currentCategory:
        print(f"{printCyan(thisCatName)}")
    currentCategory = thisCatName

    # Verify that function is defined
    if callable(thisFunctionPointer):
        print(f"[{printGreen(n+1)}] - {thisModuleName}")
    else:
        print(f"[{printRed(n+1)}] - {printGrey(thisModuleName)} {printRed('(Coming soon!)')}")

action = int(input(printYellow("\nChoose an operation: ")))
recursive = input(printYellow("Do you want to perform the selected operation recursively (include subfolders) [Y/N]?")) if askRecursive == True else "N"

# -------------------------- Modify recursive value -------------------------- #
if recursive == "Y":
    recursive = "Yes"
else:
    recursive = "No"

# -------------------------------- Search CWD -------------------------------- #
if recursive == "Yes":
    filesToSearch = recursiveFileList(cwd)
else:
    filesToSearch = os.listdir(cwd)

print(f"""
Current working directory: {printCyan(cwd)}
Action selected          : [{printCyan(action)}] {printCyan(moduleName[action])}
Files in this folder     : {printCyan(len(filesToSearch))}
Recursive                : {printCyan(recursive)}
""")


# Prepare the selected function
funcToRun = caller[action]

if funcToRun in globals() and any(funcToRun in subarray for subarray in modules):
    globals()[funcToRun]()
else:
    exit(printRed("The action you chose is not available"))
# print(f"""
# Function name to run: {funcToRun}
# Global memory address: {globals()[funcToRun]}
# """)