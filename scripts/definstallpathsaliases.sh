#!/bin/bash -x
function af.bld.request_handler() {
    if [ "$1" == "LAUNCH" -o "$1" == "ECHO" ]; then

        OSName=`uname -s`
        if [ "$OSName" == "SunOS" -o "$OSName" == "Darwin" ]; then
            declare versions=([80]=8.0 [81]=8.1 [811]=8.1.1 [812]=8.1.2 [8121]=8.1.2.1 [82]=8.2 [83]=8.3 [8301]=8.3.0.1 [8302]=8.3.0.2 [90]=9.0 [9001]=9.0.0.1 [91]=9.1 [9101]=9.1.0.1 [912]=9.1.2)
            declare bldids=([80]=0165 [81]=0049 [811]=0103 [812]=0106 [8121]=0106 [82]=0149 [83]=0102 [8301]=0042 [8302]= [90]=0053 [9001]=0030 [91]=0043 [9101]= [912]=)
        else
            declare -A versions=([80]=8.0 [81]=8.1 [811]=8.1.1 [812]=8.1.2 [8121]=8.1.2.1 [82]=8.2 [83]=8.3 [8301]=8.3.0.1 [8302]=8.3.0.2 [90]=9.0 [9001]=9.0.0.1 [91]=9.1 [9101]=9.1.0.1 [912]=9.1.2)
            declare -A bldids=([80]=0165 [81]=0049 [811]=0103 [812]=0106 [8121]=0106 [82]=0149 [83]=0102 [8301]=0042 [8302]= [90]=0053 [9001]=0030 [91]=0043 [9101]= [912]=)
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
        else
            echo ${INST_PATH}
        fi
    fi
}

CLIP_CMD=
if [ "$OSName" == "Darwin" ]; then
    CLIP_CMD='^|pbcopy';
fi

OSName=`uname -s`

alias m.bld.lst..rf='function af.bld.ls() { ls -dl /newbuilds/NB/$1/* | awk '"'"'{ printf $NF "\n" }'"'"'; }; af.bld.ls'

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

