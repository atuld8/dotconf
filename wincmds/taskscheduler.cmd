@REM this script is to update the dotconfig in the cygwin and cmd.exe
@REM Configure task scheduler job to execute this file.

@ECHO OFF

@REM For Windows platform
@SET PATH=%PATH%;C:\Program Files\Git\cmd;
%WINDIR%\system32\cmd.exe /c "cd /d %USERPROFILE%\.vim && git pull >NUL 2>NUL"

@REM For Cygwin platform
%CYGPATH%\bin\bash.exe -c "cd ~/.vim && git pull >/dev/null 2>/dev/null"
