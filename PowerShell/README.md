# PowerShell

Scripts and projects in PowerShell.

| Script / topic | Description |
|----------------|-------------|
| [AD-Group.ps1](AD-Group.ps1) | Lists or exports Active Directory group members, or tests whether users belong to a group (wildcards, optional nested lookup). Run: `.\AD-Group.ps1` to be prompted, `.\AD-Group.ps1 -GroupName 'App-Admins'`, or `.\AD-Group.ps1 -Test -GroupName 'App-Admins' -UserName 'kr*'`. |
| [AD-User.ps1](AD-User.ps1) | Lists or exports the Active Directory groups a user belongs to (wildcards, optional nested lookup). Run: `.\AD-User.ps1` to be prompted, `.\AD-User.ps1 -UserName 'kriss'`, or `.\AD-User.ps1 -UserName 'kriss' -GroupName '*admin*' -Recursive`. |
| [Analyze-EventLogs.ps1](Analyze-EventLogs.ps1) | Summarizes recurring Windows Event Viewer entries with configurable lookback. Run: `.\Analyze-EventLogs.ps1` to create and open a temporary HTML report, or `.\Analyze-EventLogs.ps1 -DaysBack 7 -Output Terminal`. |
| [RefreshEnv.ps1](RefreshEnv.ps1) | Refreshes environment variables in the **current** session from User and Machine registry (Path = Machine + User). Run: `. .\RefreshEnv.ps1` (dot-source). |
| refreshenv (Go) | For a compiled option that can also spawn a new shell or emit commands, see [Go/refreshenv](../Go/refreshenv/). Use `refreshenv.exe -emit &#124; iex` to refresh the current session. |
