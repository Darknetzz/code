import importlib
from types import ModuleType
from typing import Optional, Union


def importer_import_new(importName: str, pipName: Optional[str] = None, verbose: bool = False) -> Union[ModuleType, bool]:
    """Import a module and print a clear install hint instead of mutating the environment."""
    package_name = pipName or importName

    def vprint(txt: str) -> None:
        if verbose:
            print(txt)

    try:
        module = importlib.import_module(importName)
        globals()[importName] = module
        vprint(f"[OK] - {importName}")
        return module
    except ImportError as exc:
        vprint(exc)
        print(f"Missing required package: {importName}")
        print(f"Install it with: python -m pip install {package_name}")
        return False
        

# ---------------------------------------------------------------------------- #
#                           Import required packages                           #
# ---------------------------------------------------------------------------- #
# ──────────────────────────────── DEPRECATED ──────────────────────────────── #
# This function is 'replaced' by importer_import_new to support packages with differing
# import names and pip install names. It is highly recommended you use that one instead!
def importer_import(package: str, silent: bool=True, ignoreDeprecated: bool=False):
    if not ignoreDeprecated:
        print(f"""
          [WARNING - DEPRECATED]
          Function importer_import from {__file__} is deprecated.
          You can still use it, but it is recommended that you use importer_import_new function instead.
          For more information, see https://github.com/Darknetzz/code/tree/main/Python/utils""")
    
    def vprint(txt):
        if not silent:
            print(txt)

    try:
        module = importlib.import_module(package)
        globals()[package] = module
        vprint(f"[OK] - {package}")
        return module
    except ImportError as e:
        vprint(e)
        print(f"Missing required package: {package}")
        print(f"Install it with: python -m pip install {package}")
        return False