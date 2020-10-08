@FOR /f "tokens=1-3" %%a in ('WMIC LOGICALDISK GET FreeSpace^^^,Name^^^,Size ^|FINDSTR /I /V "Name"') do  @If NOT "%%c" == "" ( @echo wsh.echo "%%b" ^& " free=" ^& FormatNumber^(cdbl^(%%a^)/1024/1024/1024, 2^)^& " GiB"^& " size=" ^& FormatNumber^(cdbl^(%%c^)/1024/1024/1024, 2^)^& " GiB" >> %temp%\tmp.vbs )
@cscript //nologo %temp%\tmp.vbs & 
@DEL %temp%\tmp.vbs 