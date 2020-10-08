#!/usr/bin/expect -f
set timeout -1

set installpath [lindex $argv 0];
set installkey [lindex $argv 1];

spawn $installpath/install

expect "Do you wish to continue?"
send "y\n"

expect "Is this host the master server?"
send "y\n"

expect "Are you currently performing a disaster recovery of a master server?"
send "n\n"

#expect "Enter the name of the service user account to be used to start most of the daemons:"
#send "nbsvc\n"

expect "file, or enter q to quit the install script."
send "/root/nbdata/veritas_customer_registration_key.json\n"

expect "Do you want to install NetBackup and Media Manager files?"
send "y\n"

#expect "Is it OK to install in /usr/openv?"
#send "y\n"

expect "Enter license key: "
send "$installkey\n"

expect "Do you want to add additional license keys now?"
send "n\n"

expect "NetBackup server name of this machine?"
send "y\n"

expect "Do you want to add any media servers now?"
send "n\n"

expect "so backups and restores can be initiated?"
send "y\n"

expect "Enter the OpsCenter server (default: NONE):"
send "\n"
