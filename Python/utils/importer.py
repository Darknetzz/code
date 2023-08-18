try:
    import subprocess, sys
except Exception as e:
    print(e)
    exit("Something is seriously wrong with your Python installation... Bye.")

def importer_import_new(importName: str|list, pipName: str|list=None, verbose: bool=False):
    if pipName == None:
        pipName = importName

    def vprint(txt):
        if verbose == True:
            print(txt)

    try:
        globals()[importName] = __import__(importName)
        vprint(f"[OK] - {importName}")
        return globals()[importName]
    except Exception as e:
        vprint(e)
        vprint(f"[WARNING] You are missing a package required to run this script: {importName} - attempting to install...")

        install = subprocess.check_call([sys.executable, "-m", "pip", "install", pipName])

        if install == 0:
            vprint(f"[SUCCESS] Package {importName} sucessfully installed!")
            return __import__(importName)
        else:
            print(f"Unable to install required package with importName {importName} and pipName {pipName}.")
            print(f"You can attempt to manually install this package by doing \"pip install {pipName}\"")
            return False
        

# ---------------------------------------------------------------------------- #
#                           Import required packages                           #
# ---------------------------------------------------------------------------- #
# ──────────────────────────────── DEPRECATED ──────────────────────────────── #
# This function is 'replaced' by importer_import_new to support packages with differing
# import names and pip install names. It is highly recommended you use that one instead!
def importer_import(package: str, silent: bool=True, ignoreDeprecated: bool=False):
    print(f"""
          [WARNING - DEPRECATED]
          Function importer_import from {__file__} is deprecated.
          You can still use it, but it is recommended that you use importer_import_new function instead.
          For more information, see https://github.com/Darknetzz/code/tree/main/Python/utils""") if ignoreDeprecated == False else None
    
    def vprint(txt):
        if silent != True:
            print(txt)

    try:
        globals()[package] = __import__(package)
        vprint(f"[OK] - {package}")
        return globals()[package]
    except Exception as e:
        vprint(e)
        vprint(f"[WARNING] You are missing a package required to run this script: {package} - attempting to install...")

        install = subprocess.check_call([sys.executable, "-m", "pip", "install", package])

        if install == 0:
            vprint(f"[SUCCESS] Package {package} sucessfully installed!")
            # globals()[package] = __import__(package)
            # return globals()[package]
            return __import__(package)
        else:
            print(f"Unable to install required package: {package}.")
            print(f"You can attempt to manually install this package by doing \"pip install {package}\"")
            return False
            exit(f"Exiting...")