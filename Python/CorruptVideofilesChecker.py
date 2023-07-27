# ---------------------------------------------------------------------------- #
#                          Absolute must have packages                         #
# ---------------------------------------------------------------------------- #
try:
    import subprocess, os, sys, shutil
except Exception as e:
    print(e)
    exit("Something is seriously wrong with your Python installation... Bye.")

# ---------------------------------------------------------------------------- #
#                            Settings and parameters                           #
# ---------------------------------------------------------------------------- #
enableLogging   = True
logFile         = f"!_{os.path.basename(__file__)}.log"
logVerbosity    = "info"  # allowed values: see VERBOSITY_LEVELS
logDelete       = True
outputVerbosity = "info"  # allowed values : see VERBOSITY_LEVELS
ffmpegLogLevel  = "quiet" # how much ffmpeg should write to stdout - quiet means nothing (quiet, panic, fatal, error, warning, info, verbose)
multiThreaded   = True
threads         = 2
fileTypes       = (
    "mp4", "mov", "avi", "wmv", "avchd", "webm", "flv"
)

# ---------------------------------------------------------------------------- #
#                                   Constants                                  #
# ---------------------------------------------------------------------------- #
# Since this ever so slightly fucked with your head:
# INFO   : Contains everything
# WARNING: Info will be supressed
# ERROR  : Info and Warning will be supressed
# SILENT : Everything will be supressed if TRUE (no output)
VERBOSITY_LEVELS = ("debug", "info","warning","error","silent")

DEBUG_PREFIXES = [
    "[DEBUG]",
]

INFO_PREFIXES = [
    "[INFO]",
]

NOTE_PREFIXES = [
    "[NOTE]",
]

WARNING_PREFIXES = [
    "[WARNING]",
]

ERROR_PREFIXES = [
    "[ERROR]",
    "[EXCEPTION]",

]

OK_PREFIXES = [
    "[OK]",
    "[SUCCESS]",
    "[✓]",
]

OUTPUT_DEBUG   = VERBOSITY_LEVELS.index(outputVerbosity) == VERBOSITY_LEVELS.index('debug')
OUTPUT_INFO    = VERBOSITY_LEVELS.index(outputVerbosity) <= VERBOSITY_LEVELS.index('info')
OUTPUT_WARNING = VERBOSITY_LEVELS.index(outputVerbosity) <= VERBOSITY_LEVELS.index('warning')
OUTPUT_ERROR   = VERBOSITY_LEVELS.index(outputVerbosity) <= VERBOSITY_LEVELS.index('error')
OUTPUT_SILENT  = VERBOSITY_LEVELS.index(outputVerbosity) == VERBOSITY_LEVELS.index('silent')

LOG_DEBUG      = VERBOSITY_LEVELS.index(logVerbosity)    == VERBOSITY_LEVELS.index('debug')
LOG_INFO       = VERBOSITY_LEVELS.index(logVerbosity)    <= VERBOSITY_LEVELS.index('info')
LOG_WARNING    = VERBOSITY_LEVELS.index(logVerbosity)    <= VERBOSITY_LEVELS.index('warning')
LOG_ERROR      = VERBOSITY_LEVELS.index(logVerbosity)    <= VERBOSITY_LEVELS.index('error')
LOG_SILENT     = VERBOSITY_LEVELS.index(logVerbosity)    == VERBOSITY_LEVELS.index('silent')

COLORS = {
    "success"  : "92m"  , # green [OK]
    "danger"   : "91m"  , # red   [ERROR]
    "warning"  : "93m"  , # yellow [WARNING]
    "primary"  : "96m"  , # cyan  [INPUT, INFO etc.]
    "secondary": "1;30m", # grey
}

AVAILABLE_PARAMS = [
    # flag      # help description                                        # active description
    ["h", "-h | (h)elp    | Display help text and exit script."         , "[NOTE] Script running with -v flag. Log will be verbose (level: info)."], 
    ["v", "-v | (v)erbose | Verbose mode (sets verbosity level to info)", "[NOTE] Script running with -v flag. Log will be verbose (level: info)."], 
    ["q", "-q | (q)uiet   | Quiet mode (no output)"                     , "[NOTE] Script running with -q flag. All stdout supressed."], 
    ["s", "-s | (s)ilent  | Silent mode (no logging)"                   , "[NOTE] Script running with -s flag. Logging disabled for this session. This will overwrite -v flag."], 
    ["c", "-c | (c)ore    | Only use 1 core (no multithreading)"        , "[NOTE] Script running with -c flag. No multithreading will be available."]
]

# ---------------------------------------------------------------------------- #
#                               Text style functions                           #
# ---------------------------------------------------------------------------- #
def style(text, style = 'primary'):
    return f"\033[{COLORS[style]}{text}\033[00m"

def prints(text):
    if any(element in text for element in ERROR_PREFIXES):
        if OUTPUT_ERROR: print(style(f"{text}", "danger"))
    elif any(element in text for element in WARNING_PREFIXES):
        if OUTPUT_WARNING: print(style(f"{text}", "warning"))
    elif any(element in text for element in NOTE_PREFIXES):
        if OUTPUT_INFO: print(style(f"{text}", "primary"))
    elif any(element in text for element in INFO_PREFIXES):
        if OUTPUT_INFO: print(style(f"{text}", "secondary"))
    elif any(element in text for element in DEBUG_PREFIXES):
        if OUTPUT_DEBUG: print(style(f"{text}"), "primary")
    elif any(element in text for element in OK_PREFIXES):
        if OUTPUT_SILENT != True: print(style(f"{text}", "success"))

def inputs(text):
    prompt = input(style(text, "primary"))
    return prompt

# ---------------------------------------------------------------------------- #
#                           Import required packages                           #
# ---------------------------------------------------------------------------- #
packages = [
    # installname     #importname
    ["ffmpeg-python", "ffmpeg"]   , 
    ["threading"    , "threading"], 
    ["time"         , "time"]     , 
    ["importlib"    , "importlib"], 
    ["datetime"     , "datetime"] , 
    ["itertools"    , "itertools"], 
    ["platform"     , "platform"] , 
]

for package in packages:
    toInstall = package[0]
    toImport  = package[1]
    try:
        globals()[toImport] = __import__(toImport)
        prints(f"[OK] {toImport}")
    except Exception as e:
        print(style(e, "danger"))
        prints(f"[WARNING] You are missing a package required to run this script: {toInstall} - attempting to install...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", toInstall])
            prints(f"[SUCCESS] Package {toInstall} sucessfully installed!")
        except Exception as pipError:
            prints(f"Unable to install required package: {pipError}.")
            prints(f"You can manually install this package by doing \"pip install {toInstall}\"")
            exit(f"{pipError} Exiting...")

# ---------------------------------------------------------------------------- #
#                         Verify that ffmpeg is in PATH                        #
# ---------------------------------------------------------------------------- #
prints("[INFO] Checking FFMPEG availability...")
ffmpegFindPath = shutil.which("ffmpeg")

if ffmpegFindPath:
    prints("[OK] ffmpeg found in PATH!")
    ffmpegPath = ffmpegFindPath
    inPath = True
else:
    prints("""
[WARNING] ffmpeg not found in path.
This script relies on ffmpeg being in PATH (or manually provided by you below).
See https://stackoverflow.com/questions/65836756/python-ffmpeg-wont-accept-path-why

You can install ffmpeg from here: https://ffmpeg.org/download.html
    """)
    ffmpegPath = inputs("[INPUT] Please specify full path to executable ffmpeg: ")
    inPath = False

if os.path.isfile(ffmpegPath) and os.access(ffmpegPath, os.X_OK):
    prints(f"[OK] ffmpeg is executable ({ffmpegPath})")
else:
    prints(f"[WARNING] It seems the permissions for ffmpeg executable ({ffmpegPath}) is restricted. Script might not work.")

# ---------------------------------------------------------------------------- #
#                                   Functions                                  #
# ---------------------------------------------------------------------------- #

# -------- FUNCTION: Prints the current line in the script (for debug) ------- #
def currLine():
    return int(sys._getframe().f_back.f_lineno)

# --------------------------- FUNCTION: getSettings -------------------------- #
def getSettings():
    if type == "file":
        logInfo = f"Logging: Disabled for single file."
    else:
        logInfo = f"Logfile: {logFile}\nLog verbosity: {logVerbosity}"

    settingsOutput = f"""
█▀ █▀▀ ▀█▀ ▀█▀ █ █▄░█ █▀▀ █▀
▄█ ██▄ ░█░ ░█░ █ █░▀█ █▄█ ▄█
------------------------------------
Target: {filesToScan}
Type: {type}
{logInfo}
FFMPEG Log level: {ffmpegLogLevel}
Allowed file types:{fileTypes}
------------------------------------
    """
    return settingsOutput
# ------------------------- FUNCTION animated_loading ------------------------ #
def animated_loading(text):
    chars = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]
    for char in itertools.cycle(chars):
        sys.stdout.write('\r'+style(text, "warning")+style(char,"primary"))
        time.sleep(.1)
        sys.stdout.flush() 

# ------------------------------ FUNCTION withTime ----------------------------- #
def withTime(msg):
    # Force time to have 2 digits (to have same length and look nicer in output and log)
    hour      = datetime.datetime.now().hour if len(str(datetime.datetime.now().hour))     == 2 else f"0{datetime.datetime.now().hour}"
    minute    = datetime.datetime.now().minute if len(str(datetime.datetime.now().minute)) == 2 else f"0{datetime.datetime.now().minute}"
    second    = datetime.datetime.now().second if len(str(datetime.datetime.now().second)) == 2 else f"0{datetime.datetime.now().second}"
    timeStamp = f"{hour}:{ minute}:{second}:{str(datetime.datetime.now().microsecond)[: 3]}"
    return f"[{timeStamp}] {msg}"

# ------------------------ FUNCTION recursiveFileList ------------------------ #
def recursiveFileList(cwd):
    fileList = []
    for root, dirnames, filenames in os.walk(cwd):
        fileList.append(filenames)
    return fileList[0]

# ----------------------------- FUNCTION checkVid ---------------------------- #
def checkVid(fullPath):
    try:
        fileSize = round(os.path.getsize(fullPath) / 1000 / 1000 / 1000, 2)
        # prints(f"[INFO] Checking {fullPath} [{fileSize}GB]")

        if inPath == True:
            ffmpeg.input(fullPath).output("null", f="null", loglevel=ffmpegLogLevel).run()
        else:
            ffmpeg.input(fullPath).output("null", f="null", loglevel=ffmpegLogLevel).run(cmd=ffmpegPath)
    except:
        writeLog(f"[ERROR] Corrupted {fullPath}")
        return False
    else:
        writeLog(f"[OK] {fullPath}")
        return True

# ----------------------------- FUNCTION writeLog ---------------------------- #
def writeLog(msg, output = True, timestamp = True):
    # need to get and set this globally
    global enableLogging

    if timestamp == True:
        msg = withTime(msg)

    # just print to stdout - since we are not logging
    if enableLogging == False:
        if output == False:
            prints(f"[WARNING] Logging is disabled, and writeLog function called with output set to False on line {currLine()}. Text: {msg}")
        prints(msg)
        return
    
    try:
        if os.path.isfile(logFile):
            f = open(logFile, "a", encoding="utf-8")
            f.write(f"{msg}\n")
            f.close()
        else:
            f = open(logFile, "w+", encoding="utf-8")
            f.write(f"{msg}\n")
            f.close()
        if output == True:
            prints(msg)
    except Exception as e:
        prints(f"[WARNING] Unable to create log file {logFile} - permission issue?")
        prints(f"[EXCEPTION] {e}")
        prompt = inputs("[INPUT] Do you want to continue? No log will be written. [Y/N]")
        enableLogging = False
        if prompt.upper() != "Y":
            exit("Exited.")

# ---------------------------------------------------------------------------- #
#                              Parameter functions                             #
# ---------------------------------------------------------------------------- #
def param_h():
    if "Linux" in platform.system():
        cmd = "clear"
    else:
        cmd = "cls"
    os.system(cmd)

    paramHelpText = ""
    for param in AVAILABLE_PARAMS:
        paramHelpText += f"{param[1]}\n"
    exit(f"""

██╗░░██╗███████╗██╗░░░░░██████╗░
██║░░██║██╔════╝██║░░░░░██╔══██╗
███████║█████╗░░██║░░░░░██████╔╝
██╔══██║██╔══╝░░██║░░░░░██╔═══╝░
██║░░██║███████╗███████╗██║░░░░░
╚═╝░░╚═╝╚══════╝╚══════╝╚═╝░░░░░
        
This script will check the given folder for corrupt video files.

Available params:
{paramHelpText}
        """)
    
def param_v():
    global logVerbosity
    global outputVerbosity
    logVerbosity    = "info"
    outputVerbosity = "info"

def param_q():
    global outputVerbosity
    outputVerbosity = "silent"

def param_s():
    global enableLogging
    enableLogging = False

def param_c():
    global multiThreaded
    multiThreaded = False

# ---------------------------------------------------------------------------- #
#                                 Custom params                                #
# ---------------------------------------------------------------------------- #
if len(sys.argv) == 2:
    # parameters are not case sensitive, and doesn't even require a symbol first
    arg = sys.argv[1].lower()

    for param in AVAILABLE_PARAMS:
        param_key   = param[0]
        help_desc   = param[1]
        active_desc = param[2]

        if param_key in arg:
            paramFunc = f"param_{param_key}"
            if paramFunc not in globals():
                prints(f"[WARNING] Invalid parameter -{param_key}")
                continue
            globals()[paramFunc]()
            prints(active_desc)
else:
    prints("[INFO] Run this script with a '-h' flag behind to get help.")

# ---------------------------------------------------------------------------- #
#                           Ask for file/folder input                          #
# ---------------------------------------------------------------------------- #
filesToScan    = inputs("[INPUT] Folder/file you want to scan: ")
prints(f"[INFO] Verifying {filesToScan}...")

# ---------------------------------------------------------------------------- #
#                                     FILE                                     #
# ---------------------------------------------------------------------------- #
if os.path.isfile(filesToScan):
    # returns True if the path is a file or a symlink to a file.

    file = filesToScan
    type = "file"

    prints(getSettings())

    try:
        checkVid(file)
    except ffmpeg._run.Error:
        prints(f"[ERROR] [{file}] is corrupt")
    else:
        prints(f"[OK] [{file}]")


# ---------------------------------------------------------------------------- #
#                                    FOLDER                                    #
# ---------------------------------------------------------------------------- #
elif os.path.exists(filesToScan):
    # returns True if the path is a file, directory, or a symlink to a file.

    folder = filesToScan
    type   = "folder"

    # change working directory
    os.chdir(folder)

    # create a log file
    if os.path.exists(logFile) != True:
        prints(f"[INFO] A logfile ({logFile}) will be created with a list of all corrupted files.")
    else:
        if logDelete == True:
            os.remove(logFile)
            prints(f"[INFO] Logfile deleted, creating new...")
        else:
            prints(f"[INFO] A logfile ({logFile}) already exists in this folder. Using (a)ppend mode.")
    writeLog(f"""

█▀ █▀▀ █▀█ █ █▀█ ▀█▀   █▀ ▀█▀ ▄▀█ █▀█ ▀█▀
▄█ █▄▄ █▀▄ █ █▀▀ ░█░   ▄█ ░█░ █▀█ █▀▄ ░█░
------------------------------------
    {datetime.datetime.today()}
------------------------------------
    """, True, False)

    recursiveFiles = recursiveFileList(folder)
    fileCount      = len(recursiveFiles)
    corruptedCount = 0
    okCount        = 0
    currentFile    = 0

    writeLog(getSettings(), True, False)
    writeLog(f"[INFO] Scanning folder recursively: {folder}")
    writeLog(f"[INFO] Counting {fileCount} files in this folder.")

    for findex, fileName in enumerate(recursiveFiles):
        # This is the for-loop of a FILE ITERATOR
        if fileName.lower().endswith(fileTypes) != True:
            writeLog(f"[INFO] Non-video file: {fileName}")
            continue

        # # ---------------------------------------------------------------------------- #
        # #                                    THREADS                                   #
        # # ---------------------------------------------------------------------------- #
        if multiThreaded == True:
            prints(f"[DEBUG] Starting multithreaded")
            currentThreads = []
            for i in range(0,threads):
                # This is the for-loop of ONE THREAD
                # variable i = THREAD
                # variable findex = FILE INDEX (recursiveFiles)
                # Make sure we don't do any of them twice
                jumpAhead = 0
                if findex != 0:
                    jumpAhead = (i+threads-1)

                actualThread = i+1
                threadInfo   = f"[THREAD {actualThread}/{threads}]"
                nextFileName = recursiveFiles[findex+i+jumpAhead]
                fullPath     = f"{folder}{os.sep}{nextFileName}"
                fileSize     = round(os.path.getsize(fullPath) / 1000 / 1000 / 1000, 2)

                try:
                    prints(f"[INFO] {threadInfo} Checking {fullPath} [{fileSize}GB]")
                    process     = threading.Thread(name   = "checkvid", target=checkVid, args=(fullPath,))
                    process.start()
                    currentThreads.append(process)
                except:
                    prints(f"[ERROR] Unable to start thread {threadInfo}")

            for currentThread in currentThreads:
                if currentThread == True:
                    okCount += 1
                else:
                    corruptedCount += 1

                currentThread.join()
                
        # ---------------------------------------------------------------------------- #
        #                                 NON THREADED                                 #
        # ---------------------------------------------------------------------------- #
        else:
            prints(f"[DEBUG] Starting singlethreaded")

            fullPath    = f"{folder}{os.sep}{fileName}"
            fileSize  = round(os.path.getsize(fullPath) / 1000 / 1000 / 1000, 2)

            try:
                process = threading.Thread(name = "checkvid", target=checkVid, args=(fullPath,))
                process.start()
                while process.is_alive():
                    animated_loading(f"[INFO] Checking {fullPath} [{fileSize}GB] ")
            except:
                prints(f"[ERROR] Unable to start single thread")

    writeLog("[INFO] Finished scanning folder.")
    if corruptedCount > 0:
        writeLog(f"[ERROR] A total of {corruptedCount} files are corrupted. See logfile: {logFile} for more details.")
    else:
        writeLog(f"[OK] No corrupted files found in {folder}")
    writeLog(f"[RESULT] {okCount} OK - {corruptedCount} CORRUPTED", True, False)
    writeLog("------------------------------------", False, False)

else:
    exit("Invalid file/folder")