Set oShell = CreateObject ("Wscript.Shell") 
Dim strArgs
strArgs = "cmd /c %USERPROFILE%\.vim\wincmds\taskscheduler.cmd"
oShell.Run strArgs, 0, false