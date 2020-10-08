@echo off
setlocal enabledelayedexpansion
set "lock=%temp%\wait.%random%.lock"

set /a r1=%random% %% 15
@REM set BG=0123456709BCDEF
@REM set FG=EF012345A79ABCD
set BG=01234500FEFE
set FG=EFB14F670455
call set rndcolor=%%BG:~%r1%,1%%%%FG:~%r1%,1%%


for /f %%a in ('dir /b /A:D') do (
    set RUN_BLD=1
    if "%%a" EQU ".git" set RUN_BLD=0
    if "%%a" EQU ".vscode" set RUN_BLD=0
    if "%%a" EQU "webgui" set RUN_BLD=0

    if "!RUN_BLD!" EQU "0" ECHO "Skipping for %%a"

    if "!RUN_BLD!" EQU "1" start "%CD%\%%a ==> nbbuild.pl --plat AMD64 --autojobs %* " /ABOVENORMAL /MIN 9>"%lock%_%%a" cmd -new_console:n /c "color %rndcolor% && prompt $v && cd %%a && perl %%BUILD_DIR%%\nbbuild\nbbuild.pl --plat AMD64 --autojobs %*"
)

echo waiting on child processes to finish

:Wait for all processes to finish (wait until lock files are no longer locked)
1>nul 2>nul ping /n 10 ::1
for %%F in ("%lock%*") do (
  (call ) 9>"%%F" || goto :Wait
) 2>nul

::delete the lock files
del "%lock%*"

:: Finish up
echo Done - ready to continue processing
