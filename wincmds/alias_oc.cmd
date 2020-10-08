@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_OC

@DOSKEY oc.srv.status=sc query OpsCenterWebServer ^& sc query OpsCenterServer ^& sc query SQLANYs_VERITAS_OPSCENTER ^& sc query OpsCenterAuthenticationBroker
@DOSKEY oc.srv.start="%%OC_INST_PATH%%"OpsCenter\server\bin\opsadmin.bat start $*
@DOSKEY oc.srv.stop="%%OC_INST_PATH%%"OpsCenter\server\bin\opsadmin.bat stop $*

@DOSKEY oc.vxl6="%%OC_INST_PATH%%"OpsCenter\server\bin\vxlogcfg -a -p 58330 -s DebugLevel=6 -o'
@DOSKEY oc.vxl0="%%OC_INST_PATH%%"OpsCenter\server\bin\vxlogcfg -a -p 58330 -s DebugLevel=0 -o'
@DOSKEY oc.vxlids=findstr OIDNames "%%OC_INST_PATH%%OpsCenter\server\config\log.conf" $*
@DOSKEY oc.vxlv="%%OC_INST_PATH%%"OpsCenter\server\bin\vxlogview -p 58330 $*

@DOSKEY cd.oc.srv=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\server\$*
@DOSKEY cd.oc.gui=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\gui\$*
@DOSKEY cd.oc.at=%~dp0cd.cmd  "%%OC_INST_PATH%%"OpsCenter\server\authbroker\bin\$*
@DOSKEY cd.oc.log=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\server\logs\$*
@DOSKEY cd.oc.cfg=%~dp0cd.cmd "%%OC_INST_PATH%%"OpsCenter\server\config\$*

@DOSKEY oc.web='echo https://%COMPUTERNAME%:443/opscenter'

@DOSKEY e.oc.atconf=%%CFG_EDITOR%% "%%OC_INST_PATH%%OpsCenter\server\authbroker\data\systemprofile\VRTSatlocal.conf" $*
@DOSKEY e.oc.log=%%CFG_EDITOR%% "%%OC_INST_PATH%%OpsCenter\server\config\log.conf" $*
@DOSKEY e.oc.server=%%CFG_EDITOR%% "%%OC_INST_PATH%%OpsCenter\server\config\server.conf" $*

@DOSKEY a.oc=%DOSKEY_ALL_MACROS% ^| findstr "oc\..*=" $*

:QA_ALIAS_OC

@SET PATH=%PATH%;%OC_INST_PATH%OpsCenter\server\bin
@SET PATH=%PATH%;%OC_INST_PATH%OpsCenter\gui\bin
@SET PATH=%PATH%;%OC_INST_PATH%OpsCenter\server\authbroker\bin;

