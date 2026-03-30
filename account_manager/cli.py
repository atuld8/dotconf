#!/usr/bin/env python3
"""
Command-line interface for Account Manager
"""

import os
import sys
from .models import AccountManager, DatabaseLockedError
from .reports import ReportGenerator
from .io_utils import IOUtils
from .esql_integration import EsqlExecutor
from .fi_validator import FIValidator
from .jira_client import JiraClient, MockJiraClient
from .account_populator import AutoPopulateStrategy
from .euserls_integration import EuserlsUpdater
from .jira_integration import JiraIdUpdater
from .etrack_integration import EtrackExecutor, MockEtrackExecutor
import re


def _fi_sort_key(fi_id):
    """Extract numeric part from FI-<digits> for proper numeric sorting.

    Examples:
        FI-45 -> 45
        FI-123 -> 123
        FI-2345 -> 2345
    """
    match = re.search(r'FI-(\d+)', fi_id)
    return int(match.group(1)) if match else 0


def _sort_fi_ids(fi_ids):
    """Sort FI IDs numerically by their numeric part."""
    return sorted(fi_ids, key=_fi_sort_key)


def _sort_fi_items(items):
    """Sort dict items where keys are FI IDs, numerically by FI number."""
    return sorted(items, key=lambda x: _fi_sort_key(x[0]))


def print_usage(command=None):
    """Print usage information"""

    if command == 'add':
        print("""
Add Account
===========
Add a new account to the database.

Usage:
    python3 -m account_manager.cli add <etrack_user_id>

Arguments:
    etrack_user_id    Username in etrack system (e.g., john_doe)

Examples:
    python3 -m account_manager.cli add john_doe

Note: This creates minimal account with just etrack_user_id.
      Use 'update' command to fill in other fields.
""")

    elif command == 'update':
        print("""
Update Account
==============
Update existing account fields.

Usage:
    python3 -m account_manager.cli update <etrack_user_id> [field=value ...]

Arguments:
    etrack_user_id    Account to update

Fields (optional):
    first_name=<value>        First name
    last_name=<value>         Last name
    jira_account=<value>      Jira username
    veritas_email=<value>     Veritas email address
    cohesity_email=<value>    Cohesity email address
    community_account=<value> Community account name
    manual_verified=<status>  Verification status:
                              yes, no, pending, invalid, departed,
                              duplicate, suspended, external
    notes=<value>             Free-form notes

Examples:
    # Interactive mode (prompts for each field)
    python3 -m account_manager.cli update john_doe

    # Direct update
    python3 -m account_manager.cli update john_doe jira_account=john.doe

    # Multiple fields at once
    python3 -m account_manager.cli update john_doe \\
        jira_account=john.doe \\
        veritas_email=john.doe@vcompany.com \\
        cohesity_email=john.doe@ccompany.com \\
        community_account=john.doe

    # Clear a field by setting empty value
    python3 -m account_manager.cli update john_doe jira_account=
""")

    elif command == 'list':
        print("""
List Accounts
=============
Display accounts in various formats.

Usage:
    python3 -m account_manager.cli list                  # All accounts (brief)
    python3 -m account_manager.cli list-incomplete       # Only incomplete accounts
    python3 -m account_manager.cli list-pending-verify   # Complete but pending verification
                                                         # (shows 'no' and 'pending' status only)

Examples:
    python3 -m account_manager.cli list
    python3 -m account_manager.cli list-incomplete
    python3 -m account_manager.cli list-pending-verify
""")

    elif command == 'report':
        print("""
Generate Reports
================
Generate various reports about accounts.

Usage:
    python3 -m account_manager.cli report [type] [options]

Report Types:
    full            Complete details of all accounts
    summary         Statistics and summary
    missing-fields  Accounts with incomplete data
    verification    Breakdown by verification status
    table           Formatted table view
    compact         Compact table format
    markdown        Markdown-formatted table

Options:
    --show-notes    Include notes column in output (for table/compact/markdown/full)

Examples:
    python3 -m account_manager.cli report summary
    python3 -m account_manager.cli report table
    python3 -m account_manager.cli report table --show-notes
    python3 -m account_manager.cli report missing-fields
""")

    elif command == 'validate-fi':
        print("""
Validate FI Assignees
=====================
Validate that FI tickets in Jira are assigned to the correct etrack assignee.

Usage:
    python3 -m account_manager.cli validate-fi <query_name> [options]
    python3 -m account_manager.cli validate-fi --incident=<incident_no> [options]
    python3 -m account_manager.cli validate-fi --fi=<fi_id> [options]
    cat file | python3 -m account_manager.cli validate-fi --incident=- [options]
    cat file | python3 -m account_manager.cli validate-fi --fi=- [options]

Arguments:
    query_name    Name of esql query to execute (e.g., RptTerm_Open_SRs_With_Ext_Ref_FI)
    --incident=   Incident number(s) to validate (comma-separated, or - for stdin)
    --fi=         FI ID(s) to validate (e.g., FI-59131, 59131, or - for stdin)

Validation Logic:
    The esql query returns: incident_no | etrack_assignee | who_added_fi | FI_ids

    For each record:
    1. Look up etrack_assignee's jira_account from the database
    2. Fetch actual Jira assignee for each FI from Jira API
    3. Compare: FI's Jira assignee should match etrack_assignee's jira_account

    Example:
      - Etrack 1234567 assigned to: user_one
      - user_one's jira_account in DB: user.one
      - FI-10001 Jira assignee: user.two
      - Result: X MISMATCH (should be user.one, not user.two)

Options:

  Input / Source:
    --incident=<no>          Validate incident(s) by number (comma-separated, or - for stdin)
    --fi=<id>                Validate FI(s) by ID (e.g. FI-59131, comma-separated, or -)
    --all-types              Include all incident types (default: SERVICE_REQUEST only)
    --perform-sr-type-check  With query: filter to SERVICE_REQUEST only (default: trust query)

  User Handling:
    --auto-add               Auto-add missing users with minimal data (etrack_user_id only)
    --interactive            Prompt to confirm data for each new user
    --fail-on-unknown        Fail immediately when unknown user found

  Assignee Validation:
    --report                 Generate reassignment report without fixing
    --report-from=<user>     Report only FIs currently assigned to <user>
    --fix                    Fix mismatched FI assignments (verified accounts only)
    --fix-from=<user>        Fix only FIs currently assigned to <user> (implies --fix)
    --fix-interactive        Prompt (y/n/q) before each fix
    --dry-run                Preview changes without applying
    --skip-fi=<ids>          Skip specific FIs when fixing (comma-separated)
    --show-conflicts         Show FIs linked to multiple incidents with different assignees
    --table                  With --show-conflicts: display in table format

  Severity:
    --report-severity        Compare etrack severity against linked FI Case Priority
    --fix-severity           Update etrack severity from linked FI Case Priority
    --format=<fmt>           Output format for --report-severity (default: text)
                               text    Full report with narrative and detail blocks
                               table   Aligned table of all records (no narrative)
                               csv     CSV, one row per incident
                               json    JSON object with summary + records array
    --exclude-severity=<items> Exclude status items from --report-severity output
                               Options: matched, mismatched, conflict, missing_case_priority,
                               missing_etrack_severity, error (comma-separated)
    --severity-transition=<rules>
                                 Filter --report-severity/--fix-severity by transitions (comma-separated)
                                                             to1     Allow only 2/3/4 -> 1
                                                             from1   Allow only 1 -> 2/3/4
                                                             raise   Allow only higher urgency changes (e.g., 4->2, 3->1)
                                                             lower   Allow only lower urgency changes (e.g., 1->2, 2->4)
                                                             X->Y    Allow explicit transitions (e.g., 2->1,1->3)

  General:
    --skip-details           Suppress per-record detail blocks
                             (applies to --report-severity text, --show-conflicts, --report)
    --mock                   Use mock Jira/Etrack clients (no API calls, for testing)

  Severity Mapping:  P1->1  P2->2  P3->3  P4->4
  Conflict Rule:     Multiple FI priorities -> highest priority wins (P1+P3 => 1)

Examples:
    # Basic validation (warns about missing users and mismatches)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI

    # Validate single or multiple incidents
    python3 -m account_manager.cli validate-fi --incident=1234568
    python3 -m account_manager.cli validate-fi --incident=1234568,1234569

    # Validate incidents from stdin (one per line or comma-separated)
    cat incidents.txt | python3 -m account_manager.cli validate-fi --incident=-
    echo "1234568,1234569" | python3 -m account_manager.cli validate-fi --incident=-

    # Validate single or multiple FIs
    python3 -m account_manager.cli validate-fi --fi=FI-59131
    python3 -m account_manager.cli validate-fi --fi=FI-59131,FI-59132,FI-59133

    # Validate FIs from stdin (one per line or comma-separated)
    cat fi_list.txt | python3 -m account_manager.cli validate-fi --fi=-

    # Auto-add missing users (minimal data)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

    # Testing without Jira connection
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --mock

    # Fix mismatched FI assignments (updates Jira assignee for verified accounts)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix

    # Preview fixes without applying (dry-run)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix --dry-run

    # Fix only FIs currently assigned to manager (e.g., reassign from manager to engineer)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix-from=manager.name

    # Interactive fix (prompt for each)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix --fix-interactive

    # Show FIs linked to multiple incidents with different assignees
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --show-conflicts

    # Show conflicts in table format
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --show-conflicts --table

    # Fix incident(s)
    python3 -m account_manager.cli validate-fi --incident=1234568 --fix

    # Fix incident(s) (dry-run)
    python3 -m account_manager.cli validate-fi --incident=1234568 --fix --dry-run

    # Fix FI(s)
    python3 -m account_manager.cli validate-fi --fi=FI-59131 --fix

    # Include all incident types (--fi/--incident default to SERVICE_REQUEST only)
    python3 -m account_manager.cli validate-fi --fi=FI-59131 --all-types
    python3 -m account_manager.cli validate-fi --incident=1234568 --all-types

    # Filter query results to SERVICE_REQUEST only
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --perform-sr-type-check

    # Compact output for large datasets
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report --skip-details

    # Report etrack severity mismatches from linked FI Case Priority values
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report-severity

    # Fix etrack severity for selected incidents (dry-run)
    python3 -m account_manager.cli validate-fi --incident=1234568,1234569 --fix-severity --dry-run

    # Validate severity for selected FI IDs
    python3 -m account_manager.cli validate-fi --fi=FI-59131,FI-59132 --report-severity

    # Severity report as CSV (pipe to file)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report-severity --format=csv > severity.csv

    # Severity report as JSON
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report-severity --format=json

    # Severity report as aligned table (no narrative)
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report-severity --format=table

    # Fix only transitions from 2/3/4 -> 1
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix-severity --severity-transition=to1

    # Fix only 1 -> lower priority transitions, plus explicit 2 -> 1
    python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix-severity --severity-transition=from1,2->1

Type Filtering:
    - For --fi/--incident: Defaults to SERVICE_REQUEST only. Use --all-types for all.
    - For query-based: Trusts query results. Use --perform-sr-type-check to filter.

Workflow:
    1. Run validation to see mismatches and unknown users
    2. Add missing users: --auto-add or manually
    3. Update user details: update-emails, update-jira-ids
    4. Re-run validation to confirm all matches
""")

    elif command == 'import':
        print("""
Import from CSV
===============
Import account data from CSV file.

Usage:
    python3 -m account_manager.cli import <file> [mode] [--allow-empty]

Arguments:
    file    CSV file path

Modes:
    skip    Skip existing accounts (DEFAULT)
    update  Update existing accounts with non-empty values
    fail    Fail if account exists

Options:
    --allow-empty    Empty CSV values will clear existing data
                     Without this flag, only non-empty values update fields

CSV Format:
    etrack_user_id,first_name,last_name,veritas_email,cohesity_email,community_account,jira_account,manual_verified,notes
    john_doe,John,Doe,john.doe@vcompany.com,john.doe@ccompany.com,john.doe,JIRAUSER123,no,

Examples:
    # Import, skip existing accounts
    python3 -m account_manager.cli import accounts.csv

    # Update existing accounts (preserve fields not in CSV)
    python3 -m account_manager.cli import accounts.csv update

    # Update and allow empty values to clear fields
    python3 -m account_manager.cli import accounts.csv update --allow-empty
""")

    elif command == 'export-log':
        print("""
Export Action Log
=================
Export action log entries to CSV file.

Usage:
    python3 -m account_manager.cli export-log [file] [options]

Arguments:
    file    Output CSV file path (default: action_log_export.csv)

Options:
    --since=YYYY-MM-DD    Only export entries on or after this date
    --limit=N             Maximum number of entries to export

CSV Fields:
    id,action_type,target_type,target_id,old_value,new_value,status,details,created_at

Examples:
    # Export all action log entries
    python3 -m account_manager.cli export-log

    # Export to specific file
    python3 -m account_manager.cli export-log my_actions.csv

    # Export last 100 entries
    python3 -m account_manager.cli export-log --limit=100

    # Export entries since a date
    python3 -m account_manager.cli export-log --since=2026-01-01
""")

    elif command == 'import-log':
        print("""
Import Action Log
=================
Import action log entries from CSV file.

Usage:
    python3 -m account_manager.cli import-log <file>

Arguments:
    file    CSV file path

CSV Format (required fields):
    action_type    Type of action (e.g., add_account, fix_fi)

CSV Format (optional fields):
    target_type    Type of target (e.g., account, fi)
    target_id      ID of target
    old_value      Previous value
    new_value      New value
    status         success, failed, skipped, dry_run
    details        Additional details

Examples:
    python3 -m account_manager.cli import-log actions_backup.csv
""")

    elif command == 'update-emails':
        print("""
Update Veritas Emails (euserls)
===============================
Automatically update missing data using euserls command.

Usage:
    python3 -m account_manager.cli update-emails [options]

Options:
    --dry-run    Show what would be updated without making changes
    --verbose    Show detailed progress messages

Description:
    Scans all accounts and uses the euserls command to fetch:
    - veritas_email (from etrack system)
    - first_name and last_name (parsed from euserls output)
    - community_account (derived from veritas_email, e.g., John.Doe@vcompany.com -> John.Doe)

Examples:
    # Preview what will be updated
    python3 -m account_manager.cli update-emails --dry-run

    # Actually update the accounts
    python3 -m account_manager.cli update-emails

    # With detailed progress
    python3 -m account_manager.cli update-emails --verbose

Requirements:
    - euserls command available locally OR
    - RMTCMD_HOST environment variable set for SSH execution
""")

    elif command == 'fetch-email':
        print("""
Fetch Veritas Email (euserls)
=============================
Fetch Veritas email and names for a single user using euserls command.

Usage:
    python3 -m account_manager.cli fetch-email <etrack_user_id> [options]

Arguments:
    etrack_user_id    The etrack user ID to query

Options:
    --dry-run    Show the data without updating database

Description:
    Fetches from euserls and updates:
    - veritas_email
    - first_name and last_name (parsed from euserls output)
    - community_account (derived from veritas_email)

Examples:
    # Fetch and update
    python3 -m account_manager.cli fetch-email john_doe

    # Just preview
    python3 -m account_manager.cli fetch-email john_doe --dry-run
""")

    elif command == 'update-verified':
        print("""
Update Manual Verification Status
==================================
Mark an account as manually verified or not.

Usage:
    python3 -m account_manager.cli update-verified <etrack_user_id> <status>

Arguments:
    etrack_user_id    Account to update
    status            Verification status (one of):
                      - no        Not yet verified (default)
                      - yes       Verified and active
                      - pending   Verification in progress
                      - invalid   Verified but entry has incorrect data
                      - departed  Person left the organization
                      - duplicate Duplicate entry exists
                      - suspended Account temporarily inactive
                      - external  External contractor or vendor

Description:
    Sets the manual_verified field.
    - 'no' and 'pending': Account appears in list-pending-verify
    - 'yes': Account is verified and can be used for FI fixes
    - Other statuses: Account has been reviewed but is not active

Examples:
    # Mark as verified
    python3 -m account_manager.cli update-verified john_doe yes

    # Mark as not verified
    python3 -m account_manager.cli update-verified john_doe no

    # Mark as pending verification
    python3 -m account_manager.cli update-verified john_doe pending

    # Mark as departed (person left org)
    python3 -m account_manager.cli update-verified john_doe departed

    # Mark as invalid data
    python3 -m account_manager.cli update-verified john_doe invalid
""")

    elif command == 'update-notes':
        print("""
Update Account Notes
====================
Add or update notes for an account.

Usage:
    python3 -m account_manager.cli update-notes <etrack_user_id> <notes>
    python3 -m account_manager.cli update-notes <etrack_user_id> --clear

Arguments:
    etrack_user_id    Account to update
    notes            Notes text (can be multi-word)
    --clear          Clear existing notes

Description:
    Updates the notes field with free-form text.
    Can be used to store additional information, comments,
    or reminders about the account.

Examples:
    # Add notes
    python3 -m account_manager.cli update-notes john_doe "Needs verification"

    # Add multi-word notes
    python3 -m account_manager.cli update-notes john_doe This account requires special attention

    # Clear notes
    python3 -m account_manager.cli update-notes john_doe --clear
""")

    elif command == 'update-jira-ids':
        print("""
Update JIRA IDs
===============
Automatically update missing JIRA account IDs using first/last name search.

Usage:
    python3 -m account_manager.cli update-jira-ids [options]

Options:
    --dry-run    Show what would be updated without making changes
    --verbose    Show detailed progress messages
    --mock       Use mock JIRA client (for testing)

Description:
    Scans all accounts where:
    - first_name and last_name are present
    - jira_account is empty
    - manual_verified is 'no'

    Uses JIRA API to search for users by name and updates:
    - jira_account (JIRA display name)
    - cohesity_email (ONLY if it's a @cohesity.com domain)

Multiple Match Handling:
    When multiple JIRA users match, disambiguation is attempted using:
    1. Exact display name match + cohesity.com email (highest priority)
    2. Exact display name match only
    3. Email matches firstname.lastname@cohesity.com exactly

    CONFLICT BEHAVIOR: If there are multiple candidates at any priority level,
    the account is SKIPPED and reported as a conflict. You must update manually:
        python3 -m account_manager.cli update <etrack_user_id> jira_account=<value>

Output:
    - Successfully updated: accounts that were updated
    - Conflicts: accounts with multiple JIRA matches (need manual update)
    - Failed: accounts where no JIRA user was found

Examples:
    # Preview what will be updated
    python3 -m account_manager.cli update-jira-ids --dry-run

    # Actually update the accounts
    python3 -m account_manager.cli update-jira-ids

    # With detailed progress
    python3 -m account_manager.cli update-jira-ids --verbose

Requirements:
    Environment variables:
    - JIRA_SERVER_NAME: JIRA server hostname
    - JIRA_ACC_TOKEN: JIRA API token (Bearer token)
""")

    elif command == 'fetch-jira-id':
        print("""
Fetch JIRA ID
=============
Fetch JIRA account ID for a single user using first/last name search.

Usage:
    python3 -m account_manager.cli fetch-jira-id <etrack_user_id> [options]

Arguments:
    etrack_user_id    The etrack user ID to query

Options:
    --dry-run    Show the data without updating database
    --mock       Use mock JIRA client (for testing)

Description:
    Requires first_name and last_name to be set for the account.
    Fetches from JIRA and updates:
    - jira_account (JIRA display name)
    - cohesity_email (ONLY if it's a @cohesity.com domain)

    If multiple JIRA users match and cannot be disambiguated, shows
    all candidates and does NOT update. You must set manually:
        python3 -m account_manager.cli update <etrack_user_id> jira_account=<value>

Examples:
    # Fetch and update
    python3 -m account_manager.cli fetch-jira-id john_doe

    # Just preview
    python3 -m account_manager.cli fetch-jira-id john_doe --dry-run
""")

    elif command == 'auto-update':
        print("""
Auto-Update Account
====================
Automatically fetch and update all available account information.

Usage:
    python3 -m account_manager.cli auto-update <etrack_user_id> [options]

Arguments:
    etrack_user_id    The etrack user ID to update

Options:
    --dry-run    Show what would be updated without making changes
    --verbose    Show detailed progress information
    --mock       Use mock JIRA client (for testing)

Description:
    Performs the following steps in sequence:
    1. Fetch Veritas email, first_name, last_name via euserls
       (Also derives community_account from email)
    2. Fetch JIRA account ID using first/last name
       (Also fetches cohesity_email from JIRA profile)

    Stops if any step fails. Safe to re-run - skips fields already populated.

Examples:
    # Full auto-update
    python3 -m account_manager.cli auto-update john_doe

    # Preview changes without applying
    python3 -m account_manager.cli auto-update john_doe --dry-run

    # With detailed output
    python3 -m account_manager.cli auto-update john_doe --verbose

Equivalent to running:
    python3 -m account_manager.cli fetch-email john_doe
    python3 -m account_manager.cli fetch-jira-id john_doe
""")

    elif command == 'assign-etrack-fi':
        print("""
Assign Etrack and FI
====================
Assign an etrack to a user and update the linked FI in Jira.

Usage:
    python3 -m account_manager.cli assign-etrack-fi <etrack_number> <etrack_user_id> [options]

Arguments:
    etrack_number     Etrack incident number (e.g., 1234567)
    etrack_user_id    User to assign to (e.g., user_one)

Options:
    --dry-run    Show what would be done without making changes
    --mock       Use mock clients (for testing without API calls)
    --verbose    Show detailed debug information (helpful for troubleshooting)

Requirements:
    - etrack_user_id must exist in accounts database
    - Account must have jira_account set
    - Account must be verified (manual_verified = 'yes')
    - esql command available (locally or via RMTCMD_HOST)
    - eset command available for etrack reassignment
    - JIRA credentials configured for FI assignment

Workflow:
    1. Lookup etrack_user_id in database to get jira_account
    2. Verify account is marked as verified (manual_verified = 'yes')
    3. Query etrack for external_reference where ext_src in ('TOOLS_AGILE', 'JIRA')
    4. Extract linked FI ID(s) (e.g., FI-58985)
    5. If etrack not assigned to user -> reassign using 'eset -o'
    6. If FI not assigned to jira_account -> update Jira assignee

Examples:
    # Assign etrack 1234567 to user_one and update linked FI
    python3 -m account_manager.cli assign-etrack-fi 1234567 user_one

    # Preview what would be done
    python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --dry-run

    # Test mode (no actual API calls)
    python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --mock

Note:
    Only verified accounts can be used for assignment.
    To view account details before verifying:
    python3 -m account_manager.cli get <etrack_user_id>

    To verify an account:
    python3 -m account_manager.cli update-verified <etrack_user_id> yes
""")

    elif command == 'action-log':
        print("""
View Action Log
===============
View recent actions performed by the script.

Usage:
    python3 -m account_manager.cli action-log [options]

Options:
    --limit=N           Maximum entries to show (default: 50)
    --type=TYPE         Filter by action type
    --target=TYPE       Filter by target type (account, fi, etrack)
    --status=STATUS     Filter by status (success, failed, skipped, dry_run)
    --since=YYYY-MM-DD  Show only entries on or after date
    --detailed          Show detailed format instead of table

Action Types:
    add_account, update_account, delete_account, verify_account,
    fetch_email, fetch_jira_id, assign_fi, fix_fi, assign_etrack,
    validate_fi, import_accounts, export_accounts

Examples:
    # View last 50 actions (table format)
    python3 -m account_manager.cli action-log

    # View detailed format
    python3 -m account_manager.cli action-log --detailed

    # View failed actions only
    python3 -m account_manager.cli action-log --status=failed

    # View FI-related actions from today
    python3 -m account_manager.cli action-log --target=fi --since=$(date +%Y-%m-%d)

    # View recent fix attempts
    python3 -m account_manager.cli action-log --type=fix_fi --limit=20
""")

    elif command == 'action-summary':
        print("""
Action Summary
==============
View summary statistics of all actions.

Usage:
    python3 -m account_manager.cli action-summary [options]

Options:
    --since=YYYY-MM-DD  Show only entries on or after date
    --daily             Show daily activity breakdown (last 7 days)

Description:
    Shows counts of each action type grouped by status (success/failed/skipped).
    Useful for understanding script activity and identifying patterns.

Examples:
    # Overall summary
    python3 -m account_manager.cli action-summary

    # Summary for this month
    python3 -m account_manager.cli action-summary --since=$(date +%Y-%m-01)

    # Daily activity for the week
    python3 -m account_manager.cli action-summary --daily
""")

    elif command == 'action-history':
        print("""
Action History
==============
View history of actions for a specific target.

Usage:
    python3 -m account_manager.cli action-history <target_type> <target_id>

Arguments:
    target_type    Type: account, fi, etrack
    target_id      Identifier (etrack_user_id, FI-12345, 1234567)

Examples:
    # View all actions on account john_doe
    python3 -m account_manager.cli action-history account john_doe

    # View all actions on FI-58985
    python3 -m account_manager.cli action-history fi FI-58985

    # View all actions on etrack 1234567
    python3 -m account_manager.cli action-history etrack 1234567
""")

    elif command == 'action-clear':
        print("""
Clear Action Log
================
Clear old action log entries.

Usage:
    python3 -m account_manager.cli action-clear [options]

Options:
    --before=YYYY-MM-DD   Clear entries before this date
    --all                 Clear all entries (requires confirmation)

Examples:
    # Clear entries older than 30 days ago
    python3 -m account_manager.cli action-clear --before=$(date -v-30d +%Y-%m-%d)

    # Clear all entries (will prompt for confirmation)
    python3 -m account_manager.cli action-clear --all
""")

    elif command == 'lookup-etrack-emails':
        print("""
Lookup Emails
=============
Lookup Veritas/Cohesity emails for Etrack IDs, FI IDs, or usernames.

For each input, this command:
1. Resolves to etrack_user_id (via Etrack assignee lookup if needed)
2. Looks up the email address from the accounts database

Usage:
    python3 -m account_manager.cli lookup-etrack-emails [options]
    cat ids.txt | python3 -m account_manager.cli lookup-etrack-emails

Options:
    -f, --file=FILE      Read IDs from file (one per line)
    --input=TYPE         Input type: 'etrack' (default), 'fi', 'user'
    --email=TYPE         Email type: 'cohesity' (default) or 'veritas'
    --format=FMT         Output format: 'table' (default), 'csv', 'semi', 'simple'
    --include-missing    Include items where no email was found
    --verbose            Show lookup details

Input Types:
    etrack  - Etrack incident IDs (e.g., 123456) - looks up assignee
    fi      - Jira FI IDs (e.g., FI-58985) - looks up Etrack then assignee
    user    - Usernames directly (e.g., john_doe) - skips Etrack lookup

Output Formats:
    table   - Formatted table with headers
    csv     - Comma-separated values
    semi    - Semicolon-separated values (for Excel in some locales)
    simple  - Tab-separated ID and email only

Examples:
    # Etrack IDs from file
    python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt

    # FI IDs from stdin
    echo -e "FI-58985\nFI-59001" | python3 -m account_manager.cli lookup-etrack-emails --input=fi

    # Usernames directly
    python3 -m account_manager.cli lookup-etrack-emails -f users.txt --input=user

    # Get veritas emails in semicolon-separated format
    python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --email=veritas --format=semi

    # Include missing (no email found)
    python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --include-missing
""")

    elif command:
        print(f"No detailed help available for '{command}'")
        print("Run 'python3 -m account_manager.cli help' for all commands")

    else:
        # Main help screen
        print("""
================================================================================
                        ACCOUNT MANAGER CLI
                   Multi-Account Tracking and Validation
================================================================================

USAGE
    python3 -m account_manager.cli <command> [arguments] [options]
    python3 -m account_manager.cli help [command]    # Get help for specific command

ACCOUNT MANAGEMENT
    add <etrack_user_id>             Add new account (minimal - update later)
    update <etrack_user_id> [...]    Update account fields
    delete <etrack_user_id>          Delete account
    get <etrack_user_id>             Show account details
    update-verified <id> <status>    Update verification status
                                     (yes|no|pending|invalid|departed|...)
    update-notes <id> <notes>        Update notes field

    Type: help add, help update for detailed usage

VIEWING DATA
    list                             List all accounts (brief)
    list-incomplete                  List accounts with missing fields
    list-pending-verify              List complete accounts pending verification
    search <field=value>             Search accounts by field
    report [type]                    Generate reports (see help report)

    Report types: full, summary, missing-fields, table, compact, markdown,
                  verification

TRANSLATION
    translate <id> <field>           Convert between account identifiers

    Example: translate john_doe jira_account
    Fields: etrack_user_id, jira_account, veritas_email,
            cohesity_email, community_account

DATA IMPORT/EXPORT
    export [filename]                Export accounts to CSV
    import <file> [mode] [options]   Import accounts from CSV (see help import)
    export-log [file] [options]      Export action log to CSV (see help export-log)
    import-log <file>                Import action log from CSV (see help import-log)

    Modes: skip (default), update, fail
    Options: --allow-empty (empty values clear existing data)

FI VALIDATION (esql + Jira)
    validate-fi <query> [options]    Validate FI assignees (see help validate-fi)
    validate-fi --incident=<no>      Validate incident(s) (comma-separated or - for stdin)
    validate-fi --fi=<id>            Validate FI(s) (comma-separated or - for stdin)
    check-assignee <fi_id>           Check single FI assignee
    assign-etrack-fi <et> <user>     Assign etrack and linked FI to user
                                     (requires verified account)

    validate-fi options: --auto-add, --interactive, --mock, --fail-on-unknown,
                         --fix, --dry-run, --fix-interactive, --fix-from=USER,
                         --skip-fi=IDS, --incident=NUMBER, --fi=ID,
                         --all-types, --perform-sr-type-check, --skip-details,
                         --report-severity, --fix-severity, --format=FMT,
                         --severity-transition=RULES
    assign-etrack-fi options: --dry-run, --mock, --verbose

VERITAS EMAIL UPDATE (euserls)
    update-emails [options]          Update missing emails/names using euserls
    fetch-email <etrack_user_id>     Fetch data for single user

    Also fetches: first_name, last_name, community_account
    Options: --dry-run, --verbose

JIRA ID UPDATE
    update-jira-ids [options]        Update missing JIRA IDs using first/last name
    fetch-jira-id <etrack_user_id>   Fetch JIRA ID for single user

    Also fetches: cohesity_email (from JIRA)
    Options: --dry-run, --verbose, --mock

AUTO-UPDATE (Combined)
    auto-update <etrack_user_id>     Fetch email + JIRA ID in one step

    Combines: fetch-email + fetch-jira-id for a single user
    Options: --dry-run, --verbose, --mock

EMAIL LOOKUP (Batch)
    lookup-etrack-emails [options]   Lookup emails for Etrack IDs, FI IDs, or usernames

    Options: -f FILE, --input=TYPE (etrack|fi|user),
             --email=TYPE (cohesity|veritas),
             --format=FMT (table|csv|semi|simple),
             --include-missing, --verbose

OTHER
    demo                             Run interactive demo
    help [command]                   Show this help or command-specific help

ACTION LOGS
    action-log [options]             View recent actions
    action-summary [options]         View action statistics
    action-history <type> <id>       View history for specific target
    action-clear [--before=DATE]     Clear old action log entries

    Options: --limit=N, --type=TYPE, --status=STATUS, --since=YYYY-MM-DD

================================================================================

QUICK START

1. Add accounts manually:
   $ python3 -m account_manager.cli add john_doe
   $ python3 -m account_manager.cli update john_doe

2. Or discover from FI validation:
   $ python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add
   $ python3 -m account_manager.cli list-incomplete
   $ python3 -m account_manager.cli update john_doe

3. Or bulk import from CSV:
   $ python3 -m account_manager.cli import accounts.csv update

4. View and report:
   $ python3 -m account_manager.cli list
   $ python3 -m account_manager.cli report summary

================================================================================

COMMON WORKFLOWS

New User Workflow:
  validate-fi Query --auto-add  -> Discovers new users, adds etrack_user_id
  list-incomplete               -> Shows what needs updating
  export incomplete.csv         -> Export for bulk editing
  [Edit CSV with correct data]
  import incomplete.csv update  -> Import corrected data
  validate-fi Query             -> Re-validate

Translation Workflow:
  translate john_doe jira_account     -> Get Jira username
  translate john.doe@vcompany.com etrack_user_id  -> Get etrack ID

Search Workflow:
  search jira_account=john.doe        -> Find by Jira account
  search cohesity_email=cohesity.com  -> Find by email pattern

================================================================================

For detailed help on any command:
    python3 -m account_manager.cli help <command>

Examples:
    python3 -m account_manager.cli help validate-fi
    python3 -m account_manager.cli help import
    python3 -m account_manager.cli help update
    python3 -m account_manager.cli help auto-update
""")




def run_demo(db: AccountManager, report_gen: ReportGenerator):
    """Run interactive demo"""
    print("Account Manager - Demo Mode")
    print("=" * 60)

    # Add some sample data
    try:
        db.add_account(
            etrack_user_id="john_doe",
            veritas_email="john.doe@vcompany.com",
            cohesity_email="john.doe@ccompany.com",
            community_account="johndoe_community",
            jira_account="john.doe"
        )
        print("+ Added sample account: john_doe")
    except ValueError:
        print("* Sample account john_doe already exists")

    try:
        db.add_account(
            etrack_user_id="jane_smith",
            veritas_email="jane.smith@vcompany.com",
            cohesity_email="jane.smith@ccompany.com",
            jira_account="jane.smith"
        )
        print("+ Added sample account: jane_smith")
    except ValueError:
        print("* Sample account jane_smith already exists")

    print("\n" + "=" * 60)
    print("TRANSLATION EXAMPLES:")
    print("=" * 60)

    # Demonstrate translation
    jira = db.translate("john_doe", "jira_account")
    print(f"Etrack john_doe -> Jira: {jira}")

    cohesity = db.translate("john.doe@vcompany.com", "cohesity_email")
    print(f"Veritas Email -> Cohesity Email: {cohesity}")

    etrack = db.translate("jane.smith", "etrack_user_id")
    print(f"Jira jane.smith -> Etrack: {etrack}")

    print("\n" + "=" * 60)
    print("SEARCHING:")
    print("=" * 60)

    # Search example
    results = db.search_accounts(cohesity_email="cohesity")
    print(f"Found {len(results)} accounts with Cohesity email")

    print("\n" + "=" * 60)
    print("GENERATING REPORT:")
    print("=" * 60)

    # Generate report
    report = report_gen.generate_report('summary')
    print(report)


def main():
    """Main CLI entry point"""
    # Initialize components
    # Check ET_JR_ACCOUNTS_DB env var first, then fall back to module directory
    db_path = os.environ.get('ET_JR_ACCOUNTS_DB')
    if not db_path:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(module_dir, "accounts.db")
    db = AccountManager(db_path)
    report_gen = ReportGenerator(db)
    io_utils = IOUtils(db)

    if len(sys.argv) == 1:
        run_demo(db, report_gen)
        db.close()
        return

    command = sys.argv[1].lower()

    try:
        if command == 'demo':
            run_demo(db, report_gen)

        elif command == 'add':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('add')
                return
            if len(sys.argv) < 3:
                print("Usage: cli.py add <etrack_user_id>")
                print_usage()
                return
            etrack_user_id = sys.argv[2]
            try:
                db.add_account(etrack_user_id)
                db.log_action('add_account', 'account', etrack_user_id, status='success')
                print(f"+ Added account: {etrack_user_id}")
            except ValueError as e:
                db.log_action('add_account', 'account', etrack_user_id, status='failed', details=str(e))
                print(f"X {e}")

        elif command == 'update':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('update')
                return
            if len(sys.argv) < 3:
                print("Usage: cli.py update <etrack_user_id> [field=value ...]")
                return
            etrack_user_id = sys.argv[2]
            # Parse field=value pairs
            updates = {}
            allowed_fields = ['first_name', 'last_name', 'veritas_email', 'cohesity_email',
                             'community_account', 'jira_account', 'manual_verified', 'notes']

            # Validate etrack_user_id is not a field=value pair
            if '=' in etrack_user_id:
                field_part = etrack_user_id.split('=', 1)[0]
                if field_part in allowed_fields:
                    print(f"X Missing etrack_user_id. First argument looks like a field=value pair.")
                    print("Usage: cli.py update <etrack_user_id> [field=value ...]")
                    return

            # Check if account exists
            existing_account = db.get_account(etrack_user_id=etrack_user_id)
            if not existing_account:
                print(f"X Account not found: {etrack_user_id}")
                print(f"  Use 'add' command to create it first: cli.py add {etrack_user_id}")
                return

            invalid_fields = []
            for arg in sys.argv[3:]:
                if '=' in arg:
                    field, value = arg.split('=', 1)
                    if field in allowed_fields:
                        updates[field] = value
                    else:
                        invalid_fields.append(field)
            if invalid_fields:
                print(f"X Invalid field(s): {', '.join(invalid_fields)}")
                print(f"  Valid fields: {', '.join(allowed_fields)}")
                return
            if updates:
                # Get old values for logging
                old_vals = {k: existing_account.get(k) for k in updates.keys()}
                db.update_account(etrack_user_id, **updates)
                db.log_action('update_account', 'account', etrack_user_id,
                             old_value=str(old_vals), new_value=str(updates), status='success')
                print(f"+ Updated account: {etrack_user_id}")
            else:
                print("No updates provided")

        elif command == 'delete':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('delete')
                return
            if len(sys.argv) < 3:
                print("Usage: cli.py delete <etrack_user_id>")
                return
            etrack_user_id = sys.argv[2]
            if db.delete_account(etrack_user_id):
                db.log_action('delete_account', 'account', etrack_user_id, status='success')
                print(f"+ Deleted account: {etrack_user_id}")
            else:
                db.log_action('delete_account', 'account', etrack_user_id, status='failed', details='Account not found')
                print(f"X Account not found: {etrack_user_id}")

        elif command == 'get':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('get')
                return
            if len(sys.argv) < 3:
                print("Usage: cli.py get <etrack_user_id>")
                return
            etrack_user_id = sys.argv[2]
            account = db.get_account(etrack_user_id=etrack_user_id)
            if account:
                print(f"\nAccount: {etrack_user_id}")
                print(f"  First Name:        {account.get('first_name') or 'N/A'}")
                print(f"  Last Name:         {account.get('last_name') or 'N/A'}")
                print(f"  Veritas Email:     {account['veritas_email'] or 'N/A'}")
                print(f"  Cohesity Email:    {account['cohesity_email'] or 'N/A'}")
                print(f"  Community Account: {account['community_account'] or 'N/A'}")
                print(f"  Jira Account:      {account['jira_account'] or 'N/A'}")
                print(f"  Manual Verified:   {account.get('manual_verified', 'no')}")
                if account.get('notes'):
                    print(f"  Notes:             {account['notes']}")
            else:
                print(f"X Account not found: {etrack_user_id}")

        elif command == 'list':
            accounts = db.get_all_accounts()
            if accounts:
                print(f"\nTotal Accounts: {len(accounts)}\n")
                for acc in accounts:
                    jira = acc['jira_account'] or 'N/A'
                    email = acc['cohesity_email'] or acc['veritas_email'] or 'N/A'
                    print(f"{acc['etrack_user_id']:15} {jira:20} {email}")
            else:
                print("No accounts found")

        elif command == 'list-incomplete':
            # List accounts with missing fields
            accounts = db.get_all_accounts()
            incomplete = []
            skip_statuses = {'invalid', 'departed', 'suspended'}
            skip_statuses_text = ', '.join(sorted(skip_statuses))
            skipped_count = 0

            for acc in accounts:
                status = (acc.get('manual_verified') or 'no').strip().lower()
                if status in skip_statuses:
                    skipped_count += 1
                    continue

                missing = []
                if not acc.get('first_name'):
                    missing.append('first_name')
                if not acc.get('last_name'):
                    missing.append('last_name')
                if not acc['jira_account']:
                    missing.append('jira_account')
                if not acc['veritas_email']:
                    missing.append('veritas_email')
                if not acc['cohesity_email']:
                    missing.append('cohesity_email')
                if not acc['community_account']:
                    missing.append('community_account')

                if missing:
                    incomplete.append((acc, missing))

            if not incomplete:
                print("+ All accounts are complete!")
                print(f"\nNote: Skipped {skipped_count} account(s) with manual_verified in {skip_statuses_text}.")
            else:
                print(f"Found {len(incomplete)} incomplete accounts:\n")
                print("=" * 80)
                for acc, missing in incomplete:
                    print(f"\nEtrack User ID: {acc['etrack_user_id']}")
                    print(f"  Missing fields: {', '.join(missing)}")
                    print(f"  Current values:")
                    print(f"    First:     {acc.get('first_name') or '(empty)'}")
                    print(f"    Last:      {acc.get('last_name') or '(empty)'}")
                    print(f"    Jira:      {acc['jira_account'] or '(empty)'}")
                    print(f"    Veritas:   {acc['veritas_email'] or '(empty)'}")
                    print(f"    Cohesity:  {acc['cohesity_email'] or '(empty)'}")
                    print(f"    Community: {acc['community_account'] or '(empty)'}")
                    print(f"    Verified:  {acc.get('manual_verified', 'no')}")
                    if acc.get('notes'):
                        print(f"    Notes:     {acc['notes']}")
                    print(f"  To update: python3 -m account_manager.cli update {acc['etrack_user_id']}")
                print("\n" + "=" * 80)
                print(f"\nTotal incomplete: {len(incomplete)} / {len(accounts)}")
                print(f"Note: Skipped {skipped_count} account(s) with manual_verified in {skip_statuses_text}.")
                print(f"\nTo see details: python3 -m account_manager.cli report missing-fields")

        elif command == 'list-pending-verify':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('list')
                return
            # List accounts with all fields populated but manual_verified='no'
            accounts = db.get_all_accounts()
            pending = []

            for acc in accounts:
                # Check if all required fields are populated
                has_all_fields = (
                    acc.get('first_name') and
                    acc.get('last_name') and
                    acc.get('jira_account') and
                    acc.get('veritas_email') and
                    acc.get('cohesity_email') and
                    acc.get('community_account')
                )
                # Check if manual_verified is 'no' or 'pending' (needs verification)
                # Other statuses like 'invalid', 'departed', 'duplicate', etc. are already reviewed
                not_verified = acc.get('manual_verified', 'no') in ('no', 'pending')

                if has_all_fields and not_verified:
                    pending.append(acc)

            if not pending:
                print("+ No accounts pending verification!")
                print("  (All complete accounts have been manually verified)")
            else:
                print(f"Found {len(pending)} accounts pending verification:\n")
                print("=" * 80)
                for acc in pending:
                    print(f"\nEtrack User ID: {acc['etrack_user_id']}")
                    print(f"  First:     {acc.get('first_name')}")
                    print(f"  Last:      {acc.get('last_name')}")
                    print(f"  Jira:      {acc['jira_account']}")
                    print(f"  Veritas:   {acc['veritas_email']}")
                    print(f"  Cohesity:  {acc['cohesity_email']}")
                    print(f"  Community: {acc['community_account']}")
                    if acc.get('notes'):
                        print(f"  Notes:     {acc['notes']}")
                    print(f"  To verify: python3 -m account_manager.cli update-verified {acc['etrack_user_id']} yes")
                print("\n" + "=" * 80)
                print(f"\nTotal pending: {len(pending)} / {len(accounts)}")

        elif command == 'search':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('search')
                return
            if len(sys.argv) < 3:
                print("Usage: cli.py search <field=value>")
                return
            # Parse field=value
            search_params = {}
            for arg in sys.argv[2:]:
                if '=' in arg:
                    field, value = arg.split('=', 1)
                    search_params[field] = value
            results = db.search_accounts(**search_params)
            print(f"Found {len(results)} matching accounts:")
            for acc in results:
                print(f"  {acc['etrack_user_id']}: {acc['jira_account']}")

        elif command == 'translate':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('translate')
                return
            if len(sys.argv) < 4:
                print("Usage: cli.py translate <identifier> <return_field>")
                return
            identifier = sys.argv[2]
            return_field = sys.argv[3]
            result = db.translate(identifier, return_field)
            if result:
                print(result)
            else:
                print(f"X Not found: {identifier}")

        elif command == 'report':
            report_type = sys.argv[2] if len(sys.argv) > 2 else 'summary'
            show_notes = '--show-notes' in sys.argv

            # Handle help flag
            if report_type in ['-h', '--help']:
                print_usage('report')
                return

            # Remove --show-notes from report_type if it was captured
            if report_type == '--show-notes':
                report_type = 'summary'

            # Normalize underscore to dash for backward compatibility
            if report_type == 'missing_fields':
                report_type = 'missing-fields'

            # Validate report type
            valid_types = ['full', 'summary', 'missing-fields', 'table', 'compact', 'markdown', 'verification']
            if report_type not in valid_types:
                print(f"X Unknown report type: {report_type}")
                print(f"  Valid types: {', '.join(valid_types)}")
                print(f"  Use 'report -h' for help")
                return

            # Handle special compact and markdown reports
            if report_type == 'compact':
                print(report_gen.generate_compact_table(show_notes=show_notes))
            elif report_type == 'markdown':
                print(report_gen.generate_markdown_table(show_notes=show_notes))
            else:
                print(report_gen.generate_report(report_type, show_notes=show_notes))

        elif command == 'export':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('export')
                return
            filename = sys.argv[2] if len(sys.argv) > 2 else 'accounts_export.csv'
            io_utils.export_to_csv(filename)

        elif command == 'export-log':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('export-log')
                return
            # Parse options
            filename = 'action_log_export.csv'
            limit = None
            since = None
            for arg in sys.argv[2:]:
                if arg.startswith('--since='):
                    since = arg.split('=', 1)[1]
                elif arg.startswith('--limit='):
                    limit = int(arg.split('=', 1)[1])
                elif not arg.startswith('--'):
                    filename = arg
            io_utils.export_action_log(filename, limit=limit, since=since)

        elif command == 'import':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('import')
                return
            if len(sys.argv) < 3:
                print("Usage: python3 -m account_manager.cli import <csv_file> [conflict_mode] [--allow-empty]")
                print("  conflict_mode: skip (default), update, or fail")
                print("  --allow-empty: Empty CSV values will clear existing data")
                return
            filename = sys.argv[2]
            # Parse arguments
            allow_empty = '--allow-empty' in sys.argv
            remaining_args = [a for a in sys.argv[3:] if a != '--allow-empty']
            conflict_mode = remaining_args[0] if remaining_args else 'skip'
            io_utils.import_from_csv(filename, conflict_mode, allow_empty)

        elif command == 'import-log':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('import-log')
                return
            if len(sys.argv) < 3:
                print("Usage: python3 -m account_manager.cli import-log <csv_file>")
                return
            filename = sys.argv[2]
            io_utils.import_action_log(filename)

        elif command == 'validate-fi':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('validate-fi')
                return
            # Validate FI assignees from esql query
            if len(sys.argv) < 3:
                print("Usage: cli.py validate-fi <esql_query_name> [options]")
                print("       cli.py validate-fi --incident=<number> [options]")
                print("       cli.py validate-fi --fi=<fi_id> [options]")
                print("  Example: cli.py validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI")
                print("           cli.py validate-fi --incident=1234568,1234569")
                print("           cli.py validate-fi --fi=FI-59131,FI-59132")
                print("")
                print("Options:")
                print("")
                print("  Input / Source:")
                print("    --incident=<no>          Validate incident(s) (comma-separated or - for stdin)")
                print("    --fi=<id>                Validate FI(s) (comma-separated or - for stdin)")
                print("    --all-types              Include all incident types (default: SERVICE_REQUEST)")
                print("    --perform-sr-type-check  With query: filter to SERVICE_REQUEST only")
                print("")
                print("  User Handling:")
                print("    --auto-add               Auto-add missing users (etrack_user_id only)")
                print("    --interactive            Prompt to confirm data for each new user")
                print("    --fail-on-unknown        Fail immediately on unknown user")
                print("")
                print("  Assignee Validation:")
                print("    --report                 Generate reassignment report (no fixes)")
                print("    --report-from=<user>     Report only FIs assigned to <user>")
                print("    --fix                    Fix mismatched FI assignments (verified accounts only)")
                print("    --fix-from=<user>        Fix only FIs assigned to <user> (implies --fix)")
                print("    --fix-interactive        Prompt (y/n/q) before each fix")
                print("    --dry-run                Preview changes without applying")
                print("    --skip-fi=<ids>          Skip specific FIs when fixing (comma-separated)")
                print("    --show-conflicts         Show FIs linked to multiple incidents with different assignees")
                print("    --table                  With --show-conflicts: display in table format")
                print("")
                print("  Severity:")
                print("    --report-severity        Compare etrack severity to linked FI Case Priority")
                print("    --fix-severity           Update etrack severity from FI Case Priority")
                print("    --format=<fmt>           Output format: text|table|csv|json (default: text)")
                print("    --severity-transition=<rules>  Filter report/fix severity transitions")
                print("                               rules: to1, from1, raise, lower, X->Y (comma-separated)")
                print("")
                print("  General:")
                print("    --skip-details           Suppress per-record detail blocks")
                print("    --mock                   Use mock clients (no API calls)")
                print("")
                print("  Severity mapping: P1->1  P2->2  P3->3  P4->4")
                print("  Conflict rule:    multiple FI priorities -> highest wins (P1+P3 => 1)")
                return

            query_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None

            # Define valid options for validate-fi command
            valid_options = {
                '--mock', '--fix', '--dry-run', '--fix-interactive',
                '--report', '--report-severity',
                '--fix-severity', '--show-conflicts', '--table',
                '--auto-add', '--interactive', '--fail-on-unknown',
                '--all-types', '--perform-sr-type-check', '--skip-details'
            }
            valid_option_prefixes = {
                '--fix-from=', '--report-from=', '--skip-fi=', '--incident=', '--fi=', '--format=',
                '--severity-transition='
            }

            # Validate all arguments
            for arg in sys.argv[3:]:
                if arg.startswith('--'):
                    # Check if it's a valid option or valid prefix
                    is_valid = arg in valid_options or any(arg.startswith(p) for p in valid_option_prefixes)
                    if not is_valid:
                        print(f"X Error: Unknown option '{arg}'")
                        # Suggest similar options
                        similar = [opt for opt in valid_options if arg[2:6] in opt or opt[2:6] in arg]
                        if similar:
                            print(f"  Did you mean: {', '.join(sorted(similar))}?")
                        print(f"\nValid options:")
                        for opt in sorted(valid_options):
                            print(f"  {opt}")
                        for prefix in sorted(valid_option_prefixes):
                            print(f"  {prefix}<value>")
                        return

            use_mock = '--mock' in sys.argv
            fix_mismatches = '--fix' in sys.argv
            fix_dry_run = '--dry-run' in sys.argv
            fix_interactive = '--fix-interactive' in sys.argv
            generate_report = '--report' in sys.argv
            severity_report = '--report-severity' in sys.argv
            severity_fix = '--fix-severity' in sys.argv
            show_conflicts = '--show-conflicts' in sys.argv
            conflict_table = '--table' in sys.argv
            include_all_types = '--all-types' in sys.argv  # For --fi/--incident
            perform_sr_type_check = '--perform-sr-type-check' in sys.argv  # For query-based
            skip_details = '--skip-details' in sys.argv
            severity_mode = severity_report or severity_fix

            # Parse --format=<fmt>  (applies to --report-severity output)
            _valid_severity_formats = {'text', 'table', 'csv', 'json'}
            severity_fmt = 'text'
            for arg in sys.argv:
                if arg.startswith('--format='):
                    severity_fmt = arg.split('=', 1)[1].lower()
                    break
            if severity_fmt not in _valid_severity_formats:
                print(f"X Error: --format must be one of: {', '.join(sorted(_valid_severity_formats))}")
                print(f"  Got: {severity_fmt}")
                return

            # Parse --exclude-severity=<items>
            exclude_severity_items = set()
            valid_exclude_items = {'matched', 'mismatched', 'conflict', 'missing_case_priority', 'missing_etrack_severity', 'error'}
            for arg in sys.argv:
                if arg.startswith('--exclude-severity='):
                    exclude_raw = arg.split('=', 1)[1].strip()
                    exclude_tokens = [token.strip().lower() for token in exclude_raw.split(',') if token.strip()]
                    invalid_exclude = [t for t in exclude_tokens if t not in valid_exclude_items]
                    if invalid_exclude:
                        print(f"X Error: invalid --exclude-severity item(s): {', '.join(invalid_exclude)}")
                        print(f"  Valid options: {', '.join(sorted(valid_exclude_items))}")
                        return
                    exclude_severity_items = set(exclude_tokens)
                    break

            # Parse --severity-transition=<rules>
            severity_transition_raw = None
            for arg in sys.argv:
                if arg.startswith('--severity-transition='):
                    severity_transition_raw = arg.split('=', 1)[1].strip()
                    break

            severity_transition_explicit = set()
            severity_transition_to1 = False
            severity_transition_from1 = False
            severity_transition_raise = False
            severity_transition_lower = False

            if severity_transition_raw:
                transition_tokens = [token.strip().lower().replace(' ', '') for token in severity_transition_raw.split(',') if token.strip()]
                invalid_tokens = []
                for token in transition_tokens:
                    if token in ('to1', 'to-1', 'to_p1', 'to-p1'):
                        severity_transition_to1 = True
                    elif token in ('from1', 'from-1', 'from_p1', 'from-p1'):
                        severity_transition_from1 = True
                    elif token in ('raise', 'up', 'increase'):
                        severity_transition_raise = True
                    elif token in ('lower', 'down', 'decrease'):
                        severity_transition_lower = True
                    else:
                        transition_match = re.match(r'^([1-4])->([1-4])$', token)
                        if transition_match:
                            severity_transition_explicit.add((
                                int(transition_match.group(1)),
                                int(transition_match.group(2))
                            ))
                        else:
                            invalid_tokens.append(token)

                if invalid_tokens:
                    print("X Error: invalid --severity-transition rule(s): " + ', '.join(invalid_tokens))
                    print("  Accepted rules: to1, from1, raise, lower, X->Y")
                    print("  Example: --severity-transition=to1,1->3")
                    return

            # Parse --fix-from=<user>
            fix_from_user = None
            for arg in sys.argv:
                if arg.startswith('--fix-from='):
                    fix_from_user = arg.split('=', 1)[1]
                    fix_mismatches = True  # Implies --fix
                    break

            # Parse --report-from=<user>
            report_from_user = None
            for arg in sys.argv:
                if arg.startswith('--report-from='):
                    report_from_user = arg.split('=', 1)[1]
                    generate_report = True  # Implies --report
                    break

            # Parse --skip-fi=<ids>
            skip_fi_ids = set()
            for arg in sys.argv:
                if arg.startswith('--skip-fi='):
                    skip_fi_ids = set(arg.split('=', 1)[1].split(','))
                    break

            # Parse --incident=<number> or --incident=<no1,no2,...> or --incident=- (stdin)
            incident_nos = None
            for arg in sys.argv:
                if arg.startswith('--incident='):
                    inc_value = arg.split('=', 1)[1]
                    if inc_value == '-':
                        # Read incident numbers from stdin
                        import select
                        incident_nos = []
                        if select.select([sys.stdin], [], [], 0.0)[0]:
                            for line in sys.stdin:
                                line = line.strip()
                                if line:
                                    # Support comma-separated on each line too
                                    incident_nos.extend([inc.strip() for inc in line.split(',') if inc.strip()])
                        if not incident_nos:
                            print("X Error: No incident numbers provided via stdin")
                            return
                    else:
                        # Support comma-separated incident numbers
                        incident_nos = [inc.strip() for inc in inc_value.split(',') if inc.strip()]
                    break

            # Parse --fi=<id> or --fi=<id1,id2,...> or --fi=- (stdin)
            fi_ids = None
            for arg in sys.argv:
                if arg.startswith('--fi='):
                    fi_value = arg.split('=', 1)[1]
                    if fi_value == '-':
                        # Read FI IDs from stdin
                        import select
                        fi_ids = []
                        if select.select([sys.stdin], [], [], 0.0)[0]:
                            for line in sys.stdin:
                                line = line.strip()
                                if line:
                                    # Support comma-separated on each line too
                                    fi_ids.extend([fi.strip() for fi in line.split(',') if fi.strip()])
                        if not fi_ids:
                            print("X Error: No FI IDs provided via stdin")
                            return
                    else:
                        # Support comma-separated FI IDs
                        fi_ids = [fi.strip() for fi in fi_value.split(',') if fi.strip()]
                    break

            # Determine auto-populate strategy
            if '--auto-add' in sys.argv:
                auto_strategy = AutoPopulateStrategy.AUTO
            elif '--interactive' in sys.argv:
                auto_strategy = AutoPopulateStrategy.INTERACTIVE
            elif '--fail-on-unknown' in sys.argv:
                auto_strategy = AutoPopulateStrategy.FAIL
            else:
                auto_strategy = AutoPopulateStrategy.SKIP

            # Validate that we have either query_name, --incident, or --fi
            if not query_name and not incident_nos and not fi_ids:
                print("X Error: Must specify a query name, --incident=<number>, or --fi=<id>")
                print("\nUsage:")
                print("  python3 -m account_manager.cli validate-fi <query-name> [options]")
                print("  python3 -m account_manager.cli validate-fi --incident=<no1,no2,...> [options]")
                print("  python3 -m account_manager.cli validate-fi --fi=<fi-id> [options]")
                print("  python3 -m account_manager.cli validate-fi --fi=<fi1,fi2,...> [options]")
                return

            if fi_ids:
                # Normalize FI IDs for display
                fi_display_list = []
                for fi in fi_ids:
                    fi_display_list.append(fi if fi.startswith('FI-') else f'FI-{fi}')
                if len(fi_display_list) == 1:
                    print(f"Fetching by FI: {fi_display_list[0]}")
                else:
                    print(f"Fetching by FI: {len(fi_display_list)} FIs")
                    if not skip_details:
                        for fi_d in fi_display_list:
                            print(f"  - {fi_d}")
            elif incident_nos:
                if len(incident_nos) == 1:
                    print(f"Fetching incident: {incident_nos[0]}")
                else:
                    print(f"Fetching incidents: {len(incident_nos)} incidents")
                    if not skip_details:
                        for inc in incident_nos:
                            print(f"  - {inc}")
            else:
                print(f"Running esql query: {query_name}")
            print(f"Auto-populate strategy: {auto_strategy}")
            # Type filter info depends on mode
            if fi_ids or incident_nos:
                if not include_all_types:
                    print("Type filter: SERVICE_REQUEST only (use --all-types for all)")
                else:
                    print("Type filter: ALL incident types")
            else:
                # Query-based mode
                if perform_sr_type_check:
                    print("Type filter: SERVICE_REQUEST only (--perform-sr-type-check)")
                else:
                    print("Type filter: trusting query results (use --perform-sr-type-check to filter)")
            if fix_mismatches:
                mode_parts = ["ENABLED"]
                if fix_dry_run:
                    mode_parts.append("DRY-RUN")
                if fix_interactive:
                    mode_parts.append("INTERACTIVE")
                if fix_from_user:
                    mode_parts.append(f"FROM={fix_from_user}")
                if skip_fi_ids:
                    mode_parts.append(f"SKIP={','.join(skip_fi_ids)}")
                print(f"Fix mode: {' | '.join(mode_parts)}")
            if severity_mode:
                severity_parts = []
                if severity_report:
                    severity_parts.append("REPORT")
                if severity_fix:
                    severity_parts.append("FIX")
                if severity_fix and fix_dry_run:
                    severity_parts.append("DRY-RUN")
                if severity_fix and fix_interactive:
                    severity_parts.append("INTERACTIVE")
                if severity_mode and severity_transition_raw:
                    severity_parts.append(f"transition={severity_transition_raw}")
                severity_parts.append(f"format={severity_fmt}")
                if severity_fmt != 'text' and skip_details:
                    print("  Note: --skip-details is ignored for non-text formats")
                print(f"Severity mode: {' | '.join(severity_parts)}")
                print("Severity mapping: P1 -> 1, P2 -> 2, P3 -> 3, P4 -> 4")
                print("Severity conflict rule: highest FI Case Priority wins (P1 + P3 => 1)")

            def _severity_transition_matches(old_value, new_value):
                """Return True when old->new matches --severity-transition rules."""
                if not severity_transition_raw:
                    return True
                try:
                    old_int = int(old_value)
                    new_int = int(new_value)
                except (TypeError, ValueError):
                    return False

                if (old_int, new_int) in severity_transition_explicit:
                    return True
                if severity_transition_to1 and old_int in (2, 3, 4) and new_int == 1:
                    return True
                if severity_transition_from1 and old_int == 1 and new_int in (2, 3, 4):
                    return True
                if severity_transition_raise and old_int > new_int:
                    return True
                if severity_transition_lower and old_int < new_int:
                    return True
                return False
            print("=" * 60)

            # Execute esql query or fetch incident(s)/FI(s)
            executor = EsqlExecutor()
            if fi_ids:
                # Fetch records for each FI ID
                records = []
                for fi_id in fi_ids:
                    fi_records = executor.fetch_by_fi_id(fi_id, include_all_types=include_all_types)
                    records.extend(fi_records)
            elif incident_nos:
                # Use batch method for multiple incidents (more efficient)
                if len(incident_nos) > 1:
                    records = executor.fetch_incidents_batch(
                        incident_nos,
                        include_all_types=include_all_types,
                        verbose=not skip_details
                    )
                else:
                    # Single incident - use original method
                    records = executor.fetch_incident_by_id(incident_nos[0], include_all_types=include_all_types)
            else:
                records = executor.execute_and_parse(query_name)
                # For query-based: apply type filter if --perform-sr-type-check is set
                if perform_sr_type_check and records:
                    records = executor.filter_records_by_type(records, type_filter='SERVICE_REQUEST')

            if not records:
                if fi_ids:
                    if len(fi_ids) == 1:
                        fi_display = fi_ids[0] if fi_ids[0].startswith('FI-') else f'FI-{fi_ids[0]}'
                        print(f"X No records found for {fi_display}")
                    else:
                        print(f"X No records found for {len(fi_ids)} FIs")
                elif incident_nos:
                    if len(incident_nos) == 1:
                        print(f"X No FI records found for incident {incident_nos[0]}")
                    else:
                        print(f"X No FI records found for {len(incident_nos)} incidents")
                else:
                    print("X No records found from esql query")
                return

            print(f"+ Found {len(records)} FI records")
            print()

            # Always compute conflicts: FIs linked to multiple incidents with different assignees
            # Build mapping: FI_ID -> [(incident_no, etrack_user_id, who_added_fi)]
            fi_to_incidents = {}
            for record in records:
                for fi_id in record.fi_ids:
                    if fi_id not in fi_to_incidents:
                        fi_to_incidents[fi_id] = []
                    fi_to_incidents[fi_id].append({
                        'incident_no': record.incident_no,
                        'etrack_user_id': record.etrack_user_id,
                        'who_added_fi': record.who_added_fi
                    })

            # Find FIs with multiple incidents AND different assignees
            conflicts = {}
            for fi_id, incidents in fi_to_incidents.items():
                if len(incidents) > 1:
                    # Check if assignees are different
                    assignees = set(inc['etrack_user_id'] for inc in incidents)
                    if len(assignees) > 1:
                        conflicts[fi_id] = incidents

            # Show detailed conflicts if --show-conflicts
            if show_conflicts:
                if not conflicts:
                    print("+ No conflicts found - all FIs have consistent assignees")
                    print(f"\n  Total FIs analyzed: {len(fi_to_incidents)}")
                    multi_incident_fis = [fi for fi, incs in fi_to_incidents.items() if len(incs) > 1]
                    print(f"  FIs linked to multiple incidents (same assignee): {len(multi_incident_fis)}")
                    return

                if skip_details:
                    print("=" * 80)
                    print(f"FI CONFLICTS FOUND: {len(conflicts)}")
                    print("=" * 80)
                    print("Detailed conflict rows suppressed by --skip-details")
                    print("Remove --skip-details to view full conflict details.")
                    return

                print("=" * 80)
                print(f"FI CONFLICTS FOUND: {len(conflicts)}")
                print("=" * 80)
                print("These FIs are linked to multiple incidents with DIFFERENT assignees.")
                print("The --fix option cannot automatically resolve these - manual review needed.")
                print()

                if conflict_table:
                    # Table format
                    col_fi = 12
                    col_incident = 10
                    col_etrack = 22
                    col_jira = 24
                    col_added = 18

                    # Build table rows
                    table_rows = []
                    for fi_id, incidents in _sort_fi_items(conflicts.items()):
                        # Get expected Jira IDs from DB for each assignee
                        assignee_jira_map = {}
                        for inc in incidents:
                            etrack_id = inc['etrack_user_id']
                            if etrack_id not in assignee_jira_map:
                                jira_acc = db.translate(etrack_id, 'jira_account')
                                assignee_jira_map[etrack_id] = jira_acc or '(not in DB)'

                        for idx, inc in enumerate(incidents):
                            etrack_id = inc['etrack_user_id']
                            jira_acc = assignee_jira_map[etrack_id]
                            # Only show FI ID on first row for this conflict
                            fi_display = fi_id if idx == 0 else ''
                            table_rows.append((fi_display, inc['incident_no'], etrack_id, jira_acc, inc['who_added_fi']))

                    # Print table
                    separator = "+" + "-" * (col_fi + 2) + "+" + "-" * (col_incident + 2) + "+" + \
                               "-" * (col_etrack + 2) + "+" + "-" * (col_jira + 2) + "+" + "-" * (col_added + 2) + "+"

                    header = f"| {'FI ID':<{col_fi}} | {'Incident':<{col_incident}} | " \
                            f"{'Etrack Assignee':<{col_etrack}} | {'Expected Jira':<{col_jira}} | " \
                            f"{'Added By':<{col_added}} |"

                    print(separator)
                    print(header)
                    print(separator)

                    prev_fi = None
                    for fi_id, incident, etrack, jira, added in table_rows:
                        # Add separator between different FIs
                        if prev_fi is not None and fi_id != '' and fi_id != prev_fi:
                            print(separator)
                        prev_fi = fi_id if fi_id else prev_fi

                        row = f"| {fi_id[:col_fi]:<{col_fi}} | {incident[:col_incident]:<{col_incident}} | " \
                              f"{etrack[:col_etrack]:<{col_etrack}} | {jira[:col_jira]:<{col_jira}} | " \
                              f"{added[:col_added]:<{col_added}} |"
                        print(row)

                    print(separator)
                else:
                    # Detailed format (original)
                    for fi_id, incidents in _sort_fi_items(conflicts.items()):
                        print(f"\n{fi_id}")
                        print("-" * 40)

                        # Get expected Jira IDs from DB for each assignee
                        assignee_jira_map = {}
                        for inc in incidents:
                            etrack_id = inc['etrack_user_id']
                            if etrack_id not in assignee_jira_map:
                                jira_acc = db.translate(etrack_id, 'jira_account')
                                assignee_jira_map[etrack_id] = jira_acc or '(not in DB)'

                        for inc in incidents:
                            etrack_id = inc['etrack_user_id']
                            jira_acc = assignee_jira_map[etrack_id]
                            print(f"  Incident: {inc['incident_no']}")
                            print(f"    Etrack Assignee: {etrack_id}")
                            print(f"    Expected Jira:   {jira_acc}")
                            print(f"    Added by:        {inc['who_added_fi']}")
                            print()

                print("=" * 80)
                print(f"SUMMARY: {len(conflicts)} FIs with conflicting assignees")
                print("=" * 80)
                print("\nRecommendations:")
                print("  1. Review each FI to determine correct owner")
                print("  2. Use --skip-fi=<ids> to exclude these from --fix")
                print("  3. Manually assign FIs in Jira after review")

                # Generate skip-fi option with all conflicting FIs
                conflict_fi_list = ','.join(_sort_fi_ids(conflicts.keys()))
                print(f"\nTo skip all conflicting FIs:")
                print(f"  --skip-fi={conflict_fi_list}")
                return

            # Initialize Jira client
            if use_mock:
                print("Using Mock Jira Client (no actual API calls)")
                jira_client = MockJiraClient()
            else:
                try:
                    jira_client = JiraClient()
                    if not jira_client.test_connection():
                        print("X Failed to connect to Jira")
                        return
                except Exception as e:
                    print(f"X Error initializing Jira client: {e}")
                    print("Tip: Use --mock flag to test without Jira connection")
                    return

            print()

            validator = FIValidator(db, jira_client, auto_populate_strategy=auto_strategy)
            run_assignee_validation = (
                fix_mismatches or generate_report or fix_from_user is not None or report_from_user is not None
                or not severity_mode
            )

            if severity_mode:
                if use_mock:
                    etrack_client = MockEtrackExecutor()
                else:
                    try:
                        etrack_client = EtrackExecutor()
                    except Exception as e:
                        print(f"X Error initializing Etrack client: {e}")
                        print("Tip: Use --mock to test severity validation without live etrack updates")
                        return

                print("Starting severity validation (this may take a while for large datasets)...")
                severity_results = validator.validate_severity_records(records, etrack_client)

                print("\n" + "=" * 60)
                print("SEVERITY VALIDATION RESULTS")
                print("=" * 60)
                severity_results_for_output = severity_results
                if severity_transition_raw:
                    severity_results_for_output = [
                        result for result in severity_results
                        if _severity_transition_matches(result.etrack_severity, result.expected_severity)
                    ]
                    filtered_out = len(severity_results) - len(severity_results_for_output)
                    print(
                        f"Applying severity transition filter ({severity_transition_raw}): "
                        f"{len(severity_results_for_output)} kept, {filtered_out} filtered out"
                    )
                print(validator.generate_severity_report(severity_results_for_output, fmt=severity_fmt, include_details=not skip_details, exclude_items=exclude_severity_items))

                severity_actionable = validator.get_severity_mismatches(severity_results)

                if severity_fix:
                    print("\n" + "=" * 60)
                    if fix_dry_run:
                        print("FIXING ETRACK SEVERITY (DRY-RUN - no changes will be made)")
                    else:
                        print("FIXING ETRACK SEVERITY")
                    print("=" * 60)

                    severity_fixed_success = []
                    severity_fixed_failed = []
                    severity_fixed_skipped = []

                    for severity_result in severity_actionable:
                        skip_fi_matches = [
                            fi_info.fi_id for fi_info in severity_result.severity_fis
                            if fi_info.fi_id in skip_fi_ids
                        ]
                        if skip_fi_matches:
                            severity_fixed_skipped.append({
                                'incident_no': severity_result.incident_no,
                                'reason': f"Excluded via --skip-fi ({','.join(_sort_fi_ids(skip_fi_matches))})"
                            })
                            continue

                        if severity_result.status in ('missing_case_priority', 'error'):
                            severity_fixed_failed.append({
                                'incident_no': severity_result.incident_no,
                                'reason': severity_result.error or 'Linked FIs do not have usable Case Priority values',
                                'solution': 'Populate the Jira Case Priority field on the linked FI tickets and retry'
                            })
                            continue

                        if not severity_result.expected_severity:
                            severity_fixed_failed.append({
                                'incident_no': severity_result.incident_no,
                                'reason': 'Unable to determine target severity from linked FIs',
                                'solution': 'Verify the linked FIs have Case Priority values P1-P4'
                            })
                            continue

                        if severity_transition_raw:
                            old_severity = severity_result.etrack_severity
                            new_severity = severity_result.expected_severity
                            if not _severity_transition_matches(old_severity, new_severity):
                                old_display = old_severity if old_severity is not None else 'N/A'
                                new_display = new_severity if new_severity is not None else 'N/A'
                                severity_fixed_skipped.append({
                                    'incident_no': severity_result.incident_no,
                                    'reason': f"Transition {old_display}->{new_display} excluded by --severity-transition={severity_transition_raw}"
                                })
                                continue

                        if fix_interactive and not fix_dry_run:
                            print(
                                f"\n  Incident {severity_result.incident_no}: "
                                f"{severity_result.etrack_severity or 'N/A'} -> {severity_result.expected_severity} "
                                f"(Case Priority {severity_result.dominant_case_priority or 'N/A'})"
                            )
                            response = input("  Fix this severity? (y/n/q to quit): ").strip().lower()
                            if response == 'q':
                                print("  Stopping severity fix operation.")
                                break
                            if response != 'y':
                                severity_fixed_skipped.append({
                                    'incident_no': severity_result.incident_no,
                                    'reason': 'User declined'
                                })
                                continue

                        try:
                            success = etrack_client.update_severity(
                                severity_result.incident_no,
                                severity_result.expected_severity,
                                dry_run=fix_dry_run
                            )
                            if success:
                                severity_fixed_success.append({
                                    'incident_no': severity_result.incident_no,
                                    'old_severity': severity_result.etrack_severity,
                                    'new_severity': severity_result.expected_severity,
                                    'case_priority': severity_result.dominant_case_priority,
                                })
                                db.log_action(
                                    'fix_etrack_severity',
                                    'etrack',
                                    severity_result.incident_no,
                                    old_value=severity_result.etrack_severity,
                                    new_value=severity_result.expected_severity,
                                    status='dry_run' if fix_dry_run else 'success',
                                    details=(
                                        f"case_priority={severity_result.dominant_case_priority}; "
                                        f"fi_ids={','.join(_sort_fi_ids([fi.fi_id for fi in severity_result.severity_fis]))}; "
                                        f"conflict={severity_result.has_priority_conflict}"
                                    )
                                )
                            else:
                                severity_fixed_failed.append({
                                    'incident_no': severity_result.incident_no,
                                    'reason': f"etrack update failed (target severity: {severity_result.expected_severity})",
                                    'solution': f"Run manually: eset -s {severity_result.expected_severity} {severity_result.incident_no}"
                                })
                                db.log_action(
                                    'fix_etrack_severity',
                                    'etrack',
                                    severity_result.incident_no,
                                    old_value=severity_result.etrack_severity,
                                    new_value=severity_result.expected_severity,
                                    status='failed',
                                    details='etrack severity update failed'
                                )
                        except Exception as e:
                            severity_fixed_failed.append({
                                'incident_no': severity_result.incident_no,
                                'reason': str(e),
                                'solution': f"Run manually: eset -s {severity_result.expected_severity} {severity_result.incident_no}"
                            })
                            db.log_action(
                                'fix_etrack_severity',
                                'etrack',
                                severity_result.incident_no,
                                old_value=severity_result.etrack_severity,
                                new_value=severity_result.expected_severity,
                                status='failed',
                                details=str(e)
                            )

                    print("\n" + "-" * 40)
                    if fix_dry_run:
                        print("SEVERITY FIX SUMMARY (DRY-RUN)")
                    else:
                        print("SEVERITY FIX SUMMARY")
                    print("-" * 40)

                    if severity_fixed_success:
                        label = "Would fix" if fix_dry_run else "Successfully fixed"
                        print(f"\n+ {label}: {len(severity_fixed_success)}")
                        for item in sorted(severity_fixed_success, key=lambda x: int(x['incident_no'])):
                            print(
                                f"  Incident {item['incident_no']}: "
                                f"{item['old_severity'] or 'N/A'} -> {item['new_severity']} "
                                f"(Case Priority {item['case_priority'] or 'N/A'})"
                            )

                    if severity_fixed_skipped:
                        print(f"\no Skipped: {len(severity_fixed_skipped)}")
                        for item in sorted(severity_fixed_skipped, key=lambda x: int(x['incident_no'])):
                            print(f"  Incident {item['incident_no']}: {item['reason']}")

                    if severity_fixed_failed:
                        print(f"\nX Failed to fix: {len(severity_fixed_failed)}")
                        for item in sorted(severity_fixed_failed, key=lambda x: int(x['incident_no'])):
                            print(f"  Incident {item['incident_no']}: {item['reason']}")
                            print(f"    Fix: {item['solution']}")

                    if not severity_fixed_success and not severity_fixed_failed and not severity_fixed_skipped:
                        print("No severity fixes attempted.")

                    if fix_dry_run and severity_fixed_success:
                        print("\nTo apply these severity changes, run without --dry-run")

                severity_needing_fix = [
                    result.incident_no for result in severity_results_for_output
                    if result.status in ('mismatched', 'mismatched_conflict', 'missing_etrack_severity')
                ]
                print("\n" + "=" * 60)
                print("SEVERITY LISTS")
                print("=" * 60)
                if severity_needing_fix:
                    print(f"\nSeverity-Mismatch-Incidents ({len(severity_needing_fix)}):")
                    print(f"  Incident-List={','.join(sorted(severity_needing_fix, key=int))}")
                else:
                    print("\nNo etrack severity mismatches found.")

                conflict_incidents = [result.incident_no for result in severity_results_for_output if result.has_priority_conflict]
                if conflict_incidents:
                    print(f"\nSeverity-Conflict-Incidents ({len(conflict_incidents)} - highest FI Case Priority wins):")
                    print(f"  Incident-List={','.join(sorted(conflict_incidents, key=int))}")
                else:
                    print("\nNo severity conflict incidents found.")

                missing_case_priority_rows = []
                for result in sorted(severity_results, key=lambda item: int(item.incident_no)):
                    missing_fis = [
                        fi_info.fi_id
                        for fi_info in result.severity_fis
                        if not fi_info.case_priority
                    ]
                    for fi_id in _sort_fi_ids(missing_fis):
                        missing_case_priority_rows.append((
                            result.incident_no,
                            fi_id,
                            result.etrack_user_id or 'N/A',
                            result.etrack_severity or 'N/A',
                        ))

                if missing_case_priority_rows:
                    missing_case_priority_incidents = sorted({incident_no for incident_no, _, _, _ in missing_case_priority_rows}, key=int)
                    missing_case_priority_fis = _sort_fi_ids({fi_id for _, fi_id, _, _ in missing_case_priority_rows})
                    print("\nMissing-Case-Priority")
                    print("  Jira FIs below do not carry a usable 'Case Priority' value.")
                    print(f"  Incident-Count={len(missing_case_priority_incidents)}")
                    print(f"  FI-Count={len(missing_case_priority_fis)}")
                    print()

                    incident_width = max(len('Incident'), max(len(incident_no) for incident_no, _, _, _ in missing_case_priority_rows))
                    fi_width = max(len('FI ID'), max(len(fi_id) for _, fi_id, _, _ in missing_case_priority_rows))
                    assignee_width = max(len('Assignee'), max(len(assignee) for _, _, assignee, _ in missing_case_priority_rows))
                    severity_width = max(len('Etrack Sev'), max(len(severity) for _, _, _, severity in missing_case_priority_rows))
                    separator = (
                        f"+-{'-' * incident_width}-+-{'-' * fi_width}-"
                        f"+-{'-' * assignee_width}-+-{'-' * severity_width}-+"
                    )
                    header = (
                        f"| {'Incident':<{incident_width}} | {'FI ID':<{fi_width}} | "
                        f"{'Assignee':<{assignee_width}} | {'Etrack Sev':<{severity_width}} |"
                    )

                    print(separator)
                    print(header)
                    print(separator)
                    for incident_no, fi_id, assignee, severity in missing_case_priority_rows:
                        print(
                            f"| {incident_no:<{incident_width}} | {fi_id:<{fi_width}} | "
                            f"{assignee:<{assignee_width}} | {severity:<{severity_width}} |"
                        )
                    print(separator)
                else:
                    print("\nNo FIs missing Case Priority found.")

                if not run_assignee_validation:
                    return

                print()

            # Validate FI records
            print("Starting validation (this may take a while for large datasets)...")
            results = validator.validate_records(records)

            # Show newly added users
            if validator.new_users_added:
                print("\n" + "=" * 60)
                print(f"NEW USERS ADDED: {len(validator.new_users_added)}")
                print("=" * 60)
                for account_data in validator.new_users_added:
                    print(f"\n+ {account_data.etrack_user_id}")
                    print(f"  Jira: {account_data.jira_account}")
                    print(f"  Veritas: {account_data.veritas_email}")
                    print(f"  Cohesity: {account_data.cohesity_email}")
                    print(f"  Confidence: {account_data.confidence}")

            # Generate report
            print("\n" + "=" * 60)
            print("VALIDATION RESULTS")
            print("=" * 60)
            print(validator.generate_report(results, include_details=not skip_details))

            # Show mismatches
            mismatches = validator.get_mismatches(results)
            if mismatches:
                # Collect mismatch data for report
                mismatch_data = []
                for result in mismatches:
                    for v in result.fi_validations:
                        if not v.matches:
                            mismatch_data.append({
                                'fi_id': v.fi_id,
                                'current_assignee': v.jira_assignee or 'N/A',
                                'expected_assignee': v.expected_jira_id or 'N/A'
                            })

                # Filter by report_from_user if specified
                if report_from_user:
                    mismatch_data = [m for m in mismatch_data if m['current_assignee'] == report_from_user]

                # Generate formatted report if --report or --report-from
                if generate_report:
                    print("\n" + ReportGenerator.generate_fi_reassignment_report(
                        mismatch_data,
                        include_details=not skip_details
                    ))
                else:
                    # Default output
                    print("\n" + "=" * 60)
                    print(f"MISMATCHES FOUND: {len(mismatches)}")
                    print("=" * 60)
                    if skip_details:
                        total_mismatched_fis = sum(
                            1 for result in mismatches for v in result.fi_validations if not v.matches
                        )
                        print(f"Total mismatched FIs: {total_mismatched_fis}")
                        mismatch_by_expected = {}
                        mismatch_by_current = {}
                        for item in mismatch_data:
                            exp = item.get('expected_assignee') or 'N/A'
                            cur = item.get('current_assignee') or 'N/A'
                            mismatch_by_expected[exp] = mismatch_by_expected.get(exp, 0) + 1
                            mismatch_by_current[cur] = mismatch_by_current.get(cur, 0) + 1

                        top_expected = sorted(
                            mismatch_by_expected.items(),
                            key=lambda x: (-x[1], x[0])
                        )[:5]
                        top_current = sorted(
                            mismatch_by_current.items(),
                            key=lambda x: (-x[1], x[0])
                        )[:5]

                        if top_expected:
                            print("Top expected assignees (target):")
                            for assignee, count in top_expected:
                                print(f"  {assignee}: {count}")
                        if top_current:
                            print("Top current assignees (source):")
                            for assignee, count in top_current:
                                print(f"  {assignee}: {count}")

                        print("Use without --skip-details for full per-FI mismatch rows.")
                    else:
                        for result in mismatches:
                            # Get FI IDs from validations
                            fi_ids = _sort_fi_ids([v.fi_id for v in result.fi_validations])
                            fi_list = ', '.join(fi_ids) if fi_ids else 'N/A'
                            print(f"\nFIs: {fi_list}")
                            print(f"  Incident: {result.incident_no}")
                            print(f"  Etrack Assignee: {result.etrack_user_id}")
                            print(f"  Expected Jira Account (from DB): {result.db_jira_account or 'N/A'}")
                            print(f"  Status: {result.status}")
                            for v in result.fi_validations:
                                if not v.matches:
                                    print(f"    {v.fi_id}: Jira has '{v.jira_assignee or 'N/A'}' (should be '{v.expected_jira_id or 'N/A'}')")

            # Fix mismatches if --fix is enabled
            if fix_mismatches and mismatches:
                print("\n" + "=" * 60)
                if fix_dry_run:
                    print("FIXING MISMATCHES (DRY-RUN - no changes will be made)")
                else:
                    print("FIXING MISMATCHES")
                print("=" * 60)

                fixed_success = []
                fixed_failed = []
                fixed_skipped = []

                # Helper to check --fix-from filter
                def should_skip_for_filter(fi_validation):
                    """Returns (should_skip, reason) tuple"""
                    if fix_from_user:
                        current_assignee = fi_validation.jira_assignee or ''
                        if current_assignee.lower() != fix_from_user.lower():
                            return True, f'Current assignee ({current_assignee}) != {fix_from_user}'
                    return False, None

                for result in mismatches:
                    etrack_user_id = result.etrack_user_id
                    expected_jira = result.db_jira_account

                    # Check prerequisites
                    if not expected_jira:
                        for v in result.fi_validations:
                            if not v.matches:
                                # Apply --fix-from filter first
                                skip, reason = should_skip_for_filter(v)
                                if skip:
                                    fixed_skipped.append({'fi_id': v.fi_id, 'reason': reason})
                                else:
                                    fixed_failed.append({
                                        'fi_id': v.fi_id,
                                        'reason': 'No jira_account in database',
                                        'solution': f'python3 -m account_manager.cli fetch-jira-id {etrack_user_id}'
                                    })
                        continue

                    # Check if account is verified
                    account = db.get_account(etrack_user_id=etrack_user_id)
                    if not account:
                        for v in result.fi_validations:
                            if not v.matches:
                                # Apply --fix-from filter first
                                skip, reason = should_skip_for_filter(v)
                                if skip:
                                    fixed_skipped.append({'fi_id': v.fi_id, 'reason': reason})
                                else:
                                    fixed_failed.append({
                                        'fi_id': v.fi_id,
                                        'reason': 'Account not found',
                                        'solution': f'python3 -m account_manager.cli add {etrack_user_id} && python3 -m account_manager.cli fetch-email {etrack_user_id} && python3 -m account_manager.cli fetch-jira-id {etrack_user_id}'
                                    })
                        continue

                    manual_verified = account.get('manual_verified', '').lower().strip()
                    if manual_verified != 'yes':
                        # Generate appropriate message based on verification status
                        if manual_verified == 'invalid':
                            reason_msg = 'Account marked INVALID - user data is incorrect or outdated'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # Review data. If corrected, run: python3 -m account_manager.cli update-verified {etrack_user_id} yes'
                        elif manual_verified == 'no':
                            reason_msg = 'Account not yet verified - needs manual verification before auto-fix'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # Verify data is correct, then: python3 -m account_manager.cli update-verified {etrack_user_id} yes'
                        elif manual_verified == 'departed':
                            reason_msg = 'User has DEPARTED the organization - account is inactive'
                            solution_msg = f'This user is no longer with the company. Reassign FI to active user or remove FI assignment.'
                        elif manual_verified == 'pending':
                            reason_msg = 'Verification PENDING - awaiting confirmation from user/manager'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # Follow up on verification. When confirmed: python3 -m account_manager.cli update-verified {etrack_user_id} yes'
                        elif manual_verified == 'duplicate':
                            reason_msg = 'DUPLICATE entry - another record exists for this person'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # Find and use the primary account instead. Consider deleting this duplicate.'
                        elif manual_verified == 'suspended':
                            reason_msg = 'Account SUSPENDED - temporarily inactive/on hold'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # Check suspension reason. If resolved: python3 -m account_manager.cli update-verified {etrack_user_id} yes'
                        elif manual_verified == 'external':
                            reason_msg = 'EXTERNAL contractor/vendor account - different verification rules apply'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # External accounts require manager approval. If approved: python3 -m account_manager.cli update-verified {etrack_user_id} yes'
                        else:
                            # Empty or unknown value
                            reason_msg = f'Account verification status unknown (manual_verified={manual_verified or "empty"})'
                            solution_msg = f'python3 -m account_manager.cli get {etrack_user_id}  # Check data, then: python3 -m account_manager.cli update-verified {etrack_user_id} <status>'

                        for v in result.fi_validations:
                            if not v.matches:
                                # Apply --fix-from filter first
                                skip, reason = should_skip_for_filter(v)
                                if skip:
                                    fixed_skipped.append({'fi_id': v.fi_id, 'reason': reason})
                                else:
                                    fixed_failed.append({
                                        'fi_id': v.fi_id,
                                        'reason': reason_msg,
                                        'solution': solution_msg
                                    })
                        continue

                    # Attempt to fix each mismatched FI
                    for v in result.fi_validations:
                        if not v.matches:
                            # Check if FI should be skipped
                            if v.fi_id in skip_fi_ids:
                                fixed_skipped.append({
                                    'fi_id': v.fi_id,
                                    'reason': 'Excluded via --skip-fi'
                                })
                                continue

                            # Check --fix-from filter
                            skip, reason = should_skip_for_filter(v)
                            if skip:
                                fixed_skipped.append({'fi_id': v.fi_id, 'reason': reason})
                                continue

                            # Interactive prompt
                            if fix_interactive and not fix_dry_run:
                                print(f"\n  {v.fi_id}: {v.jira_assignee or 'None'} -> {expected_jira}")
                                response = input("  Fix this? (y/n/q to quit): ").strip().lower()
                                if response == 'q':
                                    print("  Stopping fix operation.")
                                    break
                                if response != 'y':
                                    fixed_skipped.append({
                                        'fi_id': v.fi_id,
                                        'reason': 'User declined'
                                    })
                                    continue

                            try:
                                if fix_dry_run:
                                    # Dry-run: just report what would happen
                                    fixed_success.append({
                                        'fi_id': v.fi_id,
                                        'old_assignee': v.jira_assignee,
                                        'new_assignee': expected_jira,
                                        'dry_run': True
                                    })
                                    db.log_action('fix_fi', 'fi', v.fi_id,
                                                 old_value=v.jira_assignee, new_value=expected_jira,
                                                 status='dry_run', details=f'etrack_user={etrack_user_id}')
                                else:
                                    success = jira_client.update_assignee(v.fi_id, expected_jira)
                                    if success:
                                        fixed_success.append({
                                            'fi_id': v.fi_id,
                                            'old_assignee': v.jira_assignee,
                                            'new_assignee': expected_jira,
                                            'dry_run': False
                                        })
                                        db.log_action('fix_fi', 'fi', v.fi_id,
                                                     old_value=v.jira_assignee, new_value=expected_jira,
                                                     status='success', details=f'etrack_user={etrack_user_id}')
                                    else:
                                        fixed_failed.append({
                                            'fi_id': v.fi_id,
                                            'reason': f'Jira API update failed (target: {expected_jira})',
                                            'solution': f'Check: 1) FI status allows reassign, 2) {expected_jira} is valid Jira user, 3) API token has permission'
                                        })
                                        db.log_action('fix_fi', 'fi', v.fi_id,
                                                     old_value=v.jira_assignee, new_value=expected_jira,
                                                     status='failed', details='Jira API update failed')
                            except Exception as e:
                                fixed_failed.append({
                                    'fi_id': v.fi_id,
                                    'reason': str(e),
                                    'solution': f'Check Jira connection and verify {expected_jira} exists in Jira'
                                })
                                db.log_action('fix_fi', 'fi', v.fi_id,
                                             old_value=v.jira_assignee, new_value=expected_jira,
                                             status='failed', details=str(e))

                # Summary
                print("\n" + "-" * 40)
                if fix_dry_run:
                    print("FIX SUMMARY (DRY-RUN)")
                else:
                    print("FIX SUMMARY")
                print("-" * 40)

                if fixed_success:
                    label = "Would fix" if fix_dry_run else "Successfully fixed"
                    print(f"\n+ {label}: {len(fixed_success)}")
                    for item in sorted(fixed_success, key=lambda x: _fi_sort_key(x['fi_id'])):
                        print(f"  {item['fi_id']}: {item['old_assignee'] or 'None'} -> {item['new_assignee']}")

                if fixed_skipped:
                    print(f"\no Skipped: {len(fixed_skipped)}")
                    for item in sorted(fixed_skipped, key=lambda x: _fi_sort_key(x['fi_id'])):
                        print(f"  {item['fi_id']}: {item['reason']}")

                if fixed_failed:
                    print(f"\nX Failed to fix: {len(fixed_failed)}")
                    for item in sorted(fixed_failed, key=lambda x: _fi_sort_key(x['fi_id'])):
                        print(f"  {item['fi_id']}: {item['reason']}")
                        print(f"    Fix: {item['solution']}")

                if not fixed_success and not fixed_failed and not fixed_skipped:
                    print("No fixes attempted.")

                if fix_dry_run and fixed_success:
                    print(f"\nTo apply these changes, run without --dry-run")

            # Show summary lists at bottom (conflict FIs and mismatch FIs)
            print("\n" + "=" * 60)
            print("FI LISTS")
            print("=" * 60)

            # Conflict FIs (skip-fi list)
            if conflicts:
                conflict_fi_list = ','.join(_sort_fi_ids(conflicts.keys()))
                print(f"\nConflict FIs ({len(conflicts)} - multiple incidents with different assignees):")
                print(f"  --skip-fi={conflict_fi_list}")
            else:
                print("\nNo conflict FIs found.")

            # Mismatch FIs (excluding conflict FIs)
            if mismatches:
                all_mismatch_fi_ids = set()
                for result in mismatches:
                    for v in result.fi_validations:
                        if not v.matches:
                            all_mismatch_fi_ids.add(v.fi_id)

                # Exclude conflict FIs from mismatch list
                conflict_fi_ids = set(conflicts.keys()) if conflicts else set()
                mismatch_only_fi_ids = all_mismatch_fi_ids - conflict_fi_ids

                if mismatch_only_fi_ids:
                    mismatch_fi_list = ','.join(_sort_fi_ids(mismatch_only_fi_ids))
                    print(f"\nMismatch FIs ({len(mismatch_only_fi_ids)} - Jira assignee doesn't match expected):")
                    print(f"  Mismatch-List={mismatch_fi_list}")
                else:
                    print("\nNo mismatch FIs found (all mismatches are conflicts).")
            else:
                print("\nNo mismatch FIs found.")

        elif command == 'check-assignee':
            # Check specific FI assignee
            if len(sys.argv) < 3:
                print("Usage: cli.py check-assignee <fi_id>")
                print("  Example: cli.py check-assignee FI-59131")
                return

            fi_id = sys.argv[2]
            use_mock = '--mock' in sys.argv

            print(f"Checking FI: {fi_id}")
            print("=" * 60)

            # Initialize Jira client
            if use_mock:
                print("Using Mock Jira Client")
                jira_client = MockJiraClient({fi_id: 'mock.user'})
            else:
                try:
                    jira_client = JiraClient()
                    if not jira_client.test_connection():
                        print("X Failed to connect to Jira")
                        return
                except Exception as e:
                    print(f"X Error initializing Jira client: {e}")
                    return

            print()

            # Get assignee from Jira
            print(f"Fetching assignee from Jira...")
            jira_assignee = jira_client.get_assignee(fi_id)

            if jira_assignee:
                print(f"+ Jira Assignee: {jira_assignee}")

                # Try to find in database
                print(f"\nSearching in database...")
                account = db.search_accounts(jira_account=jira_assignee)

                if account:
                    print(f"+ Found in database:")
                    print(f"  Etrack User ID: {account[0]['etrack_user_id']}")
                    print(f"  Jira Account: {account[0]['jira_account']}")
                    print(f"  Cohesity Email: {account[0]['cohesity_email']}")
                    print(f"  Veritas Email: {account[0]['veritas_email']}")
                else:
                    print(f"X Not found in database")
                    print(f"  You may need to add this account:")
                    print(f"  python3 -m account_manager.cli add <etrack_user_id>")
            else:
                print(f"X Could not fetch assignee (FI may not exist or has no assignee)")

            # Get full issue summary
            if not use_mock:
                print(f"\nFetching full issue details...")
                summary = jira_client.get_issue_summary(fi_id)
                if summary:
                    print(f"\nIssue Details:")
                    print(f"  Summary: {summary.get('summary')}")
                    print(f"  Status: {summary.get('status')}")
                    print(f"  Priority: {summary.get('priority')}")
                    print(f"  Created: {summary.get('created')}")
                    print(f"  Updated: {summary.get('updated')}")

        elif command == 'update-emails':
            # Update missing Veritas emails using euserls
            dry_run = '--dry-run' in sys.argv
            verbose = '--verbose' in sys.argv

            print("Updating Missing Veritas Emails")
            print("=" * 60)
            if dry_run:
                print("DRY RUN MODE - No changes will be made")
                print("=" * 60)

            try:
                updater = EuserlsUpdater(db, verbose=verbose)
                stats = updater.update_missing_emails(dry_run=dry_run)

                print("\n" + "=" * 60)
                print("SUMMARY")
                print("=" * 60)
                print(f"Accounts needing update: {stats['total']}")
                print(f"Successfully updated: {stats['updated']}")
                print(f"Failed: {stats['failed']}")
                print(f"Already had email: {stats['skipped']}")

                if not dry_run and stats['updated'] > 0:
                    print(f"\n+ Updated {stats['updated']} accounts")
                    print("Run 'list-incomplete' to see remaining missing fields")
                elif dry_run:
                    print("\nRun without --dry-run to apply updates")

            except RuntimeError as e:
                print(f"X Error: {e}")
                print("\nTroubleshooting:")
                print("  1. Ensure euserls is installed and in your PATH")
                print("  2. OR set RMTCMD_HOST environment variable for SSH execution")
                print("     Example: export RMTCMD_HOST=user@hostname")

        elif command == 'fetch-email':
            # Fetch email for a single user
            if len(sys.argv) < 3:
                print("Usage: cli.py fetch-email <etrack_user_id> [--dry-run]")
                return

            etrack_user_id = sys.argv[2]
            dry_run = '--dry-run' in sys.argv

            # Check if account exists
            account = db.get_account(etrack_user_id=etrack_user_id)
            if not account:
                print(f"X Account not found: {etrack_user_id}")
                print(f"  Add it first: python3 -m account_manager.cli add {etrack_user_id}")
                return

            print(f"Fetching email for: {etrack_user_id}")
            print("=" * 60)

            try:
                updater = EuserlsUpdater(db, verbose=True)
                success = updater.update_single_account(etrack_user_id, dry_run=dry_run)

                if success:
                    if not dry_run:
                        # Show updated account
                        account = db.get_account(etrack_user_id=etrack_user_id)
                        print("\n+ Account updated:")
                        print(f"  Etrack User ID: {account['etrack_user_id']}")
                        print(f"  Veritas Email:  {account['veritas_email']}")
                    else:
                        print("\nRun without --dry-run to update the database")
                else:
                    print("\nX Failed to fetch email")

            except RuntimeError as e:
                print(f"X Error: {e}")

        elif command == 'update-verified':
            # Update manual verification status
            if len(sys.argv) < 4:
                print("Usage: cli.py update-verified <etrack_user_id> <status>")
                print("  Valid statuses: yes, no, pending, invalid, departed, duplicate, suspended, external")
                return

            etrack_user_id = sys.argv[2]
            verified_value = sys.argv[3].lower().strip()

            # Import valid statuses from models
            from .models import VALID_VERIFICATION_STATUSES
            if verified_value not in VALID_VERIFICATION_STATUSES:
                valid_list = ', '.join(sorted(VALID_VERIFICATION_STATUSES))
                print(f"X Error: Invalid status '{verified_value}'")
                print(f"  Valid statuses: {valid_list}")
                return

            account = db.get_account(etrack_user_id=etrack_user_id)
            if not account:
                print(f"X Account not found: {etrack_user_id}")
                return

            old_verified = account.get('manual_verified', 'no')
            db.update_account(etrack_user_id, manual_verified=verified_value)
            db.log_action('verify_account', 'account', etrack_user_id,
                         old_value=old_verified, new_value=verified_value, status='success')
            print(f"+ Updated manual_verified for {etrack_user_id}: {verified_value}")

        elif command == 'update-notes':
            # Update notes field
            if len(sys.argv) < 4:
                print("Usage: cli.py update-notes <etrack_user_id> <notes>")
                print("       cli.py update-notes <etrack_user_id> --clear")
                return

            etrack_user_id = sys.argv[2]

            account = db.get_account(etrack_user_id=etrack_user_id)
            if not account:
                print(f"X Account not found: {etrack_user_id}")
                return

            if '--clear' in sys.argv:
                db.update_account(etrack_user_id, notes=None)
                print(f"+ Cleared notes for {etrack_user_id}")
            else:
                notes = ' '.join(sys.argv[3:])
                db.update_account(etrack_user_id, notes=notes)
                print(f"+ Updated notes for {etrack_user_id}")

        elif command == 'update-jira-ids':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('update-jira-ids')
                return
            # Update missing JIRA IDs using first/last name
            dry_run = '--dry-run' in sys.argv
            verbose = '--verbose' in sys.argv
            use_mock = '--mock' in sys.argv

            print("Updating Missing JIRA IDs and Cohesity Emails")
            print("=" * 60)
            if dry_run:
                print("DRY RUN MODE - No changes will be made")
                print("=" * 60)
            if use_mock:
                print("MOCK MODE - Using mock JIRA client")
                print("=" * 60)

            try:
                updater = JiraIdUpdater(db, verbose=verbose, use_mock=use_mock)
                stats = updater.update_missing_jira_ids(dry_run=dry_run)

                print("\n" + "=" * 60)
                print("SUMMARY")
                print("=" * 60)
                print(f"Accounts needing update: {stats['total']}")
                print(f"Successfully updated: {stats['updated']}")
                print(f"Cohesity emails also updated: {stats.get('emails_updated', 0)}")
                print(f"Conflicts (need manual update): {stats.get('conflicts', 0)}")
                print(f"Failed (no JIRA user found): {stats['failed']}")
                print(f"Skipped: {stats['skipped']}")

                if stats.get('conflicts', 0) > 0:
                    print(f"\n! {stats['conflicts']} accounts had conflicts - see details above")
                    print("  Use: python3 -m account_manager.cli update <etrack_user_id> jira_account=<value>")

                if not dry_run and stats['updated'] > 0:
                    print(f"\n+ Updated {stats['updated']} accounts")
                    print("Run 'list-incomplete' to see remaining missing fields")
                elif dry_run:
                    print("\nRun without --dry-run to apply updates")

            except RuntimeError as e:
                print(f"X Error: {e}")
                print("\nTroubleshooting:")
                print("  1. Ensure JIRA credentials are configured")
                print("  2. Check JIRA_URL, JIRA_USER, JIRA_API_TOKEN environment variables")
                print("  3. Use --mock for testing without real JIRA connection")

        elif command == 'fetch-jira-id':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('fetch-jira-id')
                return
            # Fetch JIRA ID for a single user
            if len(sys.argv) < 3:
                print("Usage: cli.py fetch-jira-id <etrack_user_id> [--dry-run] [--mock]")
                return

            etrack_user_id = sys.argv[2]
            dry_run = '--dry-run' in sys.argv
            use_mock = '--mock' in sys.argv

            # Check if account exists
            account = db.get_account(etrack_user_id=etrack_user_id)
            if not account:
                print(f"X Account not found: {etrack_user_id}")
                print(f"  Add it first: python3 -m account_manager.cli add {etrack_user_id}")
                return

            # Check if names are present
            if not account.get('first_name') or not account.get('last_name'):
                print(f"X Account must have both first_name and last_name")
                print(f"  Current: first_name={account.get('first_name', '(missing)')}, last_name={account.get('last_name', '(missing)')}")
                print(f"  Update names first: python3 -m account_manager.cli update-emails {etrack_user_id}")
                return

            print(f"Fetching JIRA ID for: {etrack_user_id}")
            print("=" * 60)
            if use_mock:
                print("MOCK MODE")

            try:
                updater = JiraIdUpdater(db, verbose=True, use_mock=use_mock)
                success = updater.update_single_account(etrack_user_id, dry_run=dry_run)

                if success:
                    if not dry_run:
                        # Show updated account
                        account = db.get_account(etrack_user_id=etrack_user_id)
                        print("\n+ Account updated:")
                        print(f"  Etrack User ID: {account['etrack_user_id']}")
                        print(f"  JIRA Account:   {account['jira_account']}")
                    else:
                        print("\nRun without --dry-run to update the database")
                else:
                    print("\nX Failed to fetch JIRA ID")

            except RuntimeError as e:
                print(f"X Error: {e}")

        elif command == 'auto-update':
            # Handle help flag
            if len(sys.argv) > 2 and sys.argv[2] in ['-h', '--help']:
                print_usage('auto-update')
                return
            # Auto-update: fetch-email + fetch-jira-id in one step
            if len(sys.argv) < 3:
                print("Usage: cli.py auto-update <etrack_user_id> [--dry-run] [--verbose] [--mock]")
                return

            etrack_user_id = sys.argv[2]
            dry_run = '--dry-run' in sys.argv
            verbose = '--verbose' in sys.argv
            use_mock = '--mock' in sys.argv

            print(f"Auto-Update Account: {etrack_user_id}")
            print("=" * 60)
            if dry_run:
                print("DRY RUN MODE - No changes will be made")
            if verbose:
                print("VERBOSE MODE - Detailed output enabled")
            print("=" * 60)

            # Check if account exists
            account = db.get_account(etrack_user_id=etrack_user_id)
            if not account:
                print(f"X Account not found: {etrack_user_id}")
                print(f"  Add it first: python3 -m account_manager.cli add {etrack_user_id}")
                return

            # Track what was updated
            updated_fields = []
            errors = []

            # Step 1: Fetch email/names using euserls
            print("\n[Step 1/2] Fetching Veritas email and names...")
            needs_email = not account.get('veritas_email')
            needs_names = not (account.get('first_name') and account.get('last_name'))

            if needs_email or needs_names:
                try:
                    updater = EuserlsUpdater(db, verbose=verbose)
                    success = updater.update_single_account(etrack_user_id, dry_run=dry_run)
                    if success:
                        if needs_email:
                            updated_fields.append('veritas_email')
                        if needs_names:
                            updated_fields.extend(['first_name', 'last_name'])
                        updated_fields.append('community_account')
                        print("  + Email/names fetched successfully")
                    else:
                        errors.append('euserls lookup failed')
                        print("  X Failed to fetch email/names")
                except Exception as e:
                    errors.append(f'euserls error: {e}')
                    print(f"  X Error: {e}")
            else:
                print(f"  - Already has: veritas_email, first_name, last_name")
                if verbose:
                    print(f"    Email: {account.get('veritas_email')}")
                    print(f"    Name: {account.get('first_name')} {account.get('last_name')}")

            # Refresh account data for step 2
            account = db.get_account(etrack_user_id=etrack_user_id)

            # Step 2: Fetch JIRA ID using names
            print("\n[Step 2/2] Fetching JIRA account ID...")
            needs_jira = not account.get('jira_account')
            has_names = account.get('first_name') and account.get('last_name')

            if needs_jira and has_names:
                try:
                    jira_updater = JiraIdUpdater(db, verbose=verbose, use_mock=use_mock)
                    success = jira_updater.update_single_account(etrack_user_id, dry_run=dry_run)
                    if success:
                        updated_fields.append('jira_account')
                        # Cohesity email might also have been updated
                        refreshed = db.get_account(etrack_user_id=etrack_user_id)
                        if refreshed.get('cohesity_email') and not account.get('cohesity_email'):
                            updated_fields.append('cohesity_email')
                        print("  + JIRA ID fetched successfully")
                    else:
                        errors.append('JIRA lookup failed or conflicts found')
                        print("  X Failed to fetch JIRA ID (see details above)")
                except Exception as e:
                    errors.append(f'JIRA error: {e}')
                    print(f"  X Error: {e}")
            elif not has_names:
                errors.append('Missing first_name/last_name for JIRA lookup')
                print("  X Cannot fetch JIRA ID - missing first_name or last_name")
            else:
                print(f"  - Already has: jira_account = {account.get('jira_account')}")

            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)

            if updated_fields:
                print(f"Fields updated: {', '.join(set(updated_fields))}")
            else:
                print("No fields updated (already populated or errors)")

            if errors:
                print(f"Errors: {len(errors)}")
                for err in errors:
                    print(f"  - {err}")

            # Show final account state
            final_account = db.get_account(etrack_user_id=etrack_user_id)
            if verbose or updated_fields:
                print("\nCurrent account state:")
                print(f"  Etrack User ID:    {final_account['etrack_user_id']}")
                print(f"  First Name:        {final_account.get('first_name') or '(missing)'}")
                print(f"  Last Name:         {final_account.get('last_name') or '(missing)'}")
                print(f"  Veritas Email:     {final_account.get('veritas_email') or '(missing)'}")
                print(f"  Cohesity Email:    {final_account.get('cohesity_email') or '(missing)'}")
                print(f"  Community Account: {final_account.get('community_account') or '(missing)'}")
                print(f"  JIRA Account:      {final_account.get('jira_account') or '(missing)'}")
                print(f"  Manual Verified:   {final_account.get('manual_verified', 'no')}")

            if dry_run:
                print("\nRun without --dry-run to apply changes")

        elif command == 'assign-etrack-fi':
            # Assign etrack to user and update linked FI in Jira
            if len(sys.argv) < 4:
                print("Usage: cli.py assign-etrack-fi <etrack_number> <etrack_user_id> [options]")
                print("  Example: cli.py assign-etrack-fi 1234567 user_one")
                print("")
                print("Options:")
                print("  --dry-run    Show what would be done without making changes")
                print("  --mock       Use mock clients (for testing)")
                print("  --verbose    Show detailed debug information")
                return

            etrack_number = sys.argv[2]
            etrack_user_id = sys.argv[3]
            dry_run = '--dry-run' in sys.argv
            use_mock = '--mock' in sys.argv
            verbose = '--verbose' in sys.argv

            print(f"Assign Etrack and FI")
            print("=" * 60)
            print(f"Etrack Number:   {etrack_number}")
            print(f"Target User:     {etrack_user_id}")
            if dry_run:
                print("MODE:            DRY-RUN (no changes will be made)")
            if use_mock:
                print("MODE:            MOCK (testing without API calls)")
            if verbose:
                print("MODE:            VERBOSE (debug output enabled)")
            print("=" * 60)

            # Step 1: Validate user exists in database and has jira_account
            print("\n[Step 1] Looking up user in database...")
            account = db.get_account(etrack_user_id=etrack_user_id)

            if not account:
                print(f"X User '{etrack_user_id}' not found in database")
                print(f"")
                print(f"To add this user:")
                print(f"  python3 -m account_manager.cli add {etrack_user_id}")
                print(f"  python3 -m account_manager.cli update {etrack_user_id} jira_account=<jira_username>")
                return

            jira_account = account.get('jira_account')
            if not jira_account:
                print(f"X User '{etrack_user_id}' found but jira_account is not set")
                print(f"")
                print(f"To set jira_account:")
                print(f"  python3 -m account_manager.cli update {etrack_user_id} jira_account=<jira_username>")
                print(f"")
                print(f"Or use automatic lookup:")
                print(f"  python3 -m account_manager.cli fetch-jira-id {etrack_user_id}")
                return

            # Check if account is verified
            manual_verified = account.get('manual_verified', '')
            if manual_verified.lower() != 'yes':
                print(f"X User '{etrack_user_id}' is not verified (manual_verified='{manual_verified}')")
                print(f"")
                print(f"Only verified accounts can be used for assignment.")
                print(f"To view account details before verifying:")
                print(f"  python3 -m account_manager.cli get {etrack_user_id}")
                print(f"")
                print(f"To verify this account:")
                print(f"  python3 -m account_manager.cli update-verified {etrack_user_id} yes")
                return

            print(f"  + Found user: {etrack_user_id}")
            print(f"    Jira Account: {jira_account}")

            # Step 2: Get external references from etrack
            print("\n[Step 2] Fetching external references from etrack...")
            try:
                if use_mock:
                    etrack_client = MockEtrackExecutor()
                else:
                    etrack_client = EtrackExecutor()

                external_refs = etrack_client.get_external_references(etrack_number, verbose=verbose)

                if not external_refs:
                    print(f"X No FI found linked to etrack {etrack_number} (ext_src in TOOLS_AGILE/JIRA)")
                    print("")
                    print("Possible reasons:")
                    print("  - Etrack doesn't have an FI linked")
                    print("  - External reference uses different ext_src")
                    print("  - Query/parsing issue - try with --verbose for details")
                    return

                fi_ids = _sort_fi_ids([ref.ext_ref_id for ref in external_refs])
                print(f"  + Found {len(fi_ids)} linked FI(s): {', '.join(fi_ids)}")

            except Exception as e:
                print(f"X Error fetching external references: {e}")
                return

            # Step 3: Check current etrack assignee and reassign if needed
            print("\n[Step 3] Checking etrack assignment...")
            try:
                current_assignee = etrack_client.get_etrack_assignee(etrack_number)
                print(f"  Current assignee: {current_assignee or 'N/A'}")

                if current_assignee == etrack_user_id:
                    print(f"  + Etrack already assigned to {etrack_user_id}")
                else:
                    print(f"  -> Reassigning etrack from '{current_assignee}' to '{etrack_user_id}'...")
                    success = etrack_client.assign_etrack(etrack_number, etrack_user_id, dry_run=dry_run)
                    if dry_run:
                        db.log_action('assign_etrack', 'etrack', etrack_number,
                                     old_value=current_assignee, new_value=etrack_user_id,
                                     status='dry_run')
                    elif success:
                        db.log_action('assign_etrack', 'etrack', etrack_number,
                                     old_value=current_assignee, new_value=etrack_user_id,
                                     status='success')
                    else:
                        db.log_action('assign_etrack', 'etrack', etrack_number,
                                     old_value=current_assignee, new_value=etrack_user_id,
                                     status='failed', details='eset command failed')
                        print(f"  * Failed to reassign etrack, continuing with FI assignment...")

            except Exception as e:
                print(f"  * Error checking/updating etrack: {e}")
                print(f"    Continuing with FI assignment...")

            # Step 4: Initialize Jira client and update FI assignees
            print("\n[Step 4] Updating FI assignment(s) in Jira...")
            try:
                if use_mock:
                    jira_client = MockJiraClient()
                else:
                    jira_client = JiraClient()
                    if not jira_client.test_connection():
                        print("X Failed to connect to Jira")
                        return
            except Exception as e:
                print(f"X Error initializing Jira client: {e}")
                return

            # Check and update each FI
            fi_results = {'updated': 0, 'already_assigned': 0, 'failed': 0}

            for fi_id in fi_ids:
                print(f"\n  Processing {fi_id}...")

                # Get current FI assignee
                current_fi_assignee = jira_client.get_assignee(fi_id)
                print(f"    Current Jira assignee: {current_fi_assignee or 'N/A'}")

                if current_fi_assignee == jira_account:
                    print(f"    + Already assigned to {jira_account}")
                    fi_results['already_assigned'] += 1
                else:
                    print(f"    -> Updating assignee to '{jira_account}'...")
                    if dry_run:
                        print(f"    [DRY-RUN] Would update {fi_id} assignee to {jira_account}")
                        fi_results['updated'] += 1
                        db.log_action('assign_fi', 'fi', fi_id,
                                     old_value=current_fi_assignee, new_value=jira_account,
                                     status='dry_run', details=f'etrack={etrack_number}, user={etrack_user_id}')
                    else:
                        success = jira_client.update_assignee(fi_id, jira_account)
                        if success:
                            fi_results['updated'] += 1
                            db.log_action('assign_fi', 'fi', fi_id,
                                         old_value=current_fi_assignee, new_value=jira_account,
                                         status='success', details=f'etrack={etrack_number}, user={etrack_user_id}')
                        else:
                            fi_results['failed'] += 1
                            db.log_action('assign_fi', 'fi', fi_id,
                                         old_value=current_fi_assignee, new_value=jira_account,
                                         status='failed', details=f'etrack={etrack_number}, user={etrack_user_id}')

            # Summary
            print("\n" + "=" * 60)
            print("SUMMARY")
            print("=" * 60)
            print(f"Etrack:           {etrack_number}")
            print(f"Target User:      {etrack_user_id} (Jira: {jira_account})")
            print(f"FIs Processed:    {len(fi_ids)}")
            print(f"  Updated:        {fi_results['updated']}")
            print(f"  Already OK:     {fi_results['already_assigned']}")
            print(f"  Failed:         {fi_results['failed']}")

            if dry_run:
                print("\nRun without --dry-run to apply changes")
            elif fi_results['updated'] > 0:
                print("\n+ Assignment completed successfully")
            elif fi_results['already_assigned'] == len(fi_ids):
                print("\n+ All assignments already correct")

        elif command == 'action-log':
            # View action log
            # Parse options
            limit = 50
            action_type = None
            target_type = None
            status = None
            since = None
            detailed = False

            for arg in sys.argv[2:]:
                if arg.startswith('--limit='):
                    limit = int(arg.split('=')[1])
                elif arg.startswith('--type='):
                    action_type = arg.split('=')[1]
                elif arg.startswith('--target='):
                    target_type = arg.split('=')[1]
                elif arg.startswith('--status='):
                    status = arg.split('=')[1]
                elif arg.startswith('--since='):
                    since = arg.split('=')[1]
                elif arg == '--detailed':
                    detailed = True

            report_gen = ReportGenerator(db)
            print(report_gen.generate_action_log_report(
                limit=limit,
                action_type=action_type,
                target_type=target_type,
                status=status,
                since=since,
                table_format=not detailed
            ))

        elif command == 'action-summary':
            # View action summary
            since = None
            daily = False

            for arg in sys.argv[2:]:
                if arg.startswith('--since='):
                    since = arg.split('=')[1]
                elif arg == '--daily':
                    daily = True

            report_gen = ReportGenerator(db)
            if daily:
                print(report_gen.generate_daily_activity_report())
            else:
                print(report_gen.generate_action_summary_report(since=since))

        elif command == 'action-history':
            # View history for specific target
            if len(sys.argv) < 4:
                print("Usage: cli.py action-history <target_type> <target_id>")
                print("  target_type: account, fi, etrack")
                print("  Example: cli.py action-history account john_doe")
                print("  Example: cli.py action-history fi FI-58985")
                return

            target_type = sys.argv[2]
            target_id = sys.argv[3]

            report_gen = ReportGenerator(db)
            print(report_gen.generate_target_history_report(target_type, target_id))

        elif command == 'action-clear':
            # Clear action log
            before = None
            clear_all = False

            for arg in sys.argv[2:]:
                if arg.startswith('--before='):
                    before = arg.split('=')[1]
                elif arg == '--all':
                    clear_all = True

            if not before and not clear_all:
                print("Usage: cli.py action-clear --before=YYYY-MM-DD")
                print("   or: cli.py action-clear --all")
                return

            if clear_all:
                confirm = input("Are you sure you want to clear ALL action log entries? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("Cancelled.")
                    return
                deleted = db.clear_action_log()
            else:
                deleted = db.clear_action_log(before=before)

            print(f"+ Cleared {deleted} action log entries")

        elif command == 'lookup-etrack-emails':
            # Lookup emails for list of Etrack IDs, FI IDs, or usernames
            import select

            # Parse arguments
            file_path = None
            input_type = 'etrack'  # default: etrack, fi, user
            email_type = 'cohesity'  # default
            output_format = 'table'  # default
            include_missing = False
            verbose = '--verbose' in sys.argv or '-v' in sys.argv

            for arg in sys.argv[2:]:
                if arg.startswith('-f=') or arg.startswith('--file='):
                    file_path = arg.split('=', 1)[1]
                elif arg in ['-f', '--file'] and sys.argv.index(arg) + 1 < len(sys.argv):
                    idx = sys.argv.index(arg)
                    file_path = sys.argv[idx + 1]
                elif arg.startswith('--input='):
                    input_type = arg.split('=', 1)[1].lower()
                elif arg.startswith('--email='):
                    email_type = arg.split('=', 1)[1].lower()
                elif arg.startswith('--format='):
                    output_format = arg.split('=', 1)[1].lower()
                elif arg == '--include-missing':
                    include_missing = True

            if input_type not in ['etrack', 'fi', 'user']:
                print(f"X Invalid input type: {input_type}")
                print("  Use 'etrack', 'fi', or 'user'")
                return

            if email_type not in ['cohesity', 'veritas']:
                print(f"X Invalid email type: {email_type}")
                print("  Use 'cohesity' or 'veritas'")
                return

            if output_format not in ['table', 'csv', 'semi', 'simple']:
                print(f"X Invalid format: {output_format}")
                print("  Use 'table', 'csv', 'semi', or 'simple'")
                return

            # Read IDs from file or stdin
            input_ids = []

            def parse_line(line):
                """Parse a line and extract ID based on input type."""
                line = line.strip()
                if not line or line.startswith('#'):
                    return None
                # Get first token
                token = line.split()[0] if line.split() else ''
                if not token:
                    return None
                if input_type == 'etrack':
                    # Must be numeric
                    return token if token.isdigit() else None
                elif input_type == 'fi':
                    # Must be FI-xxx pattern
                    if token.upper().startswith('FI-'):
                        return token.upper()
                    return None
                else:  # user
                    # Any non-empty string
                    return token

            if file_path:
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            parsed = parse_line(line)
                            if parsed:
                                input_ids.append(parsed)
                except FileNotFoundError:
                    print(f"X File not found: {file_path}")
                    return
            else:
                # Check if stdin has data
                if select.select([sys.stdin], [], [], 0.0)[0]:
                    for line in sys.stdin:
                        parsed = parse_line(line)
                        if parsed:
                            input_ids.append(parsed)
                else:
                    print("Usage: lookup-etrack-emails -f <file> or pipe via stdin")
                    print("Run 'help lookup-etrack-emails' for details")
                    return

            if not input_ids:
                print(f"X No valid {input_type} IDs found")
                return

            type_label = {'etrack': 'Etrack', 'fi': 'FI', 'user': 'User'}[input_type]
            print(f"Looking up {email_type} emails for {len(input_ids)} {type_label} IDs...")
            print("=" * 60)

            # Initialize Etrack executor if needed
            etrack_exec = None
            jira_client = None
            if input_type in ['etrack', 'fi']:
                try:
                    etrack_exec = EtrackExecutor()
                except RuntimeError as e:
                    print(f"X Error: {e}")
                    return

            if input_type == 'fi':
                # Need Jira client to get Etrack from FI
                try:
                    jira_client = JiraClient()
                except Exception as e:
                    print(f"X Error initializing Jira client: {e}")
                    return

            # Results storage
            results = []  # List of (input_id, assignee, email)
            missing = []  # Items with no email found

            # OPTIMIZED: Batch lookup for etrack type
            if input_type == 'etrack':
                if verbose:
                    print(f"  Batch querying {len(input_ids)} Etrack assignees...")

                # Get all assignees in batched queries
                assignee_map = etrack_exec.get_etrack_assignees_batch(input_ids, verbose=verbose)

                if verbose:
                    print(f"  Found {sum(1 for v in assignee_map.values() if v)} assignees")

                # Now lookup emails for each
                for input_id in input_ids:
                    assignee = assignee_map.get(input_id)

                    if not assignee:
                        missing.append((input_id, None, 'No assignee'))
                        continue

                    # Lookup email from accounts database
                    account = db.get_account(etrack_user_id=assignee)

                    if not account:
                        missing.append((input_id, assignee, 'Account not found'))
                        continue

                    email_field = f"{email_type}_email"
                    email = account.get(email_field) or ''

                    if email:
                        results.append((input_id, assignee, email))
                    else:
                        missing.append((input_id, assignee, f'No {email_type} email'))

            elif input_type == 'user':
                # Direct username lookup - no etrack call needed
                for input_id in input_ids:
                    assignee = input_id
                    account = db.get_account(etrack_user_id=assignee)

                    if not account:
                        missing.append((input_id, assignee, 'Account not found'))
                        continue

                    email_field = f"{email_type}_email"
                    email = account.get(email_field) or ''

                    if email:
                        results.append((input_id, assignee, email))
                    else:
                        missing.append((input_id, assignee, f'No {email_type} email'))

            else:  # fi
                # FI type - need to get Etrack from Jira first, then batch query assignees
                # OPTIMIZED: Use batch JQL search to get Etrack IDs from all FIs at once
                fi_to_etrack = {}
                fi_missing = []

                if verbose:
                    print(f"  Batch fetching Etrack IDs from {len(input_ids)} FIs...")

                # Batch fetch Etrack IDs using JQL search
                etrack_field = 'customfield_33802'
                field_map = jira_client.get_field_batch(input_ids, etrack_field)

                for fi_id in input_ids:
                    etrack_id = field_map.get(fi_id)
                    if etrack_id:
                        fi_to_etrack[fi_id] = str(etrack_id).strip()
                    else:
                        fi_missing.append((fi_id, None, 'No Etrack linked' if fi_id in field_map else 'FI not found'))

                # Batch query assignees for all Etrack IDs
                etrack_ids = list(fi_to_etrack.values())
                if etrack_ids:
                    if verbose:
                        print(f"  Batch querying {len(etrack_ids)} Etrack assignees...")
                    assignee_map = etrack_exec.get_etrack_assignees_batch(etrack_ids, verbose=verbose)
                else:
                    assignee_map = {}

                # Now lookup emails
                for fi_id, etrack_id in fi_to_etrack.items():
                    assignee = assignee_map.get(etrack_id)

                    if not assignee:
                        missing.append((fi_id, None, 'No assignee'))
                        continue

                    account = db.get_account(etrack_user_id=assignee)

                    if not account:
                        missing.append((fi_id, assignee, 'Account not found'))
                        continue

                    email_field = f"{email_type}_email"
                    email = account.get(email_field) or ''

                    if email:
                        results.append((fi_id, assignee, email))
                    else:
                        missing.append((fi_id, assignee, f'No {email_type} email'))

                # Add FIs that had no Etrack
                missing.extend(fi_missing)

            # Output results
            print()
            sep = ';' if output_format == 'semi' else ','

            if output_format in ['csv', 'semi']:
                print(f"{type_label.lower()}_id{sep}assignee{sep}email")
                for input_id, assignee, email in results:
                    print(f"{input_id}{sep}{assignee}{sep}{email}")
                if include_missing:
                    for input_id, assignee, reason in missing:
                        print(f"{input_id}{sep}{assignee or ''}{sep}{reason}")
            elif output_format == 'simple':
                for input_id, assignee, email in results:
                    print(f"{input_id}\t{email}")
                if include_missing:
                    for input_id, assignee, reason in missing:
                        print(f"{input_id}\t# {reason}")
            else:  # table
                if results:
                    print(f"{type_label+' ID':<15} {'Assignee':<20} {email_type.capitalize()+' Email'}")
                    print("-" * 65)
                    for input_id, assignee, email in results:
                        print(f"{input_id:<15} {assignee:<20} {email}")

            # Summary
            print()
            print(f"Found: {len(results)}/{len(input_ids)}")
            if missing:
                print(f"Missing: {len(missing)}")
                if include_missing and output_format == 'table':
                    print()
                    print("Missing details:")
                    for input_id, assignee, reason in missing:
                        print(f"  {input_id}: {reason}" + (f" (assignee: {assignee})" if assignee else ""))

            # Outlook copy-paste format: all emails separated by semicolons (sorted, unique)
            if results:
                emails_only = sorted(set(email for _, _, email in results))
                print()
                print("Outlook (copy-paste):")
                print("; ".join(emails_only))

        elif command in ['help', '--help', '-h']:
            # Check if help for specific command requested
            help_command = sys.argv[2] if len(sys.argv) > 2 else None
            print_usage(help_command)

        elif command in ['config', 'info', 'settings']:
            # Show configuration and settings
            print("Account Manager - Configuration")
            print("=" * 60)

            # Database
            env_db = os.environ.get('ET_JR_ACCOUNTS_DB')
            module_dir = os.path.dirname(os.path.abspath(__file__))
            default_db = os.path.join(module_dir, "accounts.db")

            print("\nDatabase:")
            if env_db:
                print(f"  Path (from ET_JR_ACCOUNTS_DB): {env_db}")
                print(f"  Exists: {os.path.exists(env_db)}")
            else:
                print(f"  Path (default): {default_db}")
                print(f"  Exists: {os.path.exists(default_db)}")

            # Record count
            try:
                accounts = db.get_all_accounts()
                print(f"  Records: {len(accounts)}")
            except Exception:
                print("  Records: (unable to query)")

            # Module info
            print("\nModule:")
            print(f"  Directory: {module_dir}")

            # Environment variables
            print("\nEnvironment Variables:")
            env_vars = [
                ('ET_JR_ACCOUNTS_DB', 'Database path'),
                ('JIRA_SERVER_NAME', 'Jira server'),
                ('JIRA_ACC_TOKEN', 'Jira API token'),
                ('JIRA_PROJECT_KEY', 'Jira project'),
                ('RMTCMD_HOST', 'Remote command host'),
            ]
            for var, desc in env_vars:
                value = os.environ.get(var)
                if value:
                    # Mask sensitive values
                    if 'TOKEN' in var or 'PASSWORD' in var:
                        display = value[:4] + '****' + value[-4:] if len(value) > 8 else '****'
                    else:
                        display = value
                    print(f"  {var}: {display}")
                else:
                    print(f"  {var}: (not set) - {desc}")

            print()

        else:
            print(f"X Unknown command: {command}")
            print("\nAvailable commands: add, update, delete, get, list, list-incomplete,")
            print("                    list-pending-verify, search, translate, report,")
            print("                    export, import, export-log, import-log,")
            print("                    validate-fi, check-assignee, assign-etrack-fi,")
            print("                    update-emails, fetch-email, update-jira-ids,")
            print("                    fetch-jira-id, auto-update, update-verified,")
            print("                    update-notes, action-log, action-summary,")
            print("                    action-history, action-clear, lookup-etrack-emails,")
            print("                    config, demo, help")
            print("\nFor detailed help: python3 -m account_manager.cli help [command]")

    except DatabaseLockedError as e:
        print(f"X Database Error: {str(e)}")
        print("\nThe database is being used by another process.")
        print("Please wait a moment and try again, or check for other running processes.")
        sys.exit(1)

    except Exception as e:
        print(f"X Error: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
