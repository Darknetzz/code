# PowerShell

Scripts and projects in PowerShell.

| Script / topic | Description |
|----------------|-------------|
| [Analyze-EventLogs.ps1](Analyze-EventLogs.ps1) | Summarizes recurring Windows Event Viewer entries with configurable lookback. Run: `.\Analyze-EventLogs.ps1 -DaysBack 7` or `.\Analyze-EventLogs.ps1 -DaysBack 14 -Output Html -OutputPath .\event-report.html`. |
| [RefreshEnv.ps1](RefreshEnv.ps1) | Refreshes environment variables in the **current** session from User and Machine registry (Path = Machine + User). Run: `. .\RefreshEnv.ps1` (dot-source). |
| refreshenv (Go) | For a compiled option that can also spawn a new shell or emit commands, see [Go/refreshenv](../Go/refreshenv/). Use `refreshenv.exe -emit &#124; iex` to refresh the current session. |
