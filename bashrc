# .bashrc
Red='\e[0;31m'
RED='\e[1;31m'
blue='\e[0;34m'
BLUE='\e[1;34m'
cyan='\e[0;36m'
CYAN='\e[1;36m'
BLACK='\e[0;30m'
GREEN='\e[0;32m'
PURPLE='\e[0;35m'
BROWN='\e[0;33m'
LIGHTGRAY='\e[0;37m'
DARKGRAY='\e[1;30m'
LIGHTBLUE='\e[1;34m'
LIGHTGREEN='\e[1;32m'
LIGHTCYAN='\e[1;36m'
LIGHTRED='\e[1;31m'
LIGHTPURPLE='\e[1;35m'
YELLOW='\e[1;33m'
WHITE='\e[1;37m'
NC='\e[0m'              # No Color

# Source global definitions
if [ -f /etc/bashrc ]; then
   . /etc/bashrc
fi

if [ -z "${VIM_BASHRC_CALLED}" ] || [ "${VIM_BASHRC_CALLED}" -eq 0 ]; then

MANPATH=$MANPATH:/usr/dt/man:/usr/man:/usr/openwin/share/man:/usr/openv/man/share/man
export MANPATH


PATH=$PATH:~/scripts:~/.vim/bin:~/.vim/scripts:~/.vim/jira:
export PATH
fi

# Define this before calling current file into bash
#export PUNIN=''
#export PNE=''
#export NIS_USER=''
#export NIS_SERVE=''
#export GIT_SERVER=''
#export GIT_USER=''
#export WIN_ENG_SY=''


alias du='du -h'
alias l='ls -CF'
alias la='ls -ACF'
alias ll='ls -l'
alias l1='ls -1F'
alias l1a='ls -1Fa'
alias l.='ls --color=auto -d .?*'
alias ll.='ls --color=auto -ld .?*'
alias lsd='ls -d */'
alias lll='ls -la | less -X'
alias dir='ls -l'
alias lsfh='ls -hF'
alias mv='mv -i'
alias rm='rm -i'
alias df='df -h'
alias cp='cp -i'
alias ..='af.cd1 () { cd ../$1; }; af.cd1'
alias ...='af.cd2 () { cd ../../$1; }; af.cd2'
alias ....='af.cd3 () { cd ../../../$1; }; af.cd3'
alias .....='af.cd4 () { cd ../../../../$1; }; af.cd4'
alias clr="clear; pwd; ls -lrth"
alias paths='echo -e ${PATH//:/\\n}'

# User specific aliases and functions
#required by screen and tmux
export DOName=''

#trap 'PS1="\n$USER@$HOSTNAME$DOMAINNAME:\$PWD \n$ "' DEBUG
#trap 'PS1="\n(\!) $USER@$HOSTNAME$DOMAINNAME:\$PWD  [\d \t] Jobs:\j \n$ "' DEBUG
#trap 'PS1="\n< (\!:\#:\$?) $USER@$HOSTNAME$DOMAINNAME:\$PWD  [\D{%A %e %B %G %R %Z} \t] Jobs:\j > \n$ "' DEBUG
#trap 'PS1="\n< (\!:\#:\$?) [\D{%A %e %B %G} \t] jobs:\j > $USER@$HOSTNAME$DOMAINNAME:\$PWD  \n$ "' DEBUG
#trap 'PS1="\n\nReturn Code:\$?\n< (\!:\#) [\D{%A %e %B %G} \t] jobs:\j > $USER@$HOSTNAME$DOMAINNAME:\$PWD  \n$ "' DEBUG
OSName=`uname -s`
if [ "$OSName" = "SunOS" ]; then PATCHNO=`cat /etc/release | grep "Solaris" | sed -e's/.*_u//' | cut -c1-2 | grep "[0-9]"`; if [ $? -ne 0 ]; then OSVer="SunOS_"`uname -r`; else OSVer="SunOS_"`uname -r`"U"${PATCHNO/\w/}; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "SunOS" ]; then if [ "`uname -r`" == "5.11" ]; then BASH_FG="-v"; else BASH_FG="-r"; fi; PATCHNO=`cat /etc/release | grep "Solaris" | sed -e's/.*_u//' | cut -c1-2 | grep "[0-9]"`; if [ $? -ne 0 ]; then OSVer="SunOS_"`uname $BASH_FG| sed -e's/5.//g'`; else OSVer="SunOS_"`uname $BASH_FG| sed -e's/5.//g'`"U"${PATCHNO/\w/}; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "AIX" ]; then OSVer=`oslevel | cut -d'.' -f1-2``oslevel -s | cut -d"-" -f2 | grep -v "00" | xargs -i expr {} | xargs -i echo " TL"{}``oslevel -s | cut -d"-" -f3 | grep -v "00" | xargs -i expr {} | xargs -i echo " SP"{}`; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/lsb-release ]; then OSVer="Ubuntu_"`lsb_release -r | cut -f2`; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release ]; then lsb_release > /dev/null 2>/dev/null; if [ $? -eq 0 ]; then OSVer="RHEL_"`lsb_release -r | cut -f2`; else OSVer="RHEL_"`awk '{print $(NF-1)}' /etc/redhat-release`; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release -a -f /etc/oracle-release ]; then lsb_release > /dev/null 2>/dev/null; if [ $? -eq 0 ]; then OSVer="OEL_"`lsb_release -r | cut -f2`; else OSVer="OEL_"`awk '{print $(NF-1)}' /etc/redhat-release`; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release -a -f /etc/centos-release ]; then lsb_release > /dev/null 2>/dev/null; if [ $? -eq 0 ]; then OSVer="CentOS_"`lsb_release -r | cut -f2 | awk -F'.' '{ print $1"."$2 }'`; else OSVer="CentOS_"`awk '{print $(NF-1)}' /etc/redhat-release`; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/SuSE-release ]; then OSVer="SuSE_"`lsb_release -r | cut -f2`; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/SUSE-brand ]; then OSVer="SuSE_"`cat /etc/os-release | grep VERSION_ID | cut -d'"' -f2`; PROCName=`uname -p`; fi
if [ "$OSName" = "HP-UX" ]; then OSVer=`uname -r | sed -e's/B.//g'`; PROCName=`uname -m`; USER=$LOGNAME;fi
if [ "$OSName" = "FreeBSD" ]; then OSVer=`uname -r | sed -e's/-RELEASE//g'`; PROCName=`uname -m`; fi

# cygwin
# OSName=`uname -o`
#if [ "$OSName" = "Cygwin" ]; then OSVer=`uname -r`; PROCName=`uname -m`; fi
export DARWIN_DATA=" "
if [ "$OSName" = "Darwin" ]; then
    OSVer="Darwin_"`uname -r`;
    PROCName=`uname -p`;
    ProductName=`sw_vers | grep ProductName | cut -f2`;
    ProductVersion=`sw_vers | grep ProductVersion | cut -f2`;
    export DARWIN_DATA=" ProductName:${PROPCOLOR}${BG}${ProductName}${PROPNAMECOLOR}${BG} ProductVer:${PROPCOLOR}${BG}${ProductVersion} "
fi

which domainname > /dev/null 2> /dev/null
if [ $? -eq 0 ]; then DOName=`domainname | grep -v "none" | xargs -i echo "."{}`; fi
TTYNAME=`tty | cut -b 6-`

COLOR_USER=${GREEN}
if [[ $EUID -eq 0 ]]; then
    COLOR_USER=${RED}
fi

GetNBUData ()
{
    local NBU_TYPE=
    local NBU_VER=
    local NBU_BUILDNUMBER=
    local NBU_MASTER=
    local NBU_CLIENT_NAME=
    local NBU_RELEASEDATE=
    NBU_DATA=
    NBU_DATA_TERMINAL=
    if [ -f /usr/openv/netbackup/bp.conf ]; then
        NBU_TYPE=Client;
        NBU_MASTER=`head -1 /usr/openv/netbackup/bp.conf | awk -F'=' '{ print $2; }'| sed -e's/^\s*//g' | sed -e's/\s*$//g'`;
        NBU_CLIENT_NAME=`grep CLIENT_NAME /usr/openv/netbackup/bp.conf | awk -F'=' '{ print $2; }'| sed -e's/^\s*//g' | sed -e's/\s*$//g'`;
        head -1 /usr/openv/netbackup/bp.conf | grep "$HOSTNAME" > /dev/null;
        if [ $? -eq 0 ]; then NBU_TYPE="Primary";
        else
            grep "^SERVER =" /usr/openv/netbackup/bp.conf | grep "$HOSTNAME" > /dev/null;
            if [ $? -eq 0 ]; then NBU_TYPE="Media"; fi;
        fi;
        if [ -f /usr/openv/netbackup/version ]; then
           NBU_VER=`grep "VERSION" /usr/openv/netbackup/version | awk '{ print $3 }'`;
           NBU_BUILDNUMBER="${BROWN}${BG}BuildDate:${blue}${BG}`grep "BUILDNUMBER" /usr/openv/netbackup/version | awk '{ print $2 }'`${BROWN}${BG} ";
           NBU_BUILDNUMBER_TERMINAL="BuildDate: `grep "BUILDNUMBER" /usr/openv/netbackup/version | awk '{ print $2 }'` ";
           NBU_RELEASEDATE="ReleaseDate: `grep "RELEASEDATE" /usr/openv/netbackup/version | awk '{ print $3"-"$4"-"$7 }'` ";
        else
            if [ -f /usr/openv/netbackup/bin/version ]; then NBU_VER=`awk '{ print $2 }' /usr/openv/netbackup/bin/version`; fi
        fi
        export NBU_DATA="${BROWN}${BG}[NBU Type:${blue}${BG}${NBU_TYPE} ${BROWN}${BG}Ver:${blue}${BG}${NBU_VER}${BROWN}${BG} ${NBU_BUILDNUMBER}${BROWN}${BG}Primary:${blue}${BG}${NBU_MASTER}${BROWN}${BG}]"
        export NBU_DATA_TERMINAL="NBU Type: ${NBU_TYPE} \nVer: ${NBU_VER} \n${NBU_BUILDNUMBER_TERMINAL} \nPrimary: ${NBU_MASTER} \nClient: ${NBU_CLIENT_NAME} \n${NBU_RELEASEDATE}"
    fi
}

GetNBUData

nbuver ()
{
    GetNBUData
    if [ "$OSName" = "SunOS" ]; then
        printf "$NBU_DATA_TERMINAL\n" | col
    else
        printf "$NBU_DATA_TERMINAL\n" | column -s ':' -t
    fi
}

ClearNBUData ()
{
    NBU_DATA=
    NBU_DATA_TERMINAL=
}

BGCOLOR="\e[47m"
ENDCOLOR="\e[m"
REDCOLOR="\e[0;31m"
PURPALCOLOR="\e[0;35m"
GREENCOLOR="\e[0;32m"
YELLOWCOLOR="\e[0;33m"

PROPNAMECOLOR=${BROWN}
PROPCOLOR=${LIGHTPURPLE}

if [ -z "$GIT_STATUS_LEVEL" ]; then
    export GIT_STATUS_LEVEL=0
fi

echo_if_platform_set() {
    if [ -z "$BUILD_OS" ]; then
        return;
    fi

    if [ -z "$GIT_SERVER" ]; then
        return;
    fi
    git remote -v 2>&1| grep $GIT_SERVER > /dev/null
    if [ $? -ne 0 ]; then
        return;
    fi

    local BUILD_OS_STR=$BUILD_OS
    echo " (${BUILD_OS_STR// --plat /, })"
}

parse_git_branch() {

    if [ "$GIT_STATUS_LEVEL" == "0" ]; then
        return;
    fi

    branch=`git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/'`

    if [ -n "$branch" ];
    then
        reponame=`basename $(git config --get remote.origin.url)| sed -e's/.git//g'`

        if [ "$GIT_STATUS_LEVEL" == "1" ]; then
            echo "($reponame @$branch)"
            return;
        fi

        if [ "$GIT_STATUS_LEVEL" == "2" ]; then
            git diff-files --no-ext-diff --quiet > /dev/null
            if [ $? -ne 0 ]; then
                echo "($reponame @$branch*)"
            else
                echo "($reponame @$branch.)"
            fi
            return;
        fi

        tracked=`git status --untracked-files=no --porcelain 2>/dev/null | wc -l | awk '{ print $1; }'`
        untracked=`git status --porcelain 2>/dev/null | wc -l | awk '{ print $1; }'`

        remote_Status="Ok"
        status_origin=`git status origin 2>/dev/null | grep -i "Your branch "`;

        status=`echo $status_origin | awk '{print $4; }'`;
        if [ "$status" == "behind" ]; then
            remote_Status="Pull"
        fi
        if [ "$status" == "ahead" ]; then
            remote_Status="Push"
        fi
        status=`echo $status_origin | awk '{print $6; }'`;
        if [ "$status" == "diverged," ]; then
            remote_Status="Merge"
        fi
        echo "($reponame @$branch T:+$tracked  UT:+$((untracked - tracked)) RS:$remote_Status)"
    fi

}

GetOpsData () {
    local OPS_VER=
    local OPS_BUILDNUMBER=
    local OPS_DATA=

    if [ "OSName" = "Linux" ]; then
        rpm -qa 2>/dev/null | grep SYMCOpsCenterServer >/dev/null 2>/dev/null
        if [ $? -eq 0 ]; then
            echo 2;
        fi
    fi
}

export TMUX_HOSTNAME=`hostname -s`
changeTmuxWindowsEveryTime() {
   PROMPT_COMMAND='printf "\033k${TMUX_HOSTNAME}\033\\"'
}

function last_three_dir {
    pwd |rev| awk -F / '{print $1,$2,$3}' | rev | sed s_\ _/_g | sed s_//_/_;
}

mcd() { mkdir -p "$1" && cd "$1"; }

bcd() {
    local levels=${1:-0}
    local maxlevel=$((`echo $PWD |sed 's/[^/]//g'|wc -m`-1 ))

    if [ $levels -gt  $maxlevel ];
    then
        levels=$maxlevel;
    fi

    local bcdpath="."
    while ((levels > 0)); do
            bcdpath=$bcdpath"/.."
            let "levels--"
    done
    cd $bcdpath || break
}

# IST:${blue}${BG}`TZ=Asia/Calcutta date "+%e-%B-%G %H:%M:%S"`
SetLongTrap()
{
    export TMUX_WINIDX=""
    if [ ! -z "$TMUX" ]; then
        export TMUX_WINIDX="["$(tmux display-message -p '#I')"."$(tmux display-message -p '#P')"] "
    fi
    if [ ! -z "$WINDOW" ]; then
        export TMUX_WINIDX="[$WINDOW] "
    fi
    trap 'PS1="\n${PROPNAMECOLOR}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*} ${PURPLE}${BG}(\$((\! -1)):\#) ${PROPNAMECOLOR}${BG}[Date:${PROPCOLOR}${BG}\D{%e-%B-%G} ${PROPNAMECOLOR}${BG}Time:${PROPCOLOR}${BG}\t ${PROPNAMECOLOR}${BG}Jobs:${PROPCOLOR}${BG}\j${PROPNAMECOLOR}${BG}] ${PROPNAMECOLOR}${BG}[OS:${PROPCOLOR}${BG}${OSName} ${PROPNAMECOLOR}${BG}Ver:${PROPCOLOR}${BG}${OSVer}${PROPNAMECOLOR}${BG} ${PROPNAMECOLOR}${BG}Proc:${PROPCOLOR}${BG}${PROCName}${PROPNAMECOLOR}${BG}${DARWIN_DATA}${PROPNAMECOLOR}${BG}TTY:${PROPCOLOR}${BG}${TTYNAME}${PROPNAMECOLOR}${BG}] [FileEntries:${PROPCOLOR}$(( $( ls -A | wc -l ) - 0 )) ${PROPNAMECOLOR}HiddenEntries:${PROPCOLOR}$(( $( ls -A | wc -l ) - $( ls | wc -l ) ))${PROPNAMECOLOR}] ${NBU_DATA} \n${COLOR_USER}${BG}${USER}${PROPNAMECOLOR}${BG}@${LIGHTPURPLE}${BG}${HOSTNAME}${DOName}${PROPNAMECOLOR}${BG}:${PURPLE}${BG}\$PWD ${NC} ${BROWN}${BG}\$(parse_git_branch)${NC}${BROWN}${BG}\$(echo_if_platform_set)${NC}\n\${SPECIAL_PRMPT_DATA}\$(UpdateTmuxWinIdx)Cmd$ \$(changeTmuxWindowsEveryTime)"' DEBUG
}

CurrDirDepth() {
    echo `pwd | awk -F"/" '{print NF - 1 ; }'`
}

GetGBaseParent() {
    if [ "$GIT_STATUS_LEVEL" == "0" ]; then
        return;
    fi

    local gbase=`git rev-parse --show-toplevel 2>/dev/null`;
    local subfolder=
    local parentfolder=
    if [ "$gbase"x != ""x ]; then
        subfolder=`basename $(dirname $gbase)`;
        if [ "$subfolder" != "/" ]; then
            parentfolder=`basename $(dirname $(dirname $gbase))`;
            if [ "$parentfolder" == "/" ]; then
                parentfolder=""
            fi
            echo "<$parentfolder/$subfolder> "
        else
            echo "<$subfolder> "
            #echo ${PROPNAMECOLOR}${BG}gprnt:${PROPCOLOR}${BG}$subfolder${PROPNAMECOLOR}${BG}
        fi
    fi
}

UpdateTmuxWinIdx () {
    if [ ! -z "$TMUX" ]; then
        export TMUX_WINIDX="["$(tmux display-message -p '#I')"."$(tmux display-message -p '#P')"] "
    fi
    if [ ! -z "$WINDOW" ]; then
        export TMUX_WINIDX="[$WINDOW] "
    fi
    echo "$TMUX_WINIDX"
}

# \W basename of current directory
SetShortTrap()
{
   local DOName=""
   export PROMPT_DIRTRIM=3
   export TMUX_WINIDX=""
   if [ ! -z "$TMUX" ]; then
       export TMUX_WINIDX="["$(tmux display-message -p '#I')"."$(tmux display-message -p '#P')"] "
   fi
   if [ ! -z "$WINDOW" ]; then
       export TMUX_WINIDX="[$WINDOW] "
   fi
   trap 'PS1="\n${PROPNAMECOLOR}${BG}(\$((\! -1)) ${PROPNAMECOLOR}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*}${PROPNAMECOLOR}${BG}) ${PROPNAMECOLOR}${BG}Date:${PROPCOLOR}${BG}\D{%d-%b-%y} \D{%T %Z} ${PROPNAMECOLOR}${BG}Jobs:${PROPCOLOR}${BG}\j${PROPNAMECOLOR}${BG} Files:${PROPCOLOR}$(( $( ls -A | wc -l ) - 0 )) ${PROPNAMECOLOR}HdnFiles:${PROPCOLOR}$(( $( ls -A | wc -l ) - $( ls | wc -l ) )) ${PROPNAMECOLOR}pushd:${PROPCOLOR}$(( $( dirs -v | wc -l ) - 1 )) ${PROPNAMECOLOR}${BG}DskUsg:${PROPCOLOR}${BG}\$([ -f ~/bin/rootDiskUsage.sh ] && ~/bin/rootDiskUsage.sh)${PROPNAMECOLOR}${BG} ${PROPNAMECOLOR}${BG}Os:${PROPCOLOR}${BG}$OSVer${PROPNAMECOLOR}${BG} ${PURPLE}${BG}\$(GetGBaseParent)${NC}${PROPNAMECOLOR}${COLOR_USER}${BG}${USER}${PROPNAMECOLOR}${BG}@${LIGHTPURPLE}${BG}${HOSTNAME%%.*}${DOName}${PROPNAMECOLOR}${BG}:${PURPLE}${BG}\w${NC} ${BROWN}${BG}\$(parse_git_branch)${NC}${BROWN}${BG}\$(echo_if_platform_set)${NC}\n\${SPECIAL_PRMPT_DATA}\$(UpdateTmuxWinIdx)Cmd$ \$(changeTmuxWindowsEveryTime)"' DEBUG
}

SetBasicTrap()
{
   local DOName=""
   export PROMPT_DIRTRIM=3
   export TMUX_WINIDX=""
   if [ ! -z "$TMUX" ]; then
       export TMUX_WINIDX="["$(tmux display-message -p '#I')"."$(tmux display-message -p '#P')"] "
   fi
   if [ ! -z "$WINDOW" ]; then
       export TMUX_WINIDX="[$WINDOW] "
   fi
   trap 'PS1="\n${PROPNAMECOLOR}${BG}(\$((\! -1)) $(((SHLVL>1))&&echo "SL:$SHLVL ")${PROPNAMECOLOR}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*}${PROPNAMECOLOR}${BG}) ${PROPNAMECOLOR}${BG}Date:${PROPCOLOR}${BG}\D{%d-%b-%y} \D{%T %Z} ${PROPNAMECOLOR}${BG}Os:${PROPCOLOR}${BG}$OSVer${PROPNAMECOLOR}${BG} ${PURPLE}${BG}\$(GetGBaseParent)${NC}${PROPNAMECOLOR}${COLOR_USER}${BG}${USER}${PROPNAMECOLOR}${BG}@${LIGHTPURPLE}${BG}${HOSTNAME%%.*}${DOName}${PROPNAMECOLOR}${BG}:${PURPLE}${BG}\w${NC} ${BROWN}${BG}\$(parse_git_branch)${NC}${BROWN}${BG}\$(echo_if_platform_set)${NC}\n\${SPECIAL_PRMPT_DATA}\$(UpdateTmuxWinIdx)Cmd$ \$(changeTmuxWindowsEveryTime)"' DEBUG
}

if [ "$TERM" == "screen" ]
then

        changeTmuxWindowsEveryTime
        export TERM=xterm-256color
        export force_color_prompt=yes
fi

trimoutput() {
    local MAX_CHARS=`stty size | awk '{ print $2 }'`
    $* | cut -c -$MAX_CHARS
}


myssh ()
{
    ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" $1
}

mysshtest ()
{
    echo $1 | grep "@" > /dev/null
    if [ $? -ne 0 ]; then
        echo "Please specify user@host";
        return;
    fi

    ssh -o "BatchMode yes" $1 "ls > /dev/null" > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "Setting passwordless login";
        ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" $1 "mkdir ~/.ssh; echo `cat ~/.ssh/id_rsa.pub` >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 644 ~/.ssh/authorized_keys"
        ssh -o "BatchMode yes" $1 "ls > /dev/null" > /dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "Coping custom bashrc";
            tar cf - -C ~/.vim/ bashrc | ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" $1 "tar xf - > /dev/null 2>&1;"
            echo "Logging to bash";
            ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -t $1 "bash --rcfile ~/bashrc -i;"
        else
            echo "Coping custom bashrc";
            tar cf - -C ~/.vim bashrc | ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "BatchMode yes"  -o "ForwardX11=yes" $1 "tar xf - > /dev/null 2>&1;"
            echo "Logging to bash";
            ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -o "BatchMode yes" -t $1 "bash --rcfile ~/bashrc -i;"
        fi
    else
        echo "Coping custom bashrc";
        tar cf - -C ~/.vim bashrc | ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "BatchMode yes"  -o "ForwardX11=yes" $1 "tar xf - > /dev/null 2>&1;"
        echo "Logging to bash";
        tmux rename-window "$(echo $* | cut -d @ -f2)"
        ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -o "BatchMode yes" -t $1 "bash --rcfile ~/.bashrc -i;"
    fi
}

mysshcftatuld ()
{
    mysshtest atuld@pcft-vm${1}.$PUNIN
}

mysshcft ()
{
    echo $1 | egrep "[0-9]*" > /dev/null
    if [ $? -ne 0 ]; then
        return;
    fi
    mysshtest root@pcft-vm${1}.$PUNIN
}

mysshcftpneatuld ()
{
    mysshtest atuld@pcft-vm${1}.$PNE
}

mysshcftpne ()
{
    echo $1 | egrep "[0-9]*" > /dev/null
    if [ $? -ne 0 ]; then
        return;
    fi
    mysshtest root@pcft-vm${1}.$PNE
}

mysshpass ()
{
    echo "Coping custom bashrc";
    tar cf - -C ~/.vim bashrc | sshpass -f ~/.stdpass ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "BatchMode yes" -o "ForwardX11=yes" $1 "tar xf - > /dev/null 2>&1;";
    echo "Logging to bash";
    sshpass -f ~/.stdpass ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -o "BatchMode yes" -t $1 "bash --rcfile ~/bashrc -i;"
}

#vimscp () {    CMD=`echo $1 | sed -e's/:/\//g'`;    CMD="scp://${CMD}";    vim $CMD; }
vimscp () {    CMD=`echo $@ | sed -e's/:/\//g'`; newCMD="";  for tok in `echo $CMD`; do `echo $tok | egrep ".*@.*//.*" > /dev/null`; if [ $? -eq 0 ]; then newCMD=$newCMD" scp://${tok}"; else newCMD=$newCMD" $tok"; fi;  done;   vim $newCMD; }

# connect to server and start the java gui at Windows Eng server
jnbSAcft () { ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" root@pcft-vm$1 "/usr/openv/netbackup/bin/jnbSA -d $WIN_ENG_SYS.$PUNIN:1.0 &"; }

alias mysshpasscmd="sshpass -f ~/.stdpass ssh $@"

if [ -z "${VIM_BASHRC_CALLED}" ] || [ "${VIM_BASHRC_CALLED}" -eq 0 ]; then
PATH=$PATH:/usr/openv/netbackup/bin/admincmd:/usr/openv/netbackup/bin:/usr/openv/db/bin:/usr/openv/netbackup/bin/goodies:/usr/openv/netbackup/bin/support:/usr/openv/netbackup/sec/at/bin:/usr/openv/volmgr/bin:/usr/openv/java/jre/bin
export PATH
fi

ls > /dev/null; if [ $? -ne 0 ]; then alias ls='ls -hF --color'; fi

if [ "$OSName" != "AIX" ]; then alias df='df -h'; alias du='du -h'; fi

which vim > /dev/null
if [ $? -ne 0 ]; then alias vim='vi'; fi

##########################
# tmux funtions start
##########################

function tmuxv {
    tmux split-window -dh "$*"
}

function tmanv {
    tmux split-window -dh "man $*"
}

function tmanh {
    tmux split-window -dv "man $*"
}

function tmuxh {
    tmux split-window -dv "$*"
}

function ttmux {
    local SID=`tty | cut -d'/' -f4`
    echo $1 | egrep "[0-9]+" > /dev/null
    if [ $? -eq 0 ]; then
        SID=$1
    fi

    if [ "$1" == "ls" ]; then
        CMD="tmux ls";
    else
        CMD="tmux attach -d -t tmux_$SID || tmux new -s tmux_$SID"
    fi
    ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -t $NIS_USER@$NIS_SERVER $CMD
}

function tscreen {
    local SID=`tty | cut -d'/' -f4`
    echo $1 | egrep "[0-9]+" > /dev/null
    if [ $? -eq 0 ]; then
        SID=$1
    fi

    if [ "$1" == "ls" ]; then
        CMD="screen -ls";
    else
        CMD="screen -d -R tmux_$SID"
    fi
    ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -t $NIS_USER@$NIS_SERVER $CMD
}
##########################
# tmux funtions end
##########################


##########################
# git funtions start
##########################
function gfuncdiff() {
    for f in  `git diff --name-only $1`; do git diff $1 $f; done
}

function gstashclone () {
    if [ "$1" == "" ]; then
        echo "Error: Argument expected.."
    else
        git clone ${USER_STASH_URL}
    fi
}

##########################
# git funtions end
##########################

##########################
# NBU specific function start
##########################

#untar the nbu patch files 1=tar path 2=patch version 3=OS name
untarpatch () {  tar -xvf $1 NB_update.install VrtsNB_CLT_${2}.README VrtsNB_CLT_${2}.postinstall VrtsNB_CLT_${2}.postuninstall VrtsNB_CLT_${2}.preinstall VrtsNB_CLT_${2}.${3}.tar.gz; }
untarcltpatch () {
                    VER=`echo "$1" | sed -e's/.*NB_CLT_//g' | sed -e's/.tar$//g'`;
                    if [ -z "$2" ]; then if [ "$OSName" = "Linux" ]; then PLT="Linux"; fi; if [ "$OSName" = "SunOS" ]; then PLT="Solaris"; fi; if [ "$OSName" = "AIX" ]; then PLT="RS6000"; fi; else PLT=$2; fi;
                    tar -xvf $1 NB_update.install VrtsNB_CLT_${VER}.README VrtsNB_CLT_${VER}.postinstall VrtsNB_CLT_${VER}.postuninstall VrtsNB_CLT_${VER}.preinstall VrtsNB_CLT_${VER}.${PLT}.tar.gz;
                  }

##########################
# NBU specific function end
##########################


if [ "$OSName" != "Darwin" ]; then
    if [ -f /usr/bin/banner ]; then banner "wel-come" && banner "$USER"; fi
fi

if [ -f ~/.vim/alias.global ]; then
   source ~/.vim/alias.global
fi
if [ -f ~/.vim/inputrc ]; then
   source ~/.vim/inputrc
fi
if [ -f ~/.alias ]; then
   source ~/.alias
fi

export HISTFILESIZE=2000
export HISTSIZE=1000
export HISTIGNORE='export VIMPASS=*:VIMPASS=*:'$HISTIGNORE

export SSH_RMNDEV='$NIS_USER@$NIS_SERVER'

export CSCOPE_EDITOR=vim

if [ -z "${VIM_BASHRC_CALLED}" ] || [ "${VIM_BASHRC_CALLED}" -eq 0 ]; then
PATH="/Users/atul.das1/perl5/bin${PATH+:}${PATH}"; export PATH;
PERL5LIB="/Users/atul.das1/perl5/lib/perl5${PERL5LIB+:}${PERL5LIB}"; export PERL5LIB;
PERL_LOCAL_LIB_ROOT="/Users/atul.das1/perl5${PERL_LOCAL_LIB_ROOT+:}${PERL_LOCAL_LIB_ROOT}"; export PERL_LOCAL_LIB_ROOT;
PERL_MB_OPT="--install_base \"/Users/atul.das1/perl5\""; export PERL_MB_OPT;
PERL_MM_OPT="INSTALL_BASE=/Users/atul.das1/perl5"; export PERL_MM_OPT;
fi

myhelp () {
echo "Below are the alias and functions you have"
echo "********************"
echo "********************"
alias
echo "********************"
echo function name
echo "   bcd # == back to # no dir"
echo "   mcd <path> == create dirs and cd to newly creared dir"
echo "********************"
declare -F
echo "********************"
}

export VIM_BASHRC_CALLED=1
shopt -s direxpand 2>/dev/null
