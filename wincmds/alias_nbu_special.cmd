@REM HIDDEN / NOT DOCUMENTED CMDS

@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_NBU_SPECIAL

@DOSKEY .nb.slp.sch=nbstlutil dump -subsys 8
@DOSKEY .nb.slp.report=nbstlutil report $*
@DOSKEY .nb.slp.imglist=nbstlutil list -U $*
@DOSKEY .nb.slp.imgid=nbstlutil list -b $*
@DOSKEY .nb.slp.state=nbstlutil stlilist -U $*
@DOSKEY .nb.slp.cancel=nbstlutil cancel $*
@DOSKEY .nb.slp.name=nbstl -b $*
@DOSKEY .nb.slp.list=nbstl -U $*
@DOSKEY .nb.slp.det=nbstl -L $*




@DOSKEY .nb.db.start=bpup -v -f -e SQLANYs_VERITAS_NB
@DOSKEY .nb.db.stop=bpdown -v -f -e SQLANYs_VERITAS_NB
@DOSKEY .nb.img.cln=bpimage -cleanup -allclients ^& nbdelete -force -allvolumes
@DOSKEY .nb.img.ids=bpimagelist -U $* ^& %%es%% ^& bpimagelist -idonly $*
@DOSKEY .nb.img.del=bpexpdate -d 0 $*
@DOSKEY .nb.pol.hwos=bppllist -hwos $*
@DOSKEY .nb.db.cnn.nb=dbisqlc -c "CS=utf8;UID=dba;PWD=nbusql;LINKS=shmem,tcpip{PORT=13785};DBN=NBDB;SERVER=NB_%%NBUDB_SERVER%%" $*
@DOSKEY .nb.db.cnn.az=dbisqlc -c "UID=dba;PWD=nbusql;DBN=NBAZDB;SERVER=NB_%%NBUDB_SERVER%%" $*
@DOSKEY .nb.db.tbl.nb=dbisqlc -q -nogui -c "UID=dba;PWD=nbusql;DBN=NBDB;SERVER=NB_%%NBUDB_SERVER%%" "select table_name from sys.systable;output to dbisqlc.output.txt"
@DOSKEY .nb.db.tbl.nz=dbisqlc -q -nogui -c "UID=dba;PWD=nbusql;DBN=NBAZDB;SERVER=NB_%%NBUDB_SERVER%%" "select table_name from sys.systable;output to dbisqlc.output.txt"
@DOSKEY .nb.db.qry.nb.qrow=dbisqlc -q -nogui -c "UID=dba;PWD=nbusql;DBN=NBDB;SERVER=NB_%%NBUDB_SERVER%%" $* ">&" dbisqlc.output.txt
@DOSKEY .nb.db.qry.nb.rows=dbisqlc -q -nogui -c "UID=dba;PWD=nbusql;DBN=NBDB;SERVER=NB_%%NBUDB_SERVER%%" $*";OUTPUT To dbisqlc.output.txt"

:QA_ALIAS_NBU_SPECIAL

