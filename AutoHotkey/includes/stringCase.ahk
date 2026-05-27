; Copy selection → transform → paste; restore clipboard after a short delay.

TransformSelection(transformFn) {
    saved := ClipboardAll()
    try {
        A_Clipboard := ""
        SendMode "Input"
        Send "^c"
        ; Second param 1 = wait until clipboard *has* data (default waits for empty!)
        if !ClipWait(2, 1)
            return
        text := A_Clipboard
        if (text = "")
            return
        A_Clipboard := transformFn(text)
        Sleep 30
        Send "^v"
    } finally {
        SetTimer(RestoreClipboard.Bind(saved), -250)
    }
}

RestoreClipboard(saved, *) {
    A_Clipboard := saved
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
