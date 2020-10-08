#!/bin/bash

RESPONSE_FILE_LOC='/tmp/nb.response.file.nbsvc'

if [ -f $RESPONSE_FILE_LOC ]; then
    rm -f $RESPONSE_FILE_LOC
fi

if [ -z "$1" ]; then
    echo "Please pass the key as argument"
    exit  1
fi

KEY=$1

cat <<EOF >>$RESPONSE_FILE_LOC
y
y
n
nbsvc
/root/nbdata/veritas_customer_registration_key.json
y
y
$KEY
n
y
n
y
NONE
EOF

echo "Response file loc: $RESPONSE_FILE_LOC"
echo "scp ${USER}@${SCP_HOSTNAME}:${RESPONSE_FILE_LOC} /tmp"
