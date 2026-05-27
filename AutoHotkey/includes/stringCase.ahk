; Copy selection → transform → paste; restore clipboard after a short delay.

TransformSelection(transformFn) {
    ReleaseHotkeyModifiers()
    saved := ClipboardAll()
    try {
        A_Clipboard := ""
        SendInput "^c"
        if !ClipWait(2)
            return ShowTransformTip("Could not copy selection — select text first.")
        text := A_Clipboard
        if (text = "")
            return ShowTransformTip("Selection was empty.")
        A_Clipboard := transformFn(text)
        Sleep 50
        SendInput "^v"
    } finally {
        SetTimer(RestoreClipboard.Bind(saved), -300)
    }
}

; Win/Ctrl may still be down when the hotkey fires — release before Send ^c / ^v.
ReleaseHotkeyModifiers() {
    for key in ["LWin", "RWin", "Control", "Alt", "Shift"]
        if GetKeyState(key, "P")
            Send "{" key " up}"
    Sleep 50
}

RestoreClipboard(saved, *) {
    A_Clipboard := saved
}

ShowTransformTip(message) {
    ToolTip message
    SetTimer(() => ToolTip(), -2500)
}

ToTitleEachWord(text) {
    return RegExReplace(text, "(\S)(\S*)", TitleWordCallback)
}

TitleWordCallback(match, *) {
    return StrUpper(match[1]) StrLower(match[2])
}

ToRandomCase(text) {
    result := ""
    for char in StrSplit(text, "") {
        if RegExMatch(char, "\p{L}")
            result .= (Random(2) = 1 ? StrUpper(char) : StrLower(char))
        else
            result .= char
    }
    return result
}

ToSlug(text) {
    text := StrLower(Trim(text))
    text := RegExReplace(text, "[^\p{L}\p{N}]+", "-")
    return RegExReplace(text, "(^-+|-+$)", "")
}
