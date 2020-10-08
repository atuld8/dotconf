@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_BMR

@DOSKEY a.bmr=DOSKEY /macros:all ^| findstr "\.bmr\..*=" ^| findstr /v "[0-9A-Za-z]\.bmr\..*="$*


@REM BMR specific commands
@DOSKEY .bmr.cfg=bmrs -op list -res config $*
@DOSKEY .bmr.srt=bmrs -op list -res srt $*
@DOSKEY .bmr.list=bmrs -op list -res $*
@DOSKEY .bmr.tbl=bmrpans -op showtables $*
@DOSKEY .bmr.dmp..tbl=bmrpans -op dump -table $*
@DOSKEY .bmr.qry..tbl=bmrpans -op query -table $*
@DOSKEY .bmr.rstfile=bmrpans -op dump -table RestoreConfigFile $*
@DOSKEY .bmr.breg=bmrsetupboot -register $*
@DOSKEY .bmr.master=bmrsetupmaster $*
@DOSKEY .bmr.import..bndl=bmrs -op import -res config -path $*
@DOSKEY .bmr.prepscript..clnt=bmrprep -restore -config current -restorescriptonly -client $*
@DOSKEY .bmr.prepscript..clnt.cfg=bmrprep -restore -config current -restorescriptonly -client $1 -config $2
@DOSKEY .bmr.prep..clnt.cfg.srt=bmrprep -restore -config current -client $1 -config $2 -srt $3 -logging
@DOSKEY .bmr.qtid..id=bmrs -op querytree -res database -table config -id $*
@DOSKEY .bmr.qtidgui..id=bmrs -o querytree -r database -table config -gui -id $*
@DOSKEY .bmr.pullrsF..clnt=bmrc -o pull -res info -sourc FFFFFFFF.restore -dest FFFFFFFF.restore -client $*
@DOSKEY .bmr.pushrsF..clnt=bmrc -o push -res info -sourc FFFFFFFF.restore -dest FFFFFFFF.restore -client $*
@DOSKEY .bmr.pull..clnt.hIp.fextn=bmrc -o pull -res info -client $1 -sourc $2.$3 -dest $1.$2.$3
@DOSKEY .bmr.push..clnt.hIp.fextn=bmrc -o push -res info -client $1 -sourc $1.$2.$3 -dest $2.$3
@DOSKEY .bmr.pullallscripts..clnt.hIp..apnd=@FOR %%f in (hosts bp.conf resolv.conf conf listfile diskdata info restore) do bmrc -o pull -res info -client $1 -sourc $2.%%f -dest $1$3.%%f
@DOSKEY .bmr.driverLoadOrder..cfgid=@FOR /F "tokens=1,2,*" %%a in ('bmrpans -op query -table BMR_LinuxScsiDriver -where "VolumeInfoId=$*" ^^^| findstr "DriverName"') do @ECHO %%c
@DOSKEY .bmr.cancelrstjob..clnt=bmrs -op complete -res restoretask -status 150 -client $*
@DOSKEY .bmr.vxlfids=findstr "OIDNames" "%%NBU_INST_PATH%%\NetBackup\nblog.conf" ^| findstr /I "bmr" $*

@DOSKEY .bmr.db.crt=dbinit -q -b -c -z UTF8 -p 4096  -dba dba,nbusql "%%NBU_CONF_PATH%%NetBackupDB\data\BMRDB.DB"
@DOSKEY .bmr.db.cnn=dbisqlc -c "CS=utf8;UID=dba;PWD=nbusql;LINKS=shmem,tcpip{PORT=13785};DBN=BMRDB;SERVER=NB_%%NBUDB_SERVER%%" $*
@DOSKEY .bmr.db.tbl=dbisqlc -q -nogui -c "UID=dba;PWD=nbusql;DBN=BMRDB;SERVER=NB_%%NBUDB_SERVER%%" "select table_name from sys.systable;output to dbisqlc.output.txt"

@DOSKEY .bmr.genbndl=bmrsavecfg -infoonly $*

:QA_ALIAS_BMR

