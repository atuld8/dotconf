@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_VRTS

@DOSKEY cp.key=type "%userprofile%\keyfile.txt" ^| clip
@DOSKEY cp.json.win=echo^|set /p=%SystemDrive%\nbudata\veritas_customer_registration_key.json^| clip
@DOSKEY cp.json.unix=echo^|set /p=/public/adas/veritas_customer_registration_key.json^| clip
@DOSKEY cp.pne=echo ^|set /p=%%PNE%%^|clip
@DOSKEY cp.punin=echo ^|set /p=%%PUNIN%%^|clip
@DOSKEY cp.rsv=echo ^|set /p=%%RSV%%^|clip

@DOSKEY cd.sym=%~dp0cd.cmd "C:\Program Files\Symantec\$*"
@DOSKEY cd.vrts=%~dp0cd.cmd "C:\Program Files\Veritas\$*"

@DOSKEY cd.l.nbudata=IF EXIST "%systemDrive%\nbudata\$*" ( %~dp0cd.cmd %systemDrive%\nbudata\$* ) ELSE ( mkdir "%systemDrive%\nbudata\$*" ^& %~dp0cd.cmd %systemDrive%\nbudata\$* 2^> NUL )
@DOSKEY cd.l.qTE=%~dp0cd.cmd %systemDrive%\nbudata\quickTestEnv\$* 2^> NUL
@DOSKEY cd.l.custdata=IF EXIST "%systemDrive%\custdata\$*" ( %~dp0cd.cmd %systemDrive%\custdata\$* ) ELSE ( mkdir "%systemDrive%\custdata\$*" ^& %~dp0cd.cmd %systemDrive%\custdata\$* 2^> NUL )

:QA_ALIAS_VRTS

