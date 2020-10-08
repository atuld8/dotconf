@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_OC

@DOSKEY .oc.svc.status=sc query OpsCenterWebServer ^& sc query OpsCenterServer ^& sc query SQLANYs_VERITAS_OPSCENTER ^& sc query OpsCenterAuthenticationBroker
@DOSKEY .oc.svc.start="%%OC_INST_PATH%%"OpsCenter\server\bin\opsadmin.bat start $*
@DOSKEY .oc.svc.stop="%%OC_INST_PATH%%"OpsCenter\server\bin\opsadmin.bat stop $*

@DOSKEY .oc.vxl6="%%OC_INST_PATH%%"OpsCenter\server\bin\vxlogcfg -a -p 58330 -s DebugLevel=6 -o'
@DOSKEY .oc.vxl0="%%OC_INST_PATH%%"OpsCenter\server\bin\vxlogcfg -a -p 58330 -s DebugLevel=0 -o'
@DOSKEY .oc.vxlids=findstr OIDNames "%%OC_INST_PATH%%OpsCenter\server\config\log.conf" $*
@DOSKEY .oc.vxlv="%%OC_INST_PATH%%"OpsCenter\server\bin\vxlogview -p 58330 $*

@DOSKEY cd.oc.svr=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\server\$*
@DOSKEY cd.oc.gui=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\gui\$*
@DOSKEY cd.oc.at=%~dp0cd.cmd  "%%OC_INST_PATH%%"OpsCenter\server\authbroker\bin\$*
@DOSKEY cd.oc.log=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\server\logs\$*
@DOSKEY cd.oc.cfg=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\server\config\$*
@DOSKEY cd.oc.respfile=%~dp0cd.cmd "%windir%\Temp\Symantec\OpsCenter\$*"
@DOSKEY cd.oc.instlogs=%~dp0cd.cmd "%ProgramData%\SYMANTEC\OpsCenter\InstallLogs\$*"

@DOSKEY .oc.web=echo https://%COMPUTERNAME%:443/opscenter $*

@DOSKEY e.oc.atconf=%%CFG_EDITOR%% "%%OC_INST_PATH%%OpsCenter\server\authbroker\data\systemprofile\VRTSatlocal.conf" $*
@DOSKEY e.oc.log=%%CFG_EDITOR%% "%%OC_INST_PATH%%OpsCenter\server\config\log.conf" $*
@DOSKEY e.oc.server=%%CFG_EDITOR%% "%%OC_INST_PATH%%OpsCenter\server\config\server.conf" $*

@DOSKEY a.oc=%DOSKEY_ALL_MACROS% ^| findstr "\.oc\..*=" $*

@DOSKEY ocver=(@FOR /F "tokens=1,* delims=REG_SZ " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Symantec\OpsCenter\Server 2^^^>NUL^^^|findstr "BuildVersion"') DO @ECHO %%a          %%b)^&(@FOR /F "tokens=1,* delims=REG_SZ " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Symantec\OpsCenter\Server 2^^^>NUL^^^|findstr "InstallDir"') DO @ECHO %%a            %%b)^&(@FOR /F "tokens=1,* delims=REG_SZ " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Symantec\OpsCenter\Server 2^^^>NUL^^^|findstr "ProductName"') DO @ECHO %%a           %%b)^&(@FOR /F "tokens=1,* delims=REG_SZ " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Symantec\OpsCenter\Server 2^^^>NUL^^^|findstr "\<Version"') DO @echo %%a               %%b)
@DOSKEY r.oc=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Symantec\OpsCenter\Server$*
@DOSKEY r.lk.oc=REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit /v LastKey /t REG_SZ /d Computer\HKEY_LOCAL_MACHINE\SOFTWARE\Symantec\OpsCenter\Server /f ^& regedit

@DOSKEY x.oc.ff=FORFILES /S /P "%%OC_INST_PATH%%." /C "cmd /c echo @path" $*

@DOSKEY cp.oc.logs=echo^|set /p=%%OC_INST_PATH%%OpsCenter\server\logs^|clip
@DOSKEY cp.oc.at=echo^|set /p=%%OC_INST_PATH%%OpsCenter\server\authbroker\bin^|clip
@DOSKEY cp.oc.svr=echo^|set /p=%%OC_INST_PATH%%OpsCenter\server\^|clip

@DOSKEY .oc.uninst=@for /f "tokens=2,*" %%a in ('REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Veritas NetBackup OpsCenter Server (64bit)" /v UninstallString^^^|findstr "UninstallString"') do %%b
@DOSKEY wmic.nb.uninst=wmic product where "name like '%%NetBackup OpsCenter%%'" call uninstall

:QA_ALIAS_OC

@SET PATH=%PATH%;%OC_INST_PATH%OpsCenter\server\bin
@SET PATH=%PATH%;%OC_INST_PATH%OpsCenter\gui\bin
@SET PATH=%PATH%;%OC_INST_PATH%OpsCenter\server\authbroker\bin;

