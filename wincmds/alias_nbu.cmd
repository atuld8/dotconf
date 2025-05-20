@call %~dp0alias_vrts.cmd %*

@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_NBU

@DOSKEY a.nb=DOSKEY /macros:all ^| findstr "\.nb\..*=" ^| findstr /v "[0-9A-Za-z]\.nb\..*=" $*
@DOSKEY a.nbc=DOSKEY /macros:all ^| findstr "\.nbc\..*=" $*
@DOSKEY a.oc=DOSKEY /macros:all ^| findstr "oc\..*=" ^| findstr /V "\.oc\..*=" $*
@DOSKEY a.nb.all=DOSKEY /macros:all ^| findstr "nb\..*= bmr\..*=" $*

@DOSKEY x.nb.logcln=DEL /S /Q "%%NBU_INST_PATH%%"NetBackup\logs\*.log
@DOSKEY x.nb.ff=FORFILES /S /P "%%NBU_INST_PATH%%." /C "cmd /c echo @path" $*

@DOSKEY e.nb.ver=%%CFG_EDITOR%% "%%NBU_INST_PATH%%NetBackup\version.txt" $*
@DOSKEY e.nb.logconf=%%CFG_EDITOR%% "%%NBU_INST_PATH%%NetBackup\nblog.conf" $*
@DOSKEY e.nb.nbsdj=%%CFG_EDITOR%% "%%NBU_INST_PATH%%NetBackup\nbsmartdiag.json" $*
@DOSKEY e.nb.svrconf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackupDB\CONF\server.conf" $*
@DOSKEY e.nb.vxdbmsconf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackupDB\data\vxdbms.conf" $*
@DOSKEY e.nb.usercert=%%CFG_EDITOR%% "%userprofile%\AppData\Roaming\VxSS\credentials" $*
@DOSKEY e.nb.at.linfo=@IF NOT EXIST %userprofile%\atlogin$*.info ( @echo Uses the authentication type, domain, user name, password, and broker ^> %userprofile%\atlogin$*.info ^&^& ( @echo WINDOWS^& @echo %COMPUTERNAME%^&@echo %USERNAME%^&@echo.)^>^> %userprofile%\atlogin$*.info ^&^& %%CFG_EDITOR%% %userprofile%\atlogin$*.info ) ELSE %%CFG_EDITOR%% %userprofile%\atlogin$*.info
@DOSKEY e.nb.db.op=%%CFG_EDITOR%% dbisqlc.output.txt $*
@DOSKEY e.bmr.bndl=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackupDB\BareMetal\client\data\bundle.dat" $*
@DOSKEY e.nb.java.authconf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackup\java\auth.conf" $*
@DOSKEY e.nb.java.authconf.tmplt=%%CFG_EDITOR%% "%%NBU_CONF_PATH%NetBackup\java\auth.conf.win.template" $*
@DOSKEY e.nb.at.conf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%NetBackup\var\global\vxss\eab\data\systemprofile\VRTSatlocal.conf" $*
@DOSKEY e.nb.java.debug=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackup\Java\Debug.properties" $*
@DOSKEY e.nb.java.setconf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackup\Java\setConf.bat" $*
@DOSKEY e.bmr.clixml=%%CFG_EDITOR%% "%%NBU_CONF_PATH%%NetBackupDB\BareMetal\client\data\bmrcli.xml" $*
@DOSKEY e.nbc.at.conf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%NetBackup\var\vxss\at\systemprofile\VRTSatlocal.conf" $*
@DOSKEY e.nb.at.local.conf=%%CFG_EDITOR%% "%%NBU_CONF_PATH%NetBackup\var\vxss\at\systemprofile\VRTSatlocal.conf" $*


@DOSKEY cat.nb.ver=type "%%NBU_INST_PATH%%"NetBackup\version.txt $*
@DOSKEY cat.nb.logconf=type "%%NBU_INST_PATH%%"NetBackup\nblog.conf $*
@DOSKEY cat.nb.svrconf=type "%%NBU_CONF_PATH%%"NetBackupDB\CONF\server.conf $*
@DOSKEY cat.nb.vxdbmsconf=type "%%NBU_CONF_PATH%%"NetBackupDB\data\vxdbms.conf $*
@DOSKEY cat.nb.db.op=type dbisqlc.output.txt $*

@DOSkEY cd.nbtstdt=IF EXIST "%SystemDrive%\nbtestdata\$*" ( %~dp0cd.cmd %SystemDrive%\nbtestdata\$* ) ELSE ( mkdir "%SystemDrive%\nbtestdata\$*" ^& %~dp0cd.cmd %SystemDrive%\nbtestdata\$* 2> NUL )

@DOSKEY cd.nb.instlogs=%~dp0cd.cmd "%allusersprofile%"\VERITAS\netBackup\InstallLogs\$*
@DOSKEY cd.nb.instlogssym=%~dp0cd.cmd "%allusersprofile%"\Symantec\netBackup\InstallLogs\$*
@DOSKEY cd.oc.instlogs=%~dp0cd.cmd "%allusersprofile%"\Symantec\opsCenter\InstallLogs\$*

@DOSKEY cd.nb=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\$*
@DOSKEY cd.nb.logs=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\logs\$*
@DOSKEY cd.nb.bin=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\bin\$*
@DOSKEY cd.nb.adm=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\bin\admincmd\$*
@DOSKEY cd.nb.gd=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\bin\goodies\$*
@DOSKEY cd.nb.at=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\sec\at\bin\$*
@DOSKEY cd.nb.az=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\sec\az\bin\$*
@DOSKEY cd.nb.var=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\var\$*
@DOSKEY cd.nb.vgbl.clust.loc=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\var\global\$*
@DOSKEY cd.nb.vgbl=%~dp0cd.cmd "%%NBU_CONF_PATH%%"NetBackup\var\global\$*
@DOSKEY cd.nb.eab=%~dp0cd.cmd "%%NBU_CONF_PATH%%"NetBackup\var\global\vxss\eab\data\$*
@DOSKEY cd.nb.eaz=%~dp0cd.cmd "%%NBU_CONF_PATH%%"NetBackup\var\global\vxss\eaz\data\$*
@DOSKEY cd.nb.vxuprepo=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\var\global\repo\$*
@DOSKEY cd.nb.report=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\var\global\report\$*
@DOSKEY cd.oc=%~dp0cd.cmd "%%OC_INST_PATH%%"\OpsCenter\$*
@DOSKEY cd.nb.volmgr=%~dp0cd.cmd "%%NBU_INST_PATH%%"volmgr\bin\$*
@DOSKEY cd.nb.odb=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackupDB\$*
@DOSKEY cd.nb.odb.bin=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackupDB\bin\$*
@DOSKEY cd.nb.odb.conf.clust.loc=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackupDB\Conf\$*
@DOSKEY cd.nb.odb.conf=%~dp0cd.cmd "%%NBU_CONF_PATH%%"NetBackupDB\Conf\$*
@DOSKEY cd.nb.odb.log=IF EXIST "%%NBU_INST_PATH%%"NetBackupDB\data\instance\log\ ( %~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackupDB\data\instance\log\$* ) ELSE ( %~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackupDB\log\$* )
@DOSKEY cd.nb.odb.data.clust.loc=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackupDB\data\$*
@DOSKEY cd.nb.odb.data=%~dp0cd.cmd "%%NBU_CONF_PATH%%"NetBackupDB\data\$*
@DOSKEY cd.nb.bkpcomp=%~dp0cd.cmd "%%NBU_INST_PATH%%"bkpcomp\$*
@DOSKEY cd.nb.wmc=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\wmc\$*
@DOSKEY cd.nb.wmcinstall=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\wmc\bin\install\$*
@DOSKEY cd.nb.tc=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\wmc\webserver\$*
@DOSKEY cd.nb.java=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\java\$*
@DOSKEY cd.nb.jre=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\jre\bin\$*
@DOSKEY cd.nb.db=%~dp0cd.cmd  "%%NBU_CONF_PATH%%"NetBackup\db\$*
@DOSKEY cd.nb.trylogs=%~dp0cd.cmd  "%%NBU_CONF_PATH%%"NetBackup\db\jobs\trylogs\$*
@DOSKEY cd.nb.floc=%~dp0cd.cmd  "%%NBU_CONF_PATH%%"NetBackup\db\images\$*
@DOSKEY cd.nb.pbx=%~dp0cd.cmd  "%SystemDrive%\Program Files (x86)"\VERITAS\VxPBX\$*
@DOSKEY cd.nb.vxms=%~dp0cd.cmd  "%SystemDrive%\Program Files\Common Files"\VERITAS\VxMS\$*
@DOSKEY cd.nb.usercert=%~dp0cd.cmd "%userprofile%"\AppData\Roaming\VxSS
@DOSKEY cd.nb.temp=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\Temp\$*
@DOSKEY cd.nb.rjc=%~dp0cd.cmd "%%NBU_INST_PATH%%"Java\$*
@DOSKEY cd.nb.tir=%~dp0cd.cmd  "%%NBU_CONF_PATH%%"NetBackup\tir_info\$*
@DOSKEY cd.bmr.sd=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\BareMetal\server\data\$*
@DOSKEY cd.bmr.cd=%~dp0cd.cmd "%%NBU_INST_PATH%%"NetBackup\BareMetal\client\data\$*


@DOSKEY x.md.nbprimaryplats..p=mkdir $*/AMD64 $*/solaris $*/solaris_x86 $*/linuxR_x86 $*/linuxS_x86

@DOSKEY r.nb.cfg=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config$*
@DOSKEY r.nb.cv=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion$*
@DOSKEY r.nb.clust=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\Cluster\Instance1$*
@DOSKEY r.nb.rjc=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas  /k /f "NetBackup - Java" /reg:64
@DOSKEY r.pbx=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\Veritas\VxPBX$*
@DOSKEY r.lk.nb=REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit /v LastKey /t REG_SZ /d Computer\HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\Config /f ^& regedit
@DOSKEY r.lk.pbx=REG ADD HKCU\Software\Microsoft\Windows\CurrentVersion\Applets\Regedit /v LastKey /t REG_SZ /d Computer\HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\Veritas\VxPBX /f ^& regedit
@DOSKEY r.nb.setvxmslog=REG ADD HKLM\SOFTWARE\Veritas\NetBackup\CurrentVersion\Config /v VXMS_VERBOSE /t REG_DWORD /f /d $*
@DOSKEY r.nb.setlog=REG ADD HKLM\SOFTWARE\Veritas\NetBackup\CurrentVersion\Config /v VERBOSE /t REG_DWORD /f /d $*
@DOSKEY r.nb.uninst=REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Veritas NetBackup" /v UninstallString
@DOSKEY r.nb.uninstsym=REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Symantec NetBackup" /v UninstallString
@DOSKEY r.nbc.uninst=REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Veritas NetBackup client" /v UninstallString
@DOSKEY r.nbc.uninstsym=REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Symantec NetBackup client" /v UninstallString
@DOSKEY .nb.path=@FOR /F "tokens=1,2,*" %%a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion /v INSTALLDIR ^^^|findstr /ri "REG_SZ"') do @ECHO %%c
@DOSKEY .nb.ver=(@FOR /F "tokens=1,* delims=REG_SZ " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion 2^^^>NUL^^^|findstr "BuildID"') DO @ECHO %%a                %%b)^&(@FOR /F "tokens=1,* delims=REG_SZ " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion 2^^^>NUL^^^|findstr "FullVersion"') DO @ECHO %%a            %%b)^&(@FOR /F "tokens=1,2,3,* delims= " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion 2^^^>NUL^^^|findstr "Install\ Type"') DO @ECHO %%a %%b           %%d)^&(@FOR /F "tokens=1,2,* " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config 2^^^>NUL^^^|findstr "EMMSERVER"') DO @echo Primary                %%c)^&(@FOR /F "tokens=1,2,* " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config /v Server /se " " 2^^^>NUL^^^|findstr "Server"') DO @echo %%a                 %%c)^&(@FOR /F "tokens=1,2,* " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config 2^^^>NUL^^^|findstr "Client_Name"') DO @ECHO %%a            %%c)^&(@FOR /F "tokens=1,2,* " %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config 2^^^>NUL^^^|findstr "Cluster_Name"') DO @ECHO %%a           %%c)
@DOSKEY x.testOps="%BUILD_DIR%\..\dest\AMD64\OpsCenter\setup.exe" -Debug -NoInstall $*

@DOSKEY set.nb.instpath=@FOR /F "tokens=1,2,*" %%a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion /v INSTALLDIR ^^^|findstr /ri "REG_SZ"') do @SET NBU_INST_PATH=%%c^& @SET NBU_CONF_PATH=%%c
@DOSKEY set.nb.clust.instpath=@FOR /F "tokens=1,2,*" %%a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion /v INSTALLDIR ^^^|findstr /ri "REG_SZ"') do @SET NBU_INST_PATH=%%c
@DOSKEY set.nb.clust.confpath=@FOR /F "tokens=1,2,*" %%a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\Cluster\Instance1 /v NetBackupSharedDrive ^^^|findstr /ri "REG_SZ"') do @SET NBU_CONF_PATH=%%c\
@DOSKEY set.nb.clust.dbserver=@FOR /F "tokens=1,2,*" %%a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\Cluster\Instance1 /v VirtualServerName ^^^|findstr /ri "REG_SZ"') do @SET NBUDB_SERVER=%%c

@REM NBU misc commands for quick ref
@DOSKEY .nb.con=cmd /c ""%%NBU_INST_PATH%%"NetBackup\java\nbjava.bat"
@DOSKEY .nb.killbpps=@FOR /f "tokens=1,2" %%a in ('bpps -S ^^^| FINDSTR /v /c:"bpps"') DO @ECHO "killing the %%a %%b" ^&^& TASKKILL /F /PID %%b
@DOSKEY .nb.cfg=bpgetconfig -s "localhost" -L $*
@DOSKEY .nb.db.pass=nbdb_admin -dba $*
@DOSKEY .nb.db.pass.def=nbdb_admin -dba nbusql
@DOSKEY .nb.propchg=bpgetconfig -d $*
@DOSKEY .nb.jb.actv=bpdbjobs -summary $* ^&^& bpdbjobs $* ^| findstr /v /c:"Done"
@DOSKEY .nb.jb=bpdbjobs -report $*
@DOSKEY .nb.jb.keep4hr=bpdbjobs -clean -keep_hours 4 $*
@DOSKEY .nb.jb.rstrt=bpdbjobs -restart $*
@DOSKEY .nb.jb.sum=bpdbjobs -summary $* ^&^& %%ES%% ^&^& bpdbjobs -report $*
@DOSKEY .nb.jb.trylog=findstr LOG "%%NBU_CONF_PATH%%NetBackup\db\jobs\trylogs\$*.t"
@DOSKEY .nb.jb.dtls=bpdbjobs.exe -jobid $* -report -all_columns  ^| perl -pe "s{\\,}{_COMMA_}g;s{,}{\n}g; s{_COMMA_}{,}g;s{([^\n])(\d{2}/\d{2}/\d{4})}{$1\n$2}g;" ^| perl -ne "print if  m{^\d{2}/\d{2}/\d{4}}"
@DOSKEY .nb.jb.10=bpdbjobs.exe ^| findstr /n . ^| findstr "^[0-9]: "
@DOSKEY .nb.cc=cat_convert -dump $*
@DOSKEY .nb.restart=bpdown -v -f ^&^& bpup -v -f
@DOSKEY .nb.mux=echo https://%%NBUDB_SERVER%%:1556/webui/login
@DOSKEY .nb.apidoc=echo https://%%NBUDB_SERVER%%/api-docs/index.html
@REM HIDDEN / NOT DOCUMENTED CMDS
@DOSKEY .nb.vxlcall=vxlogcfg -a -p 51216 -o Default -s DebugLevel=$*
@DOSKEY .nb.vxlc6=vxlogcfg -a -p 51216 -s DebugLevel=6 -o $*
@DOSKEY .nb.vxlc0=vxlogcfg -r -p 51216 -s DebugLevel -o $*
@DOSKEY .nb.vxlcls=vxlogcfg -l -p 51216 $*
@DOSKEY .nb.vxlmcln=vxlogmgr --auto --del -q $*
@DOSKEY .nb.vxlfids=findstr "OIDNames" "%%NBU_INST_PATH%%\NetBackup\nblog.conf" $*
@DOSKEY .nb.vxlv.prnt=echo vxlogview -G . -b "%%date:~4,2%%/%%date:~7,2%%/%%date:~-2%% %%time:~0,2%%:%%time:~3,2%%:%%time:~6,2%% AM" $*
@DOSKEY .nb.vxlv10min=vxlogview -G . -t 00:10:00 $*
@DOSKEY .nb.vxlv60min=vxlogview -G . -t 01:00:00 $*
@DOSKEY .nb.vxlv24h=vxlogview -G . -t 23:59:59 $*
@DOSKEY .nb.vxlvall=vxlogview -G . -p 51216 -d all $*
@DOSKEY .nb.x509=vxsslcmd x509 -text -noout -fingerprint -sha1 -in $*
@DOSKEY .nb.x509chn=vxsslcmd crl2pkcs7 -nocrl -certfile $* ^| vxsslcmd pkcs7 -print_certs -text -noout
@DOSKEY .nb.jver="%%NBU_INST_PATH%%NetBackup\jre\bin\java.exe" -version
@DOSKEY .nb.tcver="%%NBU_INST_PATH%%NetBackup\wmc\bin\setenv.bat" ^> NUL ^&^& pushd "%%NBU_INST_PATH%%NetBackup\wmc\webserver\bin" ^&^& version.bat ^&^& popd

@DOSKEY .nb.at.login=bpnbat -login ^&^& bpnbat -whoami
@DOSKEY .nb.at.login.auto=bpnbat -login -Info %userprofile%\atlogin$*.info ^&^& bpnbat -whoami
@DOSKEY .nb.at.loginweb=bpnbat -login -LoginType WEB ^&^& bpnbat -whoami
@DOSKEY .nb.at.loginweb.auto=bpnbat -login -Info %userprofile%\atlogin$*.info -LoginType WEB ^&^& bpnbat -whoami

@DOSKEY .nb.uninst=@for /f "tokens=2,*" %%a in ('REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Veritas NetBackup" /v UninstallString^^^|findstr "UninstallString"') do %%b
@DOSKEY .nbc.uninst=@for /f "tokens=2,*" %%a in ('REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Veritas NetBackup client" /v UninstallString^^^|findstr "UninstallString"') do %%b

@DOSKEY .nb.nbwebuser..p=net user nbwebsvc $* /add ^&^& net localgroup nbwebgrp /add ^&^& net localgroup nbwebgrp nbwebsvc /add
@DOSKEY .nb.sv.del.s1=wmic service where "displayname like '%%netbackup%%'" get name ^| findstr /V "^Name *$" $*
@DOSKEY .nb.sv.del.s2=for /f "tokens=*" %%s in (nbuservicelist.txt) do ( echo sc delete  "%%s" ) $*
@DOSKEY .nb.jreup="%%NBU_INST_PATH%%NetBackup\bin\goodies\nbcomponentupdate.exe" -pro netbackup -comp jre $*

@DOSKEY wmic.nb.svc=wmic service where "displayname like '%%netbackup%%'" get name
@DOSKEY wmic.nb.list=wmic product where "name like '%%NetBackup%%'" list brief
@DOSKEY wmic.nb.uninst=wmic product where "name like '%%NetBackup%%'" call uninstall

@DOSKEY bpdown=bpdown -v -f $*
@DOSKEY bpup=bpup -v -f $*

@DOSKEY cp.nb.mstr=@for /f "Tokens=3" %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config /v EMMSERVER') do @echo^|set /p=%%a^|clip
@DOSKEY cp.nb.svr=@for /f "Tokens=3" %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config /v Server /se " "') do @echo^|set /p=%%a^|clip
@DOSKEY cp.nb.clnt=@for /f "Tokens=3" %%a in ('reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\config /v Client_Name') do @echo^|set /p=%%a^|clip
@DOSKEY cp.nb.bin=echo^|set /p=%%nbin%%^|clip
@DOSKEY cp.nb.logs=echo^|set /p=%%NBU_INST_PATH%%NetBackup\logs^|clip
@DOSKEY cp.nb.win.path=echo @SET PATH=^^^^%%PATH^^^^%%;%%NBU_INST_PATH%%\NetBackup\bin;%%NBU_INST_PATH%%\NetBackup\bin\admincmd;%%NBU_INST_PATH%%\NetBackup\bin\goodies;%%NBU_INST_PATH%%\NetBackup\sec\at\bin;%%NBU_INST_PATH%%\NetBackup\bin\support;^|clip
@DOSKEY cp.nb.unix.path=echo export PATH=$PATH:/usr/openv/netbackup/bin/admincmd:/usr/openv/netbackup/bin:/usr/openv/db/bin:/usr/openv/netbackup/bin/goodies:/usr/openv/netbackup/bin/support:/usr/openv/netbackup/sec/at/bin:/usr/openv/volmgr/bin^|clip


:QA_ALIAS_NBU

@IF NOT DEFINED NBU_INST_PATH @SET NBU_INST_PATH=C:\Program Files\Veritas\
@IF NOT DEFINED NBU_CONF_PATH @SET NBU_CONF_PATH=C:\Program Files\Veritas\
@IF NOT DEFINED NBUDB_SERVER @SET NBUDB_SERVER=%COMPUTERNAME%
@IF NOT DEFINED OC_INST_PATH @SET OC_INST_PATH=C:\Program Files\Symantec\

REG query "HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion" >NUL 2>NUL
IF %ERRORLEVEL% EQU 0 CALL :SET_NBU_PATHS

@DOSKEY set.p.nb=@SET PATH=%%PATH%%;%%NBU_INST_PATH%%NetBackup\bin;%%NBU_INST_PATH%%NetBackup\bin\admincmd;%%NBU_INST_PATH%%NetBackup\bin\goodies;%%NBU_INST_PATH%%NetBackupDB\WIN64;%%NBU_INST_PATH%%NetBackupDB\bin;%%NBU_INST_PATH%%Volmgr\bin;%%NBU_INST_PATH%%pdde;%%NBU_INST_PATH%%NetBackup\bin\support;%%NBU_INST_PATH%%NetBackup\wmc\bin;%%NBU_INST_PATH%%NetBackup\sec\at\bin;%%NBU_INST_PATH%%NetBackup\sec\az\bin;%%NBU_INST_PATH%%NetBackup\jre\bin;

@IF NOT DEFINED ALREADY_SET_THE_NBU_PATH @SET PATH=%PATH%;%NBU_INST_PATH%NetBackup\bin;%NBU_INST_PATH%NetBackup\bin\admincmd;%NBU_INST_PATH%NetBackup\bin\goodies;%NBU_INST_PATH%NetBackupDB\WIN64;%NBU_INST_PATH%NetBackupDB\bin;%NBU_INST_PATH%Volmgr\bin;%NBU_INST_PATH%pdde;%NBU_INST_PATH%NetBackup\bin\support;%NBU_INST_PATH%NetBackup\wmc\bin;%NBU_INST_PATH%NetBackup\sec\at\bin;%NBU_INST_PATH%NetBackup\sec\az\bin;%NBU_INST_PATH%NetBackup\jre\bin; && @SET ALREADY_SET_THE_NBU_PATH=1

@SET nb="%NBU_INST_PATH%NetBackup"
@SET nbin="%NBU_INST_PATH%NetBackup\bin"
@SET nadm="%NBU_INST_PATH%NetBackup\bin\admincmd"
@SET ngds="%NBU_INST_PATH%NetBackup\bin\goodies"
@SET nlogs="%NBU_INST_PATH%NetBackup\logs"
@SET bmrcd="%NBU_INST_PATH%NetBackup\BareMetal\Client\data"
@SET nbdt=%SystemDrive%\nbdata
@SET cstdt=%SystemDrive%\custdata
@SET nbtstdt=%SystemDrive%\nbtestdata
@SET opv=%NBU_INST_PATH%


GOTO END_SCRIPT

:SET_NBU_PATHS
@FOR /F "tokens=1,2,*" %%a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion /v INSTALLDIR 2^>NUL ^|findstr /ri "REG_SZ"') do @SET NBU_INST_PATH=%%c&& @SET NBU_CONF_PATH=%%c
REG query "HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\Cluster\Instance1" >NUL 2>NUL
IF %ERRORLEVEL% EQU 0 CALL :SET_CONF_PATHS
ENDLOCAL

:SET_CONF_PATHS
FOR /F "tokens=1,2,*" %%a in ('REG QUERY "HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion\Cluster\Instance1" /v NetBackupSharedDrive 2^>NUL ^|findstr /ri "REG_SZ"') do @SET NBU_CONF_PATH=%%c\
ENDLOCAL

:END_SCRIPT

