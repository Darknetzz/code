#Requires AutoHotkey v2.0
#SingleInstance Force

; Entry point — add new modules under hotkeys\ or apps\ and #Include them here.

#Include includes\env.ahk
#Include includes\functions.ahk
#Include includes\stringCase.ahk

; Global hotkeys
#Include hotkeys\case-transform.ahk
; #Include hotkeys\example.ahk

; Per-app scripts (#HotIf WinActive ...)
; #Include apps\example.ahk

#Include includes\helpGui.ahk
InitHelpGui()
