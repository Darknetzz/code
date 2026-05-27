; Paths and constants shared across scripts.
; Copy config\local.example.ini to config\local.ini (gitignored) for machine-specific values.

AHK_ROOT := A_ScriptDir
REPO_ROOT := RegExReplace(AHK_ROOT, "\\AutoHotkey$")
CONFIG_DIR := AHK_ROOT "\config"
LOCAL_INI := CONFIG_DIR "\local.ini"

LoadLocalConfig() {
    if !FileExist(LOCAL_INI)
        return
    ; Extend when you add keys to local.example.ini
}

LoadLocalConfig()
