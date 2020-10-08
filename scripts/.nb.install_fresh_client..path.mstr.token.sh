#!/usr/bin/expect -f
set timeout -1

set installpath [lindex $argv 0];
set mastersvr [lindex $argv 1];
set tokenvalue [lindex $argv 2];

spawn $installpath/install

expect "Do you wish to continue?"
send "y\n"

expect "Do you want to install the NetBackup client software for this client?"
send "y\n"

expect "Enter the name of the NetBackup master server"
send "$mastersvr\n"

expect "name of the NetBackup client?"
send "y\n"

expect "Is this correct?"
send "y\n"

#expect "Is it OK to install in /usr/openv?"
#send "y\n"

expect "Enter the authorization token for $mastersvr or q to skip:"
send "$tokenvalue\n"

expect eof
