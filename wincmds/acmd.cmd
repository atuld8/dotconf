@ECHO OFF 
%SystemRoot%\System32\cmd.exe /k "@SET PATH=%PATH%;%userprofile% && @echo Initializing... This may take some time... && color a && %userprofile%\alias.cmd && cls"

