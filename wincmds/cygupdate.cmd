@PUSHD %CYGPATH%
@SET PATH=%CYGPATH%\bin;%PATH%
@wget -N https://cygwin.com/setup-x86_64.exe
@takeown /A /F setup-x86_64.exe
@icacls setup-x86_64.exe /grant administrators:F /t
@setup-x86_64.exe --no-desktop --no-shortcuts --no-startmenu --quiet-mode
@POPD
