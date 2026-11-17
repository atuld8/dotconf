#!/usr/bin/env python3
import os
import sys
import argparse
from tabulate import tabulate
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jira_api import load_config, user_search, format_user_row

cfg = load_config()

# Jira credentials and URL
JIRA_PROJECT_KEY    = os.getenv('JIRA_PROJECT_KEY')

parser = argparse.ArgumentParser(description='Get Jira user name details.')
parser.add_argument('jira_user_str', type=str, help='The user string of the Jira')

args = parser.parse_args()
print(f"[CMD] {' '.join(sys.argv)}", file=sys.stderr)
JIRA_ASSIGNEE_NAME      = args.jira_user_str

# Search users (Cloud: query=, Server: username=)
try:
    users = user_search(JIRA_ASSIGNEE_NAME)
except (RuntimeError, ValueError) as e:
    print(f'Failed to retrive user data for user string {JIRA_ASSIGNEE_NAME}: {e}')
    sys.exit(1)

if users:
    print(f"\n\nUser ID (accountId) for {JIRA_ASSIGNEE_NAME}")
    table = [format_user_row(user) for user in users]
    id_header = 'AccountId' if cfg.is_cloud else 'Key'
    print(tabulate(table, headers=[id_header, 'Name', 'Email-Address']))
else:
    print(f"No users found for query {JIRA_ASSIGNEE_NAME}")
