NEW_SESSION=1

for f in {1..9};
do
    MACHINE_NAME=rsvdev0$f
    ping -c 4 $MACHINE_NAME 2>&1 >/dev/null;
    if [ $?  -eq 0 ]; then
        echo "connecting with $MACHINE_NAME ...";
        ssh -q -t -X -Y \
            -o "TCPKeepAlive=yes" \
            -o "ServerAliveInterval=90" \
            -o "ServerAliveCountMax=10" \
            -o "ForwardX11=yes" \
            -o StrictHostKeyChecking=no \
            $MACHINE_NAME \
            "tmux attach -d -t ${1:main}";

        if [ $? -eq 0 ]; then
            NEW_SESSION=0;
        fi
    fi;
done

if [ $NEW_SESSION -eq 1 ]; then
    tmux new -s ${1:-main}
fi
