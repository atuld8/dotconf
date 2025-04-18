(
export ov='/usr/openv'
export nb='/usr/openv/netbackup'
export nbin='/usr/openv/netbackup/bin'
export nadm='/usr/openv/netbackup/bin/admincmd'
export ngds='/usr/openv/netbackup/bin/goodies'
export natbin='/usr/openv/netbackup/sec/at/bin'
export nlogs='/usr/openv/netbackup/logs'
export ovlogs='/usr/openv/logs'
export ngbl='/usr/openv/var/global'
export njava='/usr/openv/java'
export bmrsd='/usr/openv/netbackup/baremetal/server/data'
export nbdt='/mnt/nbdata/usr/openv/'
export PATH=$PATH:/usr/openv/netbackup/bin/admincmd:/usr/openv/netbackup/bin
export PATH=$PATH:/usr/openv/db/bin:/usr/openv/netbackup/bin/goodies
export PATH=$PATH:/usr/openv/netbackup/bin/support
export PATH=$PATH:/usr/openv/netbackup/sec/at/bin:/usr/openv/volmgr/bin

alias .nb.con='jnbSA -d $ENG_VM_NAME & disown'

alias e.bmr.srtcnf='vim /usr/openv/var/global/createsrt.conf'
alias cd.nb='cd /usr/openv/netbackup'
alias cd.nb.gd='cd /usr/openv/netbackup/bin/goodies/'
alias cd.nb.bin='cd /usr/openv/netbackup/bin'
alias cd.nb.logs='cd /usr/openv/netbackup/logs'
alias cd.nb.ologs='cd /usr/openv/logs'
alias cd.nb.db.log='cd /usr/openv/db/log'
alias cd.nb.tc.logs='cd /usr/openv/wmc/webserver/logs'
alias cd.nb.tc='cd /usr/openv/wmc/webserver/'
alias cd.nb.wmcinst='cd /usr/openv/wmc/bin/install'

)
