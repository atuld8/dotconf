@ECHO OFF 
%SystemRoot%\System32\cmd.exe /k "@SET PATH=%PATH%;%userprofile% && @echo Initializing... This may take some time... && color a && cd /d %userprofile%\.vim && git pull >NUL 2>NUL && cd /d %userprofile% && %userprofile%\alias.cmd && cls"

