#!/usr/bin/expect -f
set timeout -1

set installpath [lindex $argv 0];

spawn $installpath/install


expect "Do you wish to continue?"
send "y\n"

expect "Is this host the primary server?"
send "y\n"

expect "Are you currently performing a disaster recovery of a primary server?"
send "n\n"

expect "Enter the name of the service user account to be used to start most of the daemons:"
send "nbsvc\n"

expect "Do you want to install NetBackup IT Analytics Data Collector?"
send "n\n"

expect "Do you want to install NetBackup and Media Manager files?"
send "y\n"

expect "Java GUI option"
send "2\n"

expect "Are the license files downloaded from the Veritas licensing portal?"
send "n\n"

expect "Do you want to use a NetBackup evaluation license"
send "y\n"

expect "NetBackup server name of this machine?"
send "y\n"

expect "Do you want to add any media servers now?"
send "n\n"

expect "so backups and restores can be initiated?"
send "y\n"

