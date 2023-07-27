try:
    import subprocess, sys
except Exception as e:
    print(e)
    exit("Something is seriously wrong with your Python installation... Bye.")


# ---------------------------------------------------------------------------- #
#                           Import required packages                           #
# ---------------------------------------------------------------------------- #
def importer_import(package: str, silent: bool=True):
    """
    USAGE: Define a variable and call this function with package you want to install
    EXAMPLE:
        ff = importer_import('ffmpeg')
    IS EQUAL TO:
        import ffmpeg as ff

    Or you can add it to the global scope, for example in a for loop:
    
    import utils.importer as imp
    packages = ["os", "time", "random"]
    for p in packages:
        globals()[p] = imp.importer_import(p):
    tk = imp.importer_import("tkinter")
    """
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