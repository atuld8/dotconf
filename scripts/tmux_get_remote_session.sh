#!/bin/bash
HOSTNAME=$1
USER=$2
ACTION=$3
ping -n 3 $HOSTNAME > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "$HOSTNAME is not pingable..."
    exit /b 1
fi

if [ "$ACTION" == "dup" ]; then
        ssh -X -Y -o TCPKeepAlive=yes -o ServerAliveInterval=90 -o ServerAliveCountMax=10 -o ForwardX11=yes -l $USER $HOSTNAME -t tmux attach -t main
    elif [ "$ACTION" == "new" ]; then
            ssh -X -Y -o TCPKeepAlive=yes -o ServerAliveInterval=90 -o ServerAliveCountMax=10 -o ForwardX11=yes -l $USER $HOSTNAME -t tmux
        else
                ssh -X -Y -o TCPKeepAlive=yes -o ServerAliveInterval=90 -o ServerAliveCountMax=10 -o ForwardX11=yes -l $USER $HOSTNAME -t ./tmux
fi

