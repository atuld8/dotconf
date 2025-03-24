@IF "%1" == "QUICK_ACCESS" GOTO QA_ALIAS_POSTGRES

@DOSKEY a.psql=DOSKEY /macros:all ^| findstr "\.psql\..*=" ^| findstr /v "[0-9A-Za-z]\.psql\..*="$*

@REM Postgres specific commands
@DOSKEY .nb.psql=psql -h localhost -p %%PGPORT%% -U %%PGUSER%% -d NBDB -A $*
@DOSKEY .bmr.psql=psql -h localhost -p %%PGPORT%% -U %%PGUSER%% -d BMRDB -A $*
@DOSKEY .nb.psqlc=psql -h localhost -p %%PGPORT%% -U %%PGUSER%% -d NBDB --no-psqlrc --pset border=2 --pset format=aligned $*
@DOSKEY .bmr.psqlc=psql -h localhost -p %%PGPORT%% -U %%PGUSER%% -d BMRDB --no-psqlrc --pset border=2 --pset format=aligned $*
@DOSKEY .bmr.psql.tbl=psql -h localhost -p %%PGPORT%% -U %%PGUSER%% -d BMRDB --pset border=2 --pset format=aligned -t -A --no-psqlrc -c "SELECT schemaname || '.' || tablename FROM pg_catalog.pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');"
@DOSKEY .nb.psql.tbl=psql -h localhost -p %%PGPORT%% -U %%PGUSER%% -d NBDB --pset border=2 --pset format=aligned -t -A --no-psqlrc -c "SELECT schemaname || '.' || tablename FROM pg_catalog.pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');"

:QA_ALIAS_POSTGRES


