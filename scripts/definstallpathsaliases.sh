#!/bin/bash -x
function af.bld.request_handler() {
    if [ "$1" == "LAUNCH" -o "$1" == "ECHO" -o "$1" == "SJA" ]; then

        OSName=`uname -s`
        if [ "$OSName" == "SunOS" -o "$OSName" == "Darwin" ]; then
            declare versions=([83]=8.3 [8301]=8.3.0.1 [8302]=8.3.0.2 [90]=9.0 [9001]=9.0.0.1 [91]=9.1 [9101]=9.1.0.1 [10]=10.0 [10001]=10.0.0.1 [101]=10.1 [1011]=10.1.1 [102]=10.2 [10201]=10.2.0.1 [103]=10.3 [10301]=10.3.0.1 [104]=10.4 [1041]=10.4.1)
            declare bldids=([83]=0102 [8301]=0042 [8302]=0026 [90]=0053 [9001]=0030 [91]=0043 [9101]=0040 [10]=0070 [10001]=0054 [101]=0048 [1011]=0116 [102]=0065 [10201]=0037 [103]=0062 [10301]=0042 [104]= [1041]=)
        else
            declare -A versions=([83]=8.3 [8301]=8.3.0.1 [8302]=8.3.0.2 [90]=9.0 [9001]=9.0.0.1 [91]=9.1 [9101]=9.1.0.1 [912]=9.1.2 [10]=10.0 [10001]=10.0.0.1 [101]=10.1 [1011]=10.1.1 [102]=10.2 [10201]=10.2.0.1 [103]=10.3 [10301]=10.3.0.1 [104]=10.4 [10401]=10.4.0.1 [1041]=10.4.1)
            declare -A bldids=([83]=0102 [8301]=0042 [8302]=0026 [90]=0053 [9001]=0030 [91]=0043 [9101]=0040 [10]=0070 [10001]=0054 [101]=0048 [1011]=0116 [102]=0037 [1021]=0116 [102]=0065 [10201]=0037 [103]=0062 [10301]=0042 [104]= [10401]= [1041]=)
        fi

        ver=$2
        VERSION=${versions[$ver]}
        BID=${bldids[$ver]}
        PLATFORM=$3

        if [ "$VERSION" == "" ]; then
            VERSION=$2
            BID=$3
            PLATFORM=$4
        fi

        INST_PATH=/newbuilds/NB/${VERSION}/NB_${VERSION}_${BID}/NetBackup_${VERSION}_${PLATFORM}
        if [ "$1" == "LAUNCH" ]; then
            ${INST_PATH}
        fi
	if [ "$1" == "ECHO" ]; then
            echo ${INST_PATH}
        fi
        if [ "$1" == "SJA" ]; then
            find ${INST_PATH} -name *.sja
        fi
    fi
}

CLIP_CMD=
if [ "$OSName" == "Darwin" ]; then
    CLIP_CMD='^|pbcopy';
fi

OSName=`uname -s`

alias m.bld..rf='function af.bld.ls() { ls -dl /newbuilds/NB/$1/* | awk '"'"'{ printf $NF "\n" }'"'"'; }; af.bld.ls'
alias m.bld..rs9='function af.bld.ls() { ls -dl /newbuilds/NB/`echo $1| sed '"'"'s/./&./g'"'"' | sed '"'"'s/.$//g'"'"'`/* | awk '"'"'{ printf $NF "\n" }'"'"'; }; af.bld.ls'
alias m.bld..rs10='function af.bld.ls() { ls -dl /newbuilds/NB/`echo $1| sed '"'"'s/./&./g'"'"' | sed '"'"'s/.$//g'"'"'| sed '"'"'s/\.//'"'"'`/* | awk '"'"'{ printf $NF "\n" }'"'"'; }; af.bld.ls'

if [[ "$OSName" = "Linux" ]] && [[ -f /etc/redhat-release ]] || [ "$1" = "ALL" ]; then
    alias m.bld.srv.lr..rs="function af.bld.srv.lr()   { af.bld.request_handler LAUNCH \$1 LinuxR_x86_64/install; }; af.bld.srv.lr"
    alias m.bld.clnt.lr..rs="function af.bld.clnt.lr() { af.bld.request_handler LAUNCH \$1 CLIENTS2/install; }; af.bld.clnt.lr"
    alias cp.bld.srv.lr..rs="function af.bld.srv.lr()   { af.bld.request_handler ECHO \$1 LinuxR_x86_64 $CLIP_CMD; }; af.bld.srv.lr"
    alias cp.bld.clnt.lr..rs="function af.bld.clnt.lr() { af.bld.request_handler ECHO \$1 CLIENTS2 $CLIP_CMD; }; af.bld.clnt.lr"
    alias m.bld.srv.lr..rf.b="function af.bld.srv.lr()   { af.bld.request_handler LAUNCH \$1 \$2 LinuxR_x86_64/install; }; af.bld.srv.lr"
    alias m.bld.clnt.lr..rf.b="function af.bld.clnt.lr() { af.bld.request_handler LAUNCH \$1 \$2 CLIENTS2/install; }; af.bld.clnt.lr"
    alias cp.bld.srv.lr..rf.b="function af.bld.srv.lr()   { af.bld.request_handler ECHO \$1 \$2 LinuxR_x86_64 $CLIP_CMD; }; af.bld.srv.lr"
    alias cp.bld.clnt.lr..rf.b="function af.bld.clnt.lr() { af.bld.request_handler ECHO \$1 \$2 CLIENTS2 $CLIP_CMD; }; af.bld.clnt.lr"
fi

IS_SUSE=0
if [[ "$OSName" = "Linux" ]] && [[ -f /etc/SuSE-release ]] || [ "$1" = "ALL" ]; then
    IS_SUSE=1
fi

if [[ "$OSName" = "Linux" ]] && [[ -f /etc/SUSE-brand ]] || [ "$1" = "ALL" ]; then
    IS_SUSE=1
fi

if [[ "$IS_SUSE" = "1" ]]; then
    alias m.bld.srv.ls..rs="function af.bld.srv.ls()   { af.bld.request_handler LAUNCH \$1 LinuxS_x86_64/install; }; af.bld.srv.ls"
    alias m.bld.clnt.ls..rs="function af.bld.clnt.ls() { af.bld.request_handler LAUNCH \$1 CLIENTS2/install; }; af.bld.clnt.ls"
    alias cp.bld.srv.ls..rs="function af.bld.srv.ls()   { af.bld.request_handler ECHO \$1 LinuxS_x86_64 $CLIP_CMD; }; af.bld.srv.ls"
    alias cp.bld.clnt.ls..rs="function af.bld.clnt.ls() { af.bld.request_handler ECHO \$1 CLIENTS2 $CLIP_CMD; }; af.bld.clnt.ls"
    alias m.bld.srv.ls..rf.b="function af.bld.srv.ls()   { af.bld.request_handler LAUNCH \$1 \$2 LinuxS_x86_64/install; }; af.bld.srv.ls"
    alias m.bld.clnt.ls..rf.b="function af.bld.clnt.ls() { af.bld.request_handler LAUNCH \$1 \$2 CLIENTS2/install; }; af.bld.clnt.ls"
    alias cp.bld.srv.ls..rf.b="function af.bld.srv.ls()   { af.bld.request_handler ECHO \$1 \$2 LinuxS_x86_64 $CLIP_CMD; }; af.bld.srv.ls"
    alias cp.bld.clnt.ls..rf.b="function af.bld.clnt.ls() { af.bld.request_handler ECHO \$1 \$2 CLIENTS2 $CLIP_CMD; }; af.bld.clnt.ls"
fi

if [ "$OSName" = "SunOS" ] || [ "$1" = "ALL" ]; then
    alias m.bld.srv.sx86..rs="function af.bld.srv.sx86()   { af.bld.request_handler LAUNCH \$1 Solaris_x86/install; }; af.bld.srv.sx86"
    alias m.bld.clnt.sx86..rs="function af.bld.clnt.sx86() { af.bld.request_handler LAUNCH \$1 CLIENTS1/install; }; af.bld.clnt.sx86"
    alias cp.bld.srv.sx86..rs="function af.bld.srv.sx86()   { af.bld.request_handler ECHO \$1 Solaris_x86 $CLIP_CMD; }; af.bld.srv.sx86"
    alias cp.bld.clnt.sx86..rs="function af.bld.clnt.sx86() { af.bld.request_handler ECHO \$1 CLIENTS1 $CLIP_CMD; }; af.bld.clnt.sx86"
    alias m.bld.srv.sx86..rf.b="function af.bld.srv.sx86()   { af.bld.request_handler LAUNCH \$1 \$2 Solaris_x86/install; }; af.bld.srv.sx86"
    alias m.bld.clnt.sx86..rf.b="function af.bld.clnt.sx86() { af.bld.request_handler LAUNCH \$1 \$2 CLIENTS1/install; }; af.bld.clnt.sx86"
    alias cp.bld.srv.sx86..rf.b="function af.bld.srv.sx86()   { af.bld.request_handler ECHO \$1 \$2 Solaris_x86 $CLIP_CMD; }; af.bld.srv.sx86"
    alias cp.bld.clnt.sx86..rf.b="function af.bld.clnt.sx86() { af.bld.request_handler ECHO \$1 \$2 CLIENTS1 $CLIP_CMD; }; af.bld.clnt.sx86"
fi

if [ "$OSName" = "HP-UX" ] || [ "$OSName" = "AIX" ] || [ "$1" == "ALL" ]; then
    alias m.bld.clnt.othr..rs="function af.bld.clnt.othr() { af.bld.request_handler LAUNCH \$1 CLIENTS1/install; }; af.bld.clnt.othr"
    alias cp.bld.clnt.othr..rs="function af.bld.clnt.othr() { af.bld.request_handler ECHO \$1 CLIENTS1 $CLIP_CMD; }; af.bld.clnt.othr"
    alias m.bld.clnt.othr..rf.b="function af.bld.clnt.othr() { af.bld.request_handler LAUNCH \$1 \$2 CLIENTS1/install; }; af.bld.clnt.othr"
    alias cp.bld.clnt.othr..rf.b="function af.bld.clnt.othr() { af.bld.request_handler ECHO \$1 \$2 CLIENTS1 $CLIP_CMD; }; af.bld.clnt.othr"
fi

alias m.sja..rf.b="function af.sja.rf.b() { find /newbuilds/NB/\$1/NB_\$1_\$2/NetBackup_\$1_VU_* -name *.sja; }; af.sja.rf.b"
alias m.sja..rs="function af.sja.rs() { af.bld.request_handler SJA \$1 \$2 VU_* $CLIP_CMD; }; af.sja.rs"
