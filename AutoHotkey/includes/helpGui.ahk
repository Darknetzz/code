; Help / control panel — shown when main.ahk starts (unless --silent / -s).

global helpGui := ""

CASE_TRANSFORM_ROWS := [
    ["UPPERCASE", "Win+Ctrl+U", "hello → HELLO"],
    ["lowercase", "Win+Ctrl+L", "HELLO → hello"],
    ["Title Case", "Win+Ctrl+T", "hello world → Hello World"],
    ["rAnDoM cAsE", "Win+Ctrl+R", "mixed letters"],
    ["slug", "Win+Ctrl+S", "Hello World! → hello-world"],
]

InitHelpGui() {
    global helpGui

    helpGui := Gui("+Resize -MaximizeBox", "AutoHotkey — " A_ScriptName)
    helpGui.BackColor := "1e1e1e"
    helpGui.SetFont("s10 cFFFFFF", "Segoe UI")
    helpGui.OnEvent("Close", (*) => helpGui.Hide())

    helpGui.Add("Text", "w460 Center", "Hotkeys stay active while this window is hidden.")
    helpGui.Add("Text", "w460 Center cA0A0A0", "Win+Ctrl+H — show this panel again")

    helpGui.Add("GroupBox", "w460 Section", "Case transforms (select text first)")
    hotkeyList := helpGui.Add("ListView", "w440 h118 -Hdr", ["Action", "Hotkey", "Example"])
    hotkeyList.ModifyCol(1, 100)
    hotkeyList.ModifyCol(2, 110)
    hotkeyList.ModifyCol(3, 210)
    for row in CASE_TRANSFORM_ROWS
        hotkeyList.Add(, row[1], row[2], row[3])

    helpGui.Add("GroupBox", "w460 Section", "Script")
    reloadBtn := helpGui.Add("Button", "x20 yp+10 w100", "Reload")
    editBtn := helpGui.Add("Button", "x+10 yp w100", "Edit")
    hideBtn := helpGui.Add("Button", "x+10 yp w100", "Hide")
    exitBtn := helpGui.Add("Button", "x+10 yp w100", "Exit")

    reloadBtn.OnEvent("Click", ReloadMain)
    editBtn.OnEvent("Click", EditMain)
    hideBtn.OnEvent("Click", (*) => helpGui.Hide())
    exitBtn.OnEvent("Click", (*) => ExitApp())

    helpGui.Add("Text", "w460 Section c808080", "Path: " AHK_ROOT)
    helpGui.Show("AutoSize Center")

    if ShouldStartSilent()
        helpGui.Hide()
}

ShouldStartSilent() {
    for arg in A_Args
        if (arg = "--silent" || arg = "-s")
            return true
    return false
}

ShowHelpGui(*) {
    global helpGui
    if !helpGui
        return
    helpGui.Show()
    WinActivate(helpGui)
}

#^h::ShowHelpGui()
