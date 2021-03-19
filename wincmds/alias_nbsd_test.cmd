@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_NBSD_TEST

@DOSKEY t.nbsd.status=sc query nbsmartdiag
@DOSKEY t.nbsd.start=nbsmartdiag -start $*
@DOSKEY t.nbsd.term=nbsmartdiag -terminate $*
@DOSKEY t.nbsd.genlkgc=copy /y "%%NBU_INST_PATH%%NetBackup\nbsmartdiag.json" "%%NBU_INST_PATH%%NetBackup\nbsmartdiag.json.lkgc" $*
@DOSKEY t.nbsd.rev2lkgc=copy /y "%%NBU_INST_PATH%%NetBackup\nbsmartdiag.json.lkgc" "%%NBU_INST_PATH%%NetBackup\nbsmartdiag.json" $*
@DOSKEY t.nbsd.truncatelog=echo ^> "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\$*"
@DOSKEY t.nbsd.log=dir "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag" $*
@DOSKEY e.nbsd.log=%%CFG_EDITOR%% "%%NBU_INST_PATH%%NetBackup\logs\nbsmartdiag\$*"

@DOSKEY a.nbsd=%DOSKEY_ALL_MACROS% ^| findstr "\.nbsd\..*=" $*

:QA_ALIAS_NBSD_TEST



