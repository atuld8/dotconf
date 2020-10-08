@SET EXTRA_PROMPT_DATA=$S&
@SET SPECIAL_PRMPT_DATA=T$S&
@SET PROMPT=$C$D$S$T$F$S$M[%COMPUTERNAME%]$S$P$S%EXTRA_PROMPT_DATA%$_$+$+%SPECIAL_PRMPT_DATA%$G$G$S

@DOSKEY alias=DOSKEY /macros:all $* &
@DOSKEY fa=DOSKEY /macros:all ^| findstr $* &
@FOR /F "tokens=1,2,*" %a in ('REG QUERY HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion /v INSTALLDIR ^|findstr /ri "REG_SZ"') do @SET NBU_INST_PATH=%c& @SET NBU_CONF_PATH=%c
@REM SET NBU_INST_PATH=C:\Program Files\Veritas\&
@SET OC_INST_PATH=C:\Program Files\Symantec\&
@DOSKEY cd.symc=cd /d "C:\Program Files\Symantec\$*" &
@DOSKEY cd.vrts=cd /d "C:\Program Files\Veritas\$*" &
@DOSKEY cd.nb=cd /d "%NBU_INST_PATH%NetBackup\$*" &
@DOSKEY cd.nb.bin=cd /d "%NBU_INST_PATH%NetBackup\bin\$*" &
@DOSKEY cd.nb.logs=cd /d "%NBU_INST_PATH%NetBackup\logs\$*" &
@DOSKEY cd.nb.adm=cd /d "%NBU_INST_PATH%NetBackup\bin\admincmd" &
@DOSKEY cd.nb.gd=cd /d "%NBU_INST_PATH%NetBackup\bin\goodies" &
@DOSKEY cd.nb.at=cd /d "%NBU_INST_PATH%NetBackup\sec\at\bin" &
@DOSKEY cd.nb.vgbl=cd /d "%NBU_INST_PATH%NetBackup\var\global\$*" &
@DOSKEY cd.oc=cd /d "%OC_INST_PATH%\OpsCenter\$*" &
@DOSKEY cd.nb.volmgr=cd /d "%NBU_INST_PATH%\volmgr\bin\$*" &
@DOSKEY cd.nb.db=cd /d "%NBU_INST_PATH%NetBackupDB\WIN64" &
@DOSKEY cd.nb.dbconf=cd /d "%NBU_INST_PATH%NetBackupDB\Conf\$*" &
@DOSKEY cd.nb.dblog=cd /d "%NBU_INST_PATH%NetBackupDB\log\$*" &
@DOSKEY cd.nb.dbdata=cd /d "%NBU_INST_PATH%NetBackupDB\data\$*" &
@DOSKEY cd.nb.wmcinstall=cd /d "%NBU_INST_PATH%NetBackup\wmc\bin\install" &
@DOSKEY cd.nb.tc=cd /d "%NBU_INST_PATH%NetBackup\wmc\webserver\$*" &
@DOSKEY cd.nb.java=cd /d "%NBU_INST_PATH%NetBackup\java\$*" &
@DOSKEY cd.nb.bmrsd=cd /d "%NBU_INST_PATH%NetBackup\BareMetal\server\data" &
@DOSKEY cd.nb.bmrcd=cd /d "%NBU_INST_PATH%NetBackup\BareMetal\client\data" &
@DOSKEY cd.nb.trylog=cd /d  "%NBU_INST_PATH%NetBackup\db\jobs\trylogs" &
@DOSKEY cd.nb.floc=cd /d  "%NBU_INST_PATH%NetBackup\db\images\$*" &

@DOSKEY cmd.nb.ff=FORFILES /S /P "%NBU_INST_PATH%." /C "cmd /c echo @path" $*

@SET PATH=%PATH%;%NBU_INST_PATH%NetBackup\bin;%NBU_INST_PATH%NetBackup\bin\admincmd;%NBU_INST_PATH%NetBackup\bin\goodies;&

@SET nb="%NBU_INST_PATH%NetBackup"&
@SET nbin="%NBU_INST_PATH%NetBackup\bin"&
@SET nadm="%NBU_INST_PATH%NetBackup\bin\admincmd"&
@SET ngds="%NBU_INST_PATH%NetBackup\bin\goodies"&
@SET nlogs="%NBU_INST_PATH%NetBackup\logs"&
@SET bmrcd="%NBU_INST_PATH%NetBackup\BareMetal\Client\data"&
@SET bmrsd="%NBU_INST_PATH%NetBackup\BareMetal\Server\data"&

@DOSKEY cd.~.win=cd /d "%userprofile%"\$* &
@DOSKEY cd.desk=cd /d "%userprofile%"\Desktop\$* &
@DOSKEY cd.down=cd /d "%userprofile%"\Downloads\$* &
@DOSKEY cd.pf=cd /d "%ProgramFiles%"\$* &
@DOSKEY cd.pfx86=cd /d "%ProgramFiles(x86)%"\$* &
@DOSKEY cd.pd=cd /d "%ProgramData%"\$* &
@DOSKEY cd.win=cd /d "%WINDIR%"\$* &
@DOSKEY cd.sys32=cd /d "%WINDIR%"\system32\$* &
@DOSKEY cd.wow64=cd /d "%WINDIR%"\syswow64\$* &
@DOSKEY cd.temp=cd /d %temp% &

@DOSKEY cd..2=cd ..\.. &
@DOSKEY cd..3=cd ..\..\.. &
@DOSKEY cd..4=cd ..\..\..\.. &
@DOSKEY cd..5=cd ..\..\..\..\.. &
@DOSKEY cd..6=cd ..\..\..\..\..\.. &
@DOSKEY cd..7=cd ..\..\..\..\..\..\.. &
@SET dt2=..\..&
@SET dt3=..\..\..&
@SET dt4=..\..\..\..&
@SET dt5=..\..\..\..\..&
@SET dt6=..\..\..\..\..\..&
@SET dt7=..\..\..\..\..\..\..&

@DOSKEY r.nb.cv=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\NetBackup\CurrentVersion$*&
@DOSKEY wmic.nb.uninst=wmic product where "name like 'Veritas NetBackup%'"&

cls&

@ECHO ***********Press Alt+F7 to clear the history
