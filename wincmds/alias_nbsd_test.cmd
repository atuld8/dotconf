@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_NBSD_TEST

@DOSKEY t.nbsd.status=sc qc "NetBackup Smart Diagnosis Service" ^& echo. ^& echo. ^& sc query "NetBackup Smart Diagnosis Service"
@DOSKEY t.nbsd.start=nbsmartdiag -start $*
@DOSKEY t.nbsd.term=nbsmartdiag -terminate $*
@DOSKEY t.nbsd.netstr=net start "NetBackup Smart Diagnosis Service"
@DOSKEY t.nbsd.netstp=net stop "NetBackup Smart Diagnosis Service"
@DOSKEY t.nbsd.truncatelog=echo ^> "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\$*"
@DOSKEY t.nbsd.log=dir "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\"$*
@DOSKEY e.nbsd.log=%%CFG_EDITOR%% "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\$*"
@DOSKEY t.nbsd.setconf=nbsetconfig %userprofile%\.vim\wincmds\nbsd.conf
@DOSKEY t.nbsd.getconf=nbgetconfig ^| findstr "NBSD_"
@DOSKEY t.nbsd.getevd=nbgetconfig ^| findstr "NBSD_EVIDENCE_PATH"

@DOSKEY a.nbsd=%DOSKEY_ALL_MACROS% ^| findstr "\.nbsd\..*=" $*

:QA_ALIAS_NBSD_TEST

