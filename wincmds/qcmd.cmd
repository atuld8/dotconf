@ECHO OFF 
%SystemRoot%\System32\cmd.exe /k "@SET PATH=%userprofile%;%PATH%; && @echo Initializing... This may take some time... && %userprofile%\alias.cmd QUICK_ACCESS && cls"

