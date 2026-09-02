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
RCCOLOR=${blue}

# Source global definitions
if [ -f /etc/bashrc ]; then
   . /etc/bashrc
fi

MANPATH=$MANPATH:/usr/dt/man:/usr/man:/usr/openwin/share/man:/usr/openv/man/share/man
export MANPATH

# User specific aliases and functions
#required by screen and tmux
export DOName=''

OSName=`uname -s`

if [ "$OSName" = "SunOS" ]; then PATCHNO=`cat /etc/release | grep "Solaris" | sed -e's/.*_u//' | cut -c1-2 | grep "[0-9]"`; if [ $? -ne 0 ]; then OSVer="SunOS_"`uname -r`; else OSVer="SunOS_"`uname -r`"U"${PATCHNO/\w/}; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "SunOS" ]; then if [ "`uname -r`" == "5.11" ]; then BASH_FG="-v"; else BASH_FG="-r"; fi; PATCHNO=`cat /etc/release | grep "Solaris" | sed -e's/.*_u//' | cut -c1-2 | grep "[0-9]"`; if [ $? -ne 0 ]; then OSVer="SunOS_"`uname $BASH_FG| sed -e's/5.//g'`; else OSVer="SunOS_"`uname $BASH_FG| sed -e's/5.//g'`"U"${PATCHNO/\w/}; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "AIX" ]; then OSVer=`oslevel | cut -d'.' -f1-2``oslevel -s | cut -d"-" -f2 | grep -v "00" | xargs -i expr {} | xargs -i echo " TL"{}``oslevel -s | cut -d"-" -f3 | grep -v "00" | xargs -i expr {} | xargs -i echo " SP"{}`; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/lsb-release ]; then OSVer="Ubuntu_"`lsb_release -r | cut -f2`; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release ]; then lsb_release > /dev/null 2>/dev/null; if [ $? -eq 0 ]; then OSVer="RHEL_"`lsb_release -r | cut -f2`; else OSVer="RHEL_"`grep -oE '[0-9]+(\.[0-9]+)*' /etc/redhat-release | head -1`; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release -a -f /etc/oracle-release ]; then lsb_release > /dev/null 2>/dev/null; if [ $? -eq 0 ]; then OSVer="OEL_"`lsb_release -r | cut -f2`; else OSVer="OEL_"`grep -oE '[0-9]+(\.[0-9]+)*' /etc/redhat-release | head -1`; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release -a -f /etc/centos-release ]; then lsb_release > /dev/null 2>/dev/null; if [ $? -eq 0 ]; then OSVer="CentOS_"`lsb_release -r | cut -f2 | awk -F'.' '{ printf $1"."$2 }'`; else OSVer="CentOS_"`grep -oE '[0-9]+(\.[0-9]+)*' /etc/redhat-release | head -1`; fi; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/redhat-release ] && grep -qi 'rocky' /etc/redhat-release; then OSVer="Rocky_"`grep -oE '[0-9]+(\.[0-9]+)*' /etc/redhat-release | head -1`; PROCName=`uname -p`; fi
if [ "$OSName" = "Linux" -a -f /etc/SuSE-release ]; then OSVer="SuSE_"`lsb_release -r | cut -f2`; PROCName=`uname -p`; fi
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
        if [ $? -eq 0 ]; then NBU_TYPE="Master";
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
        export NBU_DATA="${BROWN}${BG}[NBU Type:${blue}${BG}${NBU_TYPE} ${BROWN}${BG}Ver:${blue}${BG}${NBU_VER}${BROWN}${BG} ${NBU_BUILDNUMBER}${BROWN}${BG}Master:${blue}${BG}${NBU_MASTER}${BROWN}${BG}]"
        export NBU_DATA_TERMINAL="NBU Type: ${NBU_TYPE} \nVer: ${NBU_VER} \n${NBU_BUILDNUMBER_TERMINAL} \nMaster: ${NBU_MASTER} \nClient: ${NBU_CLIENT_NAME} \n${NBU_RELEASEDATE}"
    fi
}

GetNBUData

.nb.ver ()
{
    GetNBUData
    if [ "$OSName" = "SunOS" ]; then
        printf "$NBU_DATA_TERMINAL\n" | col
    else
        printf "$NBU_DATA_TERMINAL\n" | column -s ':' -t
    fi
}

.nb.path ()
{
    if [ -f /usr/openv/netbackup/bin/bpcd ]; then
        echo "NetBackup installed path: " `realpath /usr/openv/`
    else
        echo "NetBackup is not installed."
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

# Helper: Get file counts efficiently (avoids duplicate ls calls)
_prompt_file_counts() {
    local all_count=$(ls -A 2>/dev/null | wc -l | tr -d ' ')
    local visible_count=$(ls 2>/dev/null | wc -l | tr -d ' ')
    echo "Files:${all_count} Hdn:$((all_count - visible_count))"
}

# IST:${blue}${BG}`TZ=Asia/Calcutta date "+%e-%B-%G %H:%M:%S"`
SetLongTrap()
{
    UpdateTmuxWinIdx > /dev/null
    trap '_cmd_timer_start; PS1="\n${CYAN}\${EXEC_TIME_DISPLAY}${NC}${PROPNAMECOLOR}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*} ${PURPLE}${BG}(\$((\! -1)):\#) ${PROPNAMECOLOR}${BG}[Date:${PROPCOLOR}${BG}\D{%e-%B-%G} ${PROPNAMECOLOR}${BG}Time:${PROPCOLOR}${BG}\t ${PROPNAMECOLOR}${BG}Jobs:${PROPCOLOR}${BG}\j${PROPNAMECOLOR}${BG}] ${PROPNAMECOLOR}${BG}[OS:${PROPCOLOR}${BG}${OSName} ${PROPNAMECOLOR}${BG}Ver:${PROPCOLOR}${BG}${OSVer}${PROPNAMECOLOR}${BG} ${PROPNAMECOLOR}${BG}Proc:${PROPCOLOR}${BG}${PROCName}${PROPNAMECOLOR}${BG}${DARWIN_DATA}${PROPNAMECOLOR}${BG}TTY:${PROPCOLOR}${BG}${TTYNAME}${PROPNAMECOLOR}${BG}] [${PROPCOLOR}\$(_prompt_file_counts)${PROPNAMECOLOR}] ${NBU_DATA} \n${COLOR_USER}${BG}${USER}${PROPNAMECOLOR}${BG}@${LIGHTPURPLE}${BG}${HOSTNAME}${DOName}${PROPNAMECOLOR}${BG}:${PURPLE}${BG}\$PWD ${NC} ${BROWN}${BG}\$(parse_git_branch)${NC}\n\${SPECIAL_PRMPT_DATA}\$(UpdateTmuxWinIdx)Cmd$ \$(changeTmuxWindowsEveryTime)"' DEBUG
}

CurrDirDepth() {
    echo `pwd | awk -F"/" '{print NF - 1 ; }'`
}

# Single source of truth for TMUX window/pane index
UpdateTmuxWinIdx () {
    export TMUX_WINIDX=""
    if [[ -n "$TMUX" ]]; then
        local win_idx=$(tmux display-message -p '#I')
        local pane_idx=$(tmux display-message -p '#P')
        local total_wins=$(tmux display-message -p '#{session_windows}')
        local total_panes=$(tmux display-message -p '#{window_panes}')
        export TMUX_WINIDX="[${win_idx}w${total_wins}.${pane_idx}p${total_panes}] "
    elif [[ -n "$WINDOW" ]]; then
        export TMUX_WINIDX="[$WINDOW] "
    fi
    echo "$TMUX_WINIDX"
}

# \W basename of current directory
SetShortTrap()
{
   local DOName=""
   export PROMPT_DIRTRIM=3
   UpdateTmuxWinIdx > /dev/null
   trap '_cmd_timer_start; PS1="\n${CYAN}\${EXEC_TIME_DISPLAY}${NC}${PROPNAMECOLOR}${BG}(\$((\! -1)) ${PROPNAMECOLOR}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*}${PROPNAMECOLOR}${BG}) ${PROPNAMECOLOR}${BG}Date:${PROPCOLOR}${BG}\D{%d-%b-%y} \D{%T %Z} ${PROPNAMECOLOR}${BG}Jobs:${PROPCOLOR}${BG}\j${PROPNAMECOLOR}${BG} ${PROPCOLOR}\$(_prompt_file_counts) ${PROPNAMECOLOR}pushd:${PROPCOLOR}$(( $( dirs -v | wc -l ) - 1 )) ${PROPNAMECOLOR}${BG}DskUsg:${PROPCOLOR}${BG}\$([ -f ~/.vim/scripts/rootDiskUsage.sh ] && ~/.vim/scripts/rootDiskUsage.sh || [ -f ~/bin/rootDiskUsage.sh ] && ~/bin/rootDiskUsage.sh)${PROPNAMECOLOR}${BG} ${PROPNAMECOLOR}${BG}Os:${PROPCOLOR}${BG}$OSVer${PROPNAMECOLOR}${BG} ${PROPNAMECOLOR}${COLOR_USER}${BG}${USER}${PROPNAMECOLOR}${BG}@${LIGHTPURPLE}${BG}${HOSTNAME%%.*}${DOName}${PROPNAMECOLOR}${BG}:${PURPLE}${BG}\w${NC} ${BROWN}${BG}\$(parse_git_branch)${NC}\n\${SPECIAL_PRMPT_DATA}\$(UpdateTmuxWinIdx)Cmd$ \$(changeTmuxWindowsEveryTime)"' DEBUG
}

SetBasicTrap()
{
   local DOName=""
   export PROMPT_DIRTRIM=3
   UpdateTmuxWinIdx > /dev/null
   trap '_cmd_timer_start; PS1="\n${CYAN}\${EXEC_TIME_DISPLAY}${NC}${PROPNAMECOLOR}${BG}(\$((\! -1)) $(((SHLVL>1))&&echo "SL:$SHLVL ")${PROPNAMECOLOR}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*}${PROPNAMECOLOR}${BG}) ${PROPNAMECOLOR}${BG}Date:${PROPCOLOR}${BG}\D{%d-%b-%y} \D{%T %Z} ${PROPNAMECOLOR}${BG}Os:${PROPCOLOR}${BG}$OSVer${PROPNAMECOLOR}${BG} ${PROPNAMECOLOR}${COLOR_USER}${BG}${USER}${PROPNAMECOLOR}${BG}@${LIGHTPURPLE}${BG}${HOSTNAME%%.*}${DOName}${PROPNAMECOLOR}${BG}:${PURPLE}${BG}\w${NC} ${BROWN}${BG}\$(parse_git_branch)${NC}\n\${SPECIAL_PRMPT_DATA}\$(UpdateTmuxWinIdx)Cmd$ \$(changeTmuxWindowsEveryTime)"' DEBUG
}

SetBasicTrap

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

if [ "`date +%Z`" != "IST" ]; then

trap 'PS1="\n${BROWN}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*} ${PURPLE}${BG}(\!:\#) \
${BROWN}${BG}[Date:${blue}${BG}\D{%e-%B-%G} ${BROWN}${BG}Time:${blue}${BG}\t ${BROWN}${BG}IST:${blue}${BG}`TZ=Asia/Calcutta date "+%e-%B-%G %H:%M:%S"`${BROWN}${BG} ${BROWN}${BG}Jobs:${blue}${BG}\j${BROWN}${BG}] \
${BROWN}${BG}[OS:${blue}${BG}${OSName} ${BROWN}${BG}Ver:${blue}${BG}${OSVer}${BROWN}${BG} ${BROWN}${BG}Proc:${blue}${BG}${PROCName}${BROWN}${BG} ${BROWN}${BG}TTY:${blue}${BG}${TTYNAME}${BROWN}${BG}] \
${NBU_DATA}\
\n${COLOR_USER}${BG}${USER}${BROWN}${BG}@${blue}${BG}${HOSTNAME}${DOName}${BROWN}${BG}:${PURPLE}${BG}\$PWD ${NC}\nCmd$ $(changeTmuxWindowsEveryTime)"' DEBUG

else

    trap 'PS1="\n${BROWN}${BG}(\$((\! - 1 )) ${BROWN}${BG}RC:${RED}${BG}\${?##0}${GREEN}${BG}\${?##[1-9]*}${BROWN}${BG}) ${PURPLE}${BG} \
${BROWN}${BG}[Date:${blue}${BG}\D{%e-%B-%G} ${BROWN}${BG}Time:${blue}${BG}\t ${BROWN}${BG}Jobs:${blue}${BG}\j${BROWN}${BG}] \
${BROWN}${BG}[OS:${blue}${BG}${OSName} ${BROWN}${BG}Ver:${blue}${BG}${OSVer}${BROWN}${BG} ${BROWN}${BG}Proc:${blue}${BG}${PROCName}${BROWN}${BG} ${BROWN}${BG}TTY:${blue}${BG}${TTYNAME}${BROWN}${BG}] \
${NBU_DATA} $(parse_git_branch)\
\n${COLOR_USER}${BG}${USER}${BROWN}${BG}@${blue}${BG}${HOSTNAME}${DOName}${BROWN}${BG}:${PURPLE}${BG}\$PWD ${NC}\nCmd$ $(changeTmuxWindowsEveryTime)"' DEBUG

fi

TMUXINFO=" ${HOSTNAME/.*/} $OSName ${OSVer} TstStp"
#PROMPT_COMMAND='echo -ne "\033_${USER}@${HOSTNAME%%.*}:${PWD/#$HOME/~}"; echo -ne "\033\\";printf "\033k$TMUXINFO\033\\"'
if [ "$TERM" == "screen" ]; then
    changeTmuxWindowsEveryTime
fi

alias cd.nbbin='cd /usr/openv/netbackup/bin/'
alias cd.nadmin='cd /usr/openv/netbackup/bin/admincmd/'
alias cd.olog='cd /usr/openv/logs'
alias cd.nblog='cd /usr/openv/netbackup/logs'
alias cd.ov='cd /usr/openv'

alias e.nblogconf='vim /usr/openv/netbackup/nblog.conf'
alias e.bpconf='vim /usr/openv/netbackup/bp.conf'

alias cat.nblogconf='cat /usr/openv/netbackup/nblog.conf'
alias cat.bpconf='cat /usr/openv/netbackup/bp.conf'
alias cat.nbver='cat /usr/openv/netbackup/version'
alias cat.nbinver='cat /usr/openv/netbackup/bin/version'

alias dir="ls"
alias copy="cp"
alias rename="mv"
alias md="mkdir"
alias rd="rmdir"
alias del="rm -i"
alias l='ls -CF'
alias la='ls -ACF'
alias ll='ls -l'
alias l1='ls -1'
alias l1a='ls -1Fa'
alias ls='ls -hF --color'
alias l.='ls -d .* --color=auto'
alias lld='ls --color=always -al | grep --color=never "^d"'
alias lll='ls -la | less -X'
alias lart='ls -ACFrt'
alias lrt='ls -CFrt'
alias llrt='ls -lFrt'
alias dir='ls -l'
alias grep='grep --color'
alias rga='rg -n --color=always --hidden --follow --ignore-case'

ls > /dev/null; if [ $? -ne 0 ]; then alias ls='ls -hF --color'; fi

if [ "$OSName" != "AIX" ]; then alias df='df -h'; alias du='du -h'; fi

which vim > /dev/null
if [ $? -ne 0 ]; then alias vim='vi'; fi

##########################
# tmux functions start
##########################

# Split pane vertical (right) - persistent shell with command
tx.vp() {
    local pane_id
    pane_id=$(tmux split-window -dh -P -F '#{pane_id}')
    [[ -n "$*" ]] && tmux send-keys -t "$pane_id" "$*" Enter
}

# Split pane horizontal (below) - persistent shell with command
tx.hp() {
    local pane_id
    pane_id=$(tmux split-window -dv -P -F '#{pane_id}')
    [[ -n "$*" ]] && tmux send-keys -t "$pane_id" "$*" Enter
}

# Split pane vertical (right) - run command and close when done
tx.vx() { tmux split-window -dh "bash -ic '$*'"; }

# Split pane horizontal (below) - run command and close when done
tx.hx() { tmux split-window -dv "bash -ic '$*'"; }

# Split vertical and jump to new pane
tx.vj() {
    tmux split-window -h
    [[ -n "$*" ]] && tmux send-keys "$*" Enter
}

# Split horizontal and jump to new pane
tx.hj() {
    tmux split-window -v
    [[ -n "$*" ]] && tmux send-keys "$*" Enter
}

# New window and jump to it
tx.wj() {
    tmux new-window
    [[ -n "$*" ]] && tmux send-keys "$*" Enter
}

# New window, run command, close when done
tx.w() { tmux new-window "bash -ic '$*'"; }

# Split vertical and show man page
tx.vman() { tmux split-window -dh "man $*"; }

# Split horizontal and show man page
tx.hman() { tmux split-window -dv "man $*"; }

# Split vertical with readonly viewer (bat or less)
tx.vw() {
    local file="$1"
    [[ -z "$file" ]] && { echo "Usage: tx.vw <file>"; return 1; }
    if command -v bat &>/dev/null; then
        tmux split-window -dh "bat --style=header,numbers,grid,changes --color=always --paging=always --tabs=4 --wrap=auto '$file'"
    else
        tmux split-window -dh "less -i -g -J -N -F -R -S -M -W -Q --mouse '$file'"
    fi
}

# Remote tmux session
tx.remote() {
    local SID=$(tty | cut -d'/' -f4)
    [[ "$1" =~ ^[0-9]+$ ]] && SID=$1
    if [[ "$1" == "ls" ]]; then
        CMD="tmux ls"
    else
        CMD="tmux attach -d -t tmux_$SID || tmux new -s tmux_$SID"
    fi
    ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -t $NIS_USER@$NIS_SERVER $CMD
}

# Remote screen session
tx.scr() {
    local SID=$(tty | cut -d'/' -f4)
    [[ "$1" =~ ^[0-9]+$ ]] && SID=$1
    if [[ "$1" == "ls" ]]; then
        CMD="screen -ls"
    else
        CMD="screen -d -R tmux_$SID"
    fi
    ssh -X -Y -o "TCPKeepAlive=yes" -o "ServerAliveInterval=90" -o "ServerAliveCountMax=10" -o "ForwardX11=yes" -t $NIS_USER@$NIS_SERVER $CMD
}

# ── Modern tmux popup features ──────────────────────────────────────────────

# Generic popup - run any command in a popup window
tx.popup() {
    if [[ -n "$*" ]]; then
        tmux display-popup -E -w 80% -h 70% -d "#{pane_current_path}" "bash -ic '$*'"
    else
        tmux display-popup -E -w 80% -h 70% -d "#{pane_current_path}" "$SHELL"
    fi
}

# FZF file picker in popup
tx.fzf() {
    tmux display-popup -E -w 80% -h 70% -d "#{pane_current_path}" \
        'file=$(fzf --preview "cat {}") && [ -n "$file" ] && ${EDITOR:-vim} "$file"'
}

# htop in popup
tx.htop() { tmux display-popup -E -w 90% -h 80% "htop"; }

# lazygit in popup
tx.lazygit() {
    command -v lazygit &>/dev/null && tmux display-popup -E -w 90% -h 90% -d "#{pane_current_path}" "lazygit" || echo "lazygit not installed"
}

# Quick scratch terminal popup
tx.pad() { tmux display-popup -E -w 60% -h 50% -d "#{pane_current_path}" "$SHELL"; }

# Run command in popup and wait
tx.run() { tmux display-popup -E -w 80% -h 70% -d "#{pane_current_path}" "bash -ic '$*; echo; read -n 1 -s -r -p \"Press any key\"'"; }

# Tail logs in popup
tx.logs() { tmux display-popup -E -w 90% -h 80% "tail -f ${1:-/var/log/system.log}"; }

# List tx commands
tx.help() { echo "tx.vp tx.hp tx.vx tx.hx tx.vj tx.hj tx.w tx.wj tx.vman tx.hman tx.vw tx.remote tx.scr tx.popup tx.fzf tx.htop tx.lazygit tx.pad tx.run tx.logs"; }

##########################
# tmux functions end
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

if [ -f /usr/bin/banner ]; then banner "wel-come" && banner "$USER"; fi

export PATH=$PATH:/usr/openv/netbackup/bin/admincmd:/usr/openv/netbackup/bin:/usr/openv/db/bin
export TERM=xterm

if [ -f ~/.vim/alias.global ]; then
   source ~/.vim/alias.global
fi
if [ -f ~/.vim/inputrc ]; then
   source ~/.vim/inputrc
fi
if [ -f ~/.alias ]; then
   source ~/.alias
fi

export HISTFILESIZE=500000
export HISTSIZE=100000
export HISTIGNORE='export VIMPASS=*:VIMPASS=*:'$HISTIGNORE

export CSCOPE_EDITOR=/usr/local/bin/vim

##########################
# ENHANCEMENTS START
##########################

# --- Timezone shortcuts ---
alias tz.ist='TZ="Asia/Kolkata" date +"%Y-%m-%d %H:%M:%S %Z"'
alias tz.utc='TZ="UTC" date +"%Y-%m-%d %H:%M:%S %Z"'
alias tz.pst='TZ="America/Los_Angeles" date +"%Y-%m-%d %H:%M:%S %Z"'
alias tz.est='TZ="America/New_York" date +"%Y-%m-%d %H:%M:%S %Z"'
alias tz.cst='TZ="America/Chicago" date +"%Y-%m-%d %H:%M:%S %Z"'
alias tz.all='echo "Local: $(date +"%Y-%m-%d %H:%M:%S %Z")"; echo "UTC:   $(TZ=UTC date +"%Y-%m-%d %H:%M:%S %Z")"; echo "IST:   $(TZ=Asia/Kolkata date +"%Y-%m-%d %H:%M:%S %Z")"; echo "PST:   $(TZ=America/Los_Angeles date +"%Y-%m-%d %H:%M:%S %Z")"'

# --- SSH Agent Management ---
_start_ssh_agent() {
    if [[ -z "$SSH_AUTH_SOCK" ]] || ! ssh-add -l &>/dev/null; then
        local agent_file="$HOME/.ssh/agent.env"
        if [[ -f "$agent_file" ]]; then
            source "$agent_file" &>/dev/null
        fi
        if ! ssh-add -l &>/dev/null; then
            eval "$(ssh-agent -s)" > /dev/null
            echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > "$agent_file"
            echo "export SSH_AGENT_PID=$SSH_AGENT_PID" >> "$agent_file"
            chmod 600 "$agent_file"
            [[ -f ~/.ssh/id_rsa ]] && ssh-add ~/.ssh/id_rsa 2>/dev/null
            [[ -f ~/.ssh/id_ed25519 ]] && ssh-add ~/.ssh/id_ed25519 2>/dev/null
        fi
    fi
}
[[ $- == *i* ]] && _start_ssh_agent
alias ssh.keys='ssh-add -l'
alias ssh.add='ssh-add'

# --- FZF Keybindings ---
if [[ -f ~/.fzf.bash ]]; then
    source ~/.fzf.bash
elif [[ -f /usr/share/fzf/key-bindings.bash ]]; then
    source /usr/share/fzf/key-bindings.bash
    source /usr/share/fzf/completion.bash 2>/dev/null
elif [[ -f /opt/homebrew/opt/fzf/shell/key-bindings.bash ]]; then
    source /opt/homebrew/opt/fzf/shell/key-bindings.bash
    source /opt/homebrew/opt/fzf/shell/completion.bash 2>/dev/null
elif [[ -f /usr/local/opt/fzf/shell/key-bindings.bash ]]; then
    source /usr/local/opt/fzf/shell/key-bindings.bash
    source /usr/local/opt/fzf/shell/completion.bash 2>/dev/null
fi
export FZF_DEFAULT_OPTS='--height 40% --layout=reverse --border'
export FZF_CTRL_R_OPTS='--sort --exact'

# --- Directory Bookmarks ---
export DIRMARKS_DIR="$HOME/.dirmarks"
[[ -d "$DIRMARKS_DIR" ]] || mkdir -p "$DIRMARKS_DIR"

mark() {
    local name="${1:-$(basename "$PWD")}"
    ln -sfn "$PWD" "$DIRMARKS_DIR/$name"
    echo "Bookmarked: $name -> $PWD"
}

jump() {
    local target="$DIRMARKS_DIR/$1"
    if [[ -L "$target" ]]; then
        cd -P "$target" || return 1
    else
        echo "Bookmark not found: $1"
        marks
        return 1
    fi
}

marks() {
    echo "Directory bookmarks:"
    for f in "$DIRMARKS_DIR"/*; do
        [[ -L "$f" ]] && printf "  %-15s -> %s\n" "$(basename "$f")" "$(readlink "$f")"
    done
}

unmark() {
    if [[ -L "$DIRMARKS_DIR/$1" ]]; then
        rm "$DIRMARKS_DIR/$1"
        echo "Removed bookmark: $1"
    else
        echo "Bookmark not found: $1"
    fi
}

_dirmarks_complete() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    COMPREPLY=($(compgen -W "$(ls "$DIRMARKS_DIR" 2>/dev/null)" -- "$cur"))
}
complete -F _dirmarks_complete jump unmark

# --- Command Execution Time ---
_cmd_timer_start() {
    _cmd_start_time=${_cmd_start_time:-$SECONDS}
}

_cmd_timer_stop() {
    local elapsed=$((SECONDS - ${_cmd_start_time:-$SECONDS}))
    unset _cmd_start_time
    if [[ $elapsed -ge 12 ]]; then
        if [[ $elapsed -ge 3600 ]]; then
            _last_cmd_time="$(($elapsed/3600))h$((($elapsed%3600)/60))m$(($elapsed%60))s"
        elif [[ $elapsed -ge 60 ]]; then
            _last_cmd_time="$(($elapsed/60))m$(($elapsed%60))s"
        else
            _last_cmd_time="${elapsed}s"
        fi
        export EXEC_TIME_DISPLAY="⏱ ${_last_cmd_time} "
    else
        export EXEC_TIME_DISPLAY=""
    fi
}

# Set PROMPT_COMMAND for timer stop (timer start is integrated into Set*Trap functions)
PROMPT_COMMAND="_cmd_timer_stop${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

# --- Kubernetes Context ---
_k8s_context() {
    if command -v kubectl &>/dev/null && [[ -f ~/.kube/config ]]; then
        local ctx ns
        ctx=$(kubectl config current-context 2>/dev/null)
        if [[ -n "$ctx" ]]; then
            ns=$(kubectl config view --minify --output 'jsonpath={..namespace}' 2>/dev/null)
            echo "⎈ ${ctx}/${ns:-default} "
        fi
    fi
}

if command -v kubectl &>/dev/null; then
    alias k='kubectl'
    alias kgp='kubectl get pods'
    alias kgs='kubectl get svc'
    alias kgn='kubectl get nodes'
    alias kga='kubectl get all'
    alias kctx='kubectl config get-contexts'
    alias kns='kubectl config set-context --current --namespace'
    alias klog='kubectl logs -f'
    alias kexec='kubectl exec -it'
fi

##########################
# ENHANCEMENTS END
##########################

myhelp () {
echo "Below are the alias and functions you have"
echo "********************"
echo "********************"
alias
echo "********************"
echo function name
echo "   bcd # == back to # no dir"
echo "   mcd <path> == create dirs and cd to newly creared dir"
echo "   mark [name] == bookmark current directory"
echo "   jump <name> == jump to bookmarked directory"
echo "   marks == list all bookmarks"
echo "   tz.ist/tz.utc/tz.pst/tz.all == timezone shortcuts"
echo "********************"
declare -F
echo "********************"
}

shopt -s direxpand 2>/dev/null
