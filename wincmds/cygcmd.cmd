@ECHO OFF 

SETLOCAL
PATH=%CYGPATH%\bin;%PATH%
@CD /d %cd%
%CYGPATH%\bin\mintty.exe -i /Cygwin-Terminal.ico --dir "%cd%" /bin/bash
ENDLOCAL

GOTO :EOF

@REM %CYGPATH%\bin\bash.exe --login -i -c "cd '%cd%' && bash"
