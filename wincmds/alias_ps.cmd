@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_PS

@DOSKEY a.ps=%DOSKEY_ALL_MACROS% ^| findstr "ps\..*= \.ps.*=" $*
@DOSKEY .ps=powershell.exe $*
@DOSKEY .ps1=powershell.exe -File $*
@DOSKEY ps.unc=powershell.exe get-WmiObject -class Win32_Share -computer $*

:QA_ALIAS_PS

