@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_SF

@DOSKEY a.sf=DOSKEY /macros:all ^| findstr "sf\..*=" ^| findstr /V "\.sf\..*=" $*
@DOSKEY a.sf.all=DOSKEY /macros:all ^| findstr "sf\..*= bmr\..*=" $*

@DOSKEY cd.sf.clust.conf=%~dp0cd.cmd "%%VCS_HOME%%"\conf\config\"$*

@DOSKEY sf.clust.status=hasys -state $*
@DOSKEY sf.clust.stop=hastop -all $*
@DOSKEY sf.clust.start=hastart -all $*
@DOSKEY sf.clust.cf.verify=hacf -verify $*
@DOSKEY sf.clust.force1=hasys -force $*
@DOSKEY sf.clust.status.det=hastatus $*
@DOSKEY sf.clust.version=haclus -value EngineVersion
@DOSKEY sf.clust.gui=hagui
@DOSKEY sf.clust.passreset=haconf -makerw ^& hauser -update admin ^& haconf -dump -makero
@DOSKEY sf.clust.haconf.ro=haconf -dump -makero
@DOSKEY sf.clust.haconf.rw=haconf -makerw
@DOSKEY sf.clust.llt.start=net start llt /y
@DOSKEY sf.clust.llt.stop=net stop llt /y
@DOSKEY sf.clust.gab.start=net start gab /y
@DOSKEY sf.clust.gab.stop=net stop gab /y

@DOSKEY e.sf.maincf=%%CFG_EDITOR%% "%%VCS_HOME%%"\conf\config\main.cf
@DOSKEY e.sf.typescf=%%CFG_EDITOR%% "%%VCS_HOME%%"\conf\config\types.cf
@DOSKEY e.sf.gabtab=%%CFG_EDITOR%% "%%VCS_ROOT%%"\comms\gab\gabtab.txt
@DOSKEY e.sf.llttab=%%CFG_EDITOR%% "%%VCS_ROOT%%"\comms\llt\llttab.txt
@DOSKEY e.sf.llthosts=%%CFG_EDITOR%% "%%VCS_ROOT%%"\comms\llt\llthosts.txt
@DOSKEY e.sf.log=%%CFG_EDITOR%% "%%VCS_HOME%%"\log\engine_*.txt

@DOSKEY r.sf.vcs=reg query HKEY_LOCAL_MACHINE\SOFTWARE\Veritas\VCS\Base$*

:QA_ALIAS_SF

