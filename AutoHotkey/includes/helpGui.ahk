; Help / control panel — shown when main.ahk starts (unless --silent / -s).

global helpGui := ""

; VS Code–style dark palette
GUI_BG     := "1e1e1e"
GUI_PANEL  := "252526"
GUI_TEXT   := "cccccc"
GUI_DIM    := "858585"
GUI_ACCENT := "569cd6"

CASE_TRANSFORM_ROWS := [
    ["UPPERCASE", "Win+Ctrl+U", "hello → HELLO"],
    ["lowercase", "Win+Ctrl+L", "HELLO → hello"],
    ["Title Case", "Win+Ctrl+T", "hello world → Hello World"],
    ["rAnDoM cAsE", "Win+Ctrl+R", "mixed letters"],
    ["slug", "Win+Ctrl+S", "Hello World! → hello-world"],
]

InitHelpGui() {
    global helpGui

    helpGui := Gui("+Resize -MaximizeBox", "AutoHotkey")
    helpGui.BackColor := GUI_BG
    helpGui.MarginX := 20
    helpGui.MarginY := 16
    helpGui.OnEvent("Close", (*) => helpGui.Hide())

    helpGui.SetFont("s14 bold c" GUI_TEXT, "Segoe UI")
    helpGui.Add("Text", "w440", "AutoHotkey")

    helpGui.SetFont("s9 c" GUI_DIM, "Segoe UI")
    helpGui.Add("Text", "w440", "Select text in the target app, then press a shortcut (not this window)")
    helpGui.Add("Text", "w440 c" GUI_DIM, "Win+Ctrl+H — show this panel again")

    AddSpacer(helpGui, 6)

    helpGui.SetFont("s10 bold c" GUI_TEXT, "Segoe UI")
    helpGui.Add("Text", "w440 Section", "Case transforms")

    helpGui.SetFont("s9 c" GUI_DIM, "Segoe UI")
    helpGui.Add("Text", "xs w440", "Select text in any app, then press a shortcut.")

    hotkeyPanel := helpGui.Add("Edit", "ReadOnly -E0x200 w440 h132 Background" GUI_PANEL " c" GUI_TEXT, BuildHotkeyTable())
    hotkeyPanel.SetFont("s9", "Cascadia Mono")

    AddSpacer(helpGui, 8)

    helpGui.SetFont("s10 bold c" GUI_TEXT, "Segoe UI")
    helpGui.Add("Text", "w440 Section", "Script")

    AddActionLink(helpGui, "Reload", ReloadMain, "xs")
    AddActionLink(helpGui, "Edit", EditMain, "x+24 yp")
    AddActionLink(helpGui, "Hide", (*) => helpGui.Hide(), "x+24 yp")
    AddActionLink(helpGui, "Exit", (*) => ExitApp(), "x+24 yp cE06C75")

    AddSpacer(helpGui, 10)

    helpGui.SetFont("s8 c" GUI_DIM, "Segoe UI")
    helpGui.Add("Text", "w440 Section", AHK_ROOT)

    helpGui.Show("w480 AutoSize Center")

    if ShouldStartSilent()
        helpGui.Hide()
}

BuildHotkeyTable() {
    sep := "────────────────────────────────────────────────────────"
    header := Format("{:-14}  {:14}  {}", "Action", "Hotkey", "Example")
    lines := [header, sep]
    for row in CASE_TRANSFORM_ROWS
        lines.Push(Format("{:-14}  {:14}  {}", row[1], row[2], row[3]))
    return JoinLines(lines)
}

JoinLines(lines, delim := "`n") {
    out := ""
    for line in lines
        out .= (out = "" ? "" : delim) line
    return out
}

AddSpacer(gui, height) {
    gui.Add("Text", "h" height " w1", "")
}

AddActionLink(gui, label, callback, options := "") {
    gui.SetFont("s10 c" GUI_ACCENT " underline", "Segoe UI")
    link := gui.Add("Text", options " h22 +0x200", label)
    link.OnEvent("Click", callback)
    return link
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
