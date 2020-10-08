@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_NBSD_TEST

@DOSKEY t.nbsd.isrunning=sc qc "NetBackup Smart Diagnosis Service" ^& echo. ^& echo. ^& sc query "NetBackup Smart Diagnosis Service"
@DOSKEY t.nbs=nbsmartdiag $*
@DOSKEY t.nbsd.start=nbsmartdiag -start $*
@DOSKEY t.nbsd.term=nbsmartdiag -terminate $*
@DOSKEY t.nbsd.netstr=net start "NetBackup Smart Diagnosis Service"
@DOSKEY t.nbsd.netstp=net stop "NetBackup Smart Diagnosis Service"
@DOSKEY t.nbsd.truncatelog=echo ^> "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\$*"
@DOSKEY t.nbsd.log=dir "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\"$*
@DOSKEY e.nbsd.log=%%CFG_EDITOR%% "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\$*"
@DOSKEY t.nbsd.setconf=nbsetconfig %userprofile%\.vim\wincmds\nbsd.conf
@DOSKEY t.nbsd.getconf=nbgetconfig ^| findstr "NBSD_" $*
@DOSKEY t.nbsd.lstcfg=nbsmartdiag -list_config $*
@DOSKEY t.nbsd.getevd=nbgetconfig ^| findstr "NBSD_EVIDENCE_PATH" $*

@DOSKEY a.nbsd=%DOSKEY_ALL_MACROS% ^| findstr "\.nbsd\..*=" $*

@DOSKEY cd.nbsd.logs=cd /d "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag" $*
@DOSKEY cd.nbsd.evd=@FOR /F "tokens=3" %%d in ('nbgetconfig.exe ^^^| findstr "NBSD_EVIDENCE_PATH"') DO @%~dp0cd.cmd %%d\nbsmartdiag
@DOSKEY t.nbsd.delevd=@FOR /F "tokens=1,2,*" %%d in ('nbgetconfig.exe ^^^| findstr "NBSD_EVIDENCE_PATH"') DO @IF EXIST "%%f\nbsmartdiag" (@RMDIR /s /q "%%f\nbsmartdiag\" )
@DOSKEY t.nbsd.dellogs=@DEL /F /Q "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\*.log"
@DOSKEY t.nbsd.resetconf=@FOR /F "tokens=1,2,*" %%d in ('nbgetconfig.exe ^^^| findstr "NBSD_" ^^^| findstr /V "NBSD_EVIDENCE_PATH"') DO @ECHO %%d %%e ^| nbsetconfig $*

:QA_ALIAS_NBSD_TEST

