@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_VRTS

@DOSKEY cp.key=type "%userprofile%\keyfile.txt" ^| clip
@DOSKEY cp.nb.json.win=echo^|set /p=%SystemDrive%\nbdata\veritas_customer_registration_key.json^| clip
@DOSKEY cp.nb.json.winrmt=echo^|set /p=H:\veritas_customer_registration_key.json^| clip
@DOSKEY cp.nb.json.unix=echo^|set /p=/root/nbdata/veritas_customer_registration_key.json^| clip
@DOSKEY cp.nb.json.unixrmt=echo^|set /p=/public/adas/veritas_customer_registration_key.json^| clip
@DOSKEY cp.pne=echo ^|set /p=%%PNE%%^|clip
@DOSKEY cp.punin=echo ^|set /p=%%PUNIN%%^|clip
@DOSKEY cp.rsv=echo ^|set /p=%%RSV%%^|clip

@DOSKEY cd.sym=%~dp0cd.cmd "C:\Program Files\Symantec\$*"
@DOSKEY cd.vrts=%~dp0cd.cmd "C:\Program Files\Veritas\$*"

@DOSKEY cd.nbdt=IF EXIST "%systemDrive%\nbdata\$*" ( %~dp0cd.cmd %systemDrive%\nbdata\$* ) ELSE ( mkdir "%systemDrive%\nbdata\$*" ^& %~dp0cd.cmd %systemDrive%\nbdata\$* 2^> NUL )
@DOSKEY cd.qTE=%~dp0cd.cmd %systemDrive%\nbdata\quickTestEnv\$* 2^> NUL
@DOSKEY cd.cstdt=IF EXIST "%systemDrive%\custdata\$*" ( %~dp0cd.cmd %systemDrive%\custdata\$* ) ELSE ( mkdir "%systemDrive%\custdata\$*" ^& %~dp0cd.cmd %systemDrive%\custdata\$* 2^> NUL )

:QA_ALIAS_VRTS

