@REM SETX PROMPT $C$D$S$T$F$S$M[^%COMPUTERNAME^%]$S$P$S%EXTRA_PROMPT_DATA%$_$+^%SPECIAL_PRMPT_DATA^%$G$G$S >NUL
@REM SETX EXTRA_PROMPT_DATA $S >NUL
@REM SETX SPECIAL_PRMPT_DATA T$S >NUL
@REM SETX MVP %userprofile%\.vim
@REM SETX /M CYGPATH %CYGPATH%
@REM SETX JAVA_HOME ""%ProgramFiles%\Java\jdk1.8.0_xxx"


@DOSKEY m.rdpclip.restart=@For /f "tokens=1,2" %%a in ('tasklist.exe ^^^| findstr "rdpclip"') do taskkill /f /pid %%b ^&^& rdpclip ^&^& tasklist.exe ^| findstr "rdpclip"
@DOSKEY m.cpcmd=copy /Y %~dp0acmd.cmd %%windir%%\system32 ^& copy /Y %~dp0cygcmd.cmd %%windir%%\system32 ^& copy /Y %~dp0mini.cmd %%windir%%\system32 ^& copy /Y %~dp0qcmd.cmd %%windir%%\system32
@DOSKEY m.setx=@FOR /F "tokens=1,*" %%a in ('findstr /B /C:"@REM SETX " %~dp0alias_global.cmd %~dp0alias_odd.cmd') do @ECHO %%b
@DOSKEY m.ts=%~dp0taskscheduler.cmd
@DOSKEY m.cp.dk.gkf=copy /Y %userprofile%\alias.doskey %userprofile%\alias.doskey.gkf

@REM This is for debugging and coding related alias
@DOSKEY @winkit.v10=%~dp0cd.cmd "%ProgramFiles%\Windows Kits\10\Debuggers\x64" ^&^& $* ^& %~dp0cd.cmd -
@DOSKEY @winkit.v81=%~dp0cd.cmd "%ProgramFiles%\Windows Kits\8.1\Debuggers\x64" ^&^& $* ^& %~dp0cd.cmd -

@DOSKEY .windbg64.vstdaln="%SYSTEMDRIVE%\Program Files (x86)\Debugging Tools for Windows (x86)\windbg.exe" $*
@DOSKEY .windbg64.v10="%SYSTEMDRIVE%\Program Files (x86)\Windows Kits\10\Debuggers\x64\windbg.exe" $*
@DOSKEY .windbg64.v81="%SYSTEMDRIVE%\Program Files (x86)\Windows Kits\8.1\Debuggers\x64\windbg.exe" $*

@DOSKEY .updatecmd=(for /f %%f in ('where acmd.cmd') do copy /y %%userprofile%%\.vim\wincmds\acmd.cmd %%f) ^&^& (for /f %%f in ('where qcmd.cmd') do copy /y %%userprofile%%\.vim\wincmds\qcmd.cmd %%f) ^&^& (for /f %%f in ('where mini.cmd') do copy /y %%userprofile%%\.vim\wincmds\mini.cmd %%f)  ^&^& (for /f %%f in ('where cygcmd.cmd') do copy /y %%userprofile%%\.vim\wincmds\cygcmd.cmd %%f)