# Account Manager

Multi-account tracking system for managing etrack ID, Veritas email, Cohesity email, Community account, Jira account, and more.

## Project Structure

```
account_manager/
├── __init__.py           # Package initialization
├── __main__.py           # Module entry point
├── models.py             # Core database models and CRUD operations
├── reports.py            # Report generation functionality
├── io_utils.py           # CSV import/export utilities
├── cli.py                # Command-line interface
├── jira_client.py        # JIRA API client
├── jira_integration.py   # JIRA ID auto-fetch logic
├── euserls_integration.py # euserls integration for Veritas emails/names
├── esql_integration.py   # esql query execution
├── etrack_integration.py # Etrack assignment (esql, eset)
├── fi_validator.py       # FI assignee validation
├── account_populator.py  # Auto-population strategies
└── README.md             # This file
```

## Installation

Requires Python 3.9+. Install dependencies:

```bash
pip install requests python-dotenv tabulate
```

## Environment Variables

```bash
# For JIRA integration
export JIRA_SERVER_NAME="your-jira-server.atlassian.net"
export JIRA_ACC_TOKEN="your-api-token"
export JIRA_PROJECT_KEY="FI"

# For remote euserls execution (optional)
export RMTCMD_HOST="remote-host"
```

## Usage

### Quick Start

```bash
cd /path/to/account_manager

# Run demo
python3 -m account_manager

# Get help
python3 -m account_manager.cli help
python3 -m account_manager.cli help <command>
```

### Command-Line Interface

```bash
# Account Management
python3 -m account_manager.cli add john_doe
python3 -m account_manager.cli update john_doe jira_account=john.doe
python3 -m account_manager.cli update john_doe first_name=John last_name=Doe
python3 -m account_manager.cli get john_doe
python3 -m account_manager.cli delete john_doe
python3 -m account_manager.cli list
python3 -m account_manager.cli list-incomplete

# Search and Translate
python3 -m account_manager.cli search cohesity_email=cohesity
python3 -m account_manager.cli translate john_doe jira_account

# Reports
python3 -m account_manager.cli report summary
python3 -m account_manager.cli report table
python3 -m account_manager.cli report table --show-notes
python3 -m account_manager.cli report compact
python3 -m account_manager.cli report markdown
python3 -m account_manager.cli report missing_fields

# Import/Export
python3 -m account_manager.cli export accounts.csv
python3 -m account_manager.cli import accounts.csv update
python3 -m account_manager.cli import accounts.csv update --allow-empty

# Auto-fetch Veritas emails and names (euserls)
python3 -m account_manager.cli update-emails --dry-run
python3 -m account_manager.cli update-emails
python3 -m account_manager.cli fetch-email john_doe

# Auto-fetch JIRA IDs (requires names)
python3 -m account_manager.cli update-jira-ids --dry-run
python3 -m account_manager.cli update-jira-ids
python3 -m account_manager.cli fetch-jira-id john_doe

# Manual verification status
python3 -m account_manager.cli update-verified john_doe yes
python3 -m account_manager.cli update-notes john_doe "Needs review"

# FI Validation
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix  # Fix mismatches
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report  # Generate report
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report-from=manager.name
python3 -m account_manager.cli check-assignee FI-12345

# Etrack and FI Assignment (requires verified account)
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --dry-run
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --mock

# Action Logs
python3 -m account_manager.cli action-log                          # View recent actions
python3 -m account_manager.cli action-log --status=failed          # View failed actions
python3 -m account_manager.cli action-summary                      # View statistics
python3 -m account_manager.cli action-summary --daily              # Daily breakdown
python3 -m account_manager.cli action-history account john_doe     # History for account
python3 -m account_manager.cli action-history fi FI-12345          # History for FI

# Email Lookup (batch)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt                  # From Etrack IDs
python3 -m account_manager.cli lookup-etrack-emails -f fis.txt --input=fi           # From FI IDs
python3 -m account_manager.cli lookup-etrack-emails -f users.txt --input=user       # From usernames
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --email=veritas  # Veritas email
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --format=semi    # Semicolon-separated
echo "123456" | python3 -m account_manager.cli lookup-etrack-emails                 # From stdin
```

## Features

### Core Operations
- **CRUD Operations**: Create, Read, Update, Delete accounts
- **Search**: Partial matching across all fields
- **Translate**: Convert between any account identifiers
- **Batch Operations**: Import/Export via CSV

### Auto-Population
- **euserls Integration**: Auto-fetch Veritas emails, first/last names, and derive community account
- **JIRA Integration**: Auto-fetch JIRA IDs using first/last name search, also fetches Cohesity email
- **Smart Disambiguation**: Handles multiple JIRA user matches using email prefix matching

### Etrack Assignment
- **assign-etrack-fi**: Assign etrack incident and linked FI to a user in one command
- **Safe Operation**: Only verified accounts (manual_verified = 'yes') can be used
- **External Reference Lookup**: Automatically finds FI linked to etrack (ext_src = TOOLS_AGILE)

### Email Lookup
- **lookup-etrack-emails**: Batch lookup emails from Etrack IDs, FI IDs, or usernames
- **Flexible Input**: Read from file or stdin
- **Output Formats**: Table, CSV, semicolon-separated, simple
- **Email Types**: Cohesity or Veritas emails
- **Dry Run Mode**: Preview changes before applying them

### Reports
- **Table Report**: Formatted table with all accounts
- **Summary Report**: Statistics and percentages
- **Missing Fields Report**: Incomplete records
- **Compact/Markdown**: Alternative formats
- **--show-notes**: Include notes column in reports
- **FI Reassignment Report**: Formatted report of FI mismatches (`--report`, `--report-from`)

### Action Logs
- **action-log**: View recent actions with filtering (--limit, --status, --type, --since)
- **action-summary**: View statistics by action type and success rate
- **action-history**: View all actions for specific target (account, fi, etrack)
- **action-clear**: Clear old log entries
- **Automatic Logging**: All add/update/delete/fix operations are logged

### Data Management
- **CSV Export**: Export all accounts to CSV
- **CSV Import**: Import with conflict handling (skip/update/fail)
- **--allow-empty**: Option to clear fields with empty CSV values
- **Database Lock Handling**: Automatic retry on database locks

### Verification & Notes
- **manual_verified**: Track whether account has been manually verified (yes/no)
- **notes**: Free-form text field for additional information

## Database Schema

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    etrack_user_id TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    veritas_email TEXT,
    cohesity_email TEXT,
    community_account TEXT,
    jira_account TEXT,
    manual_verified TEXT DEFAULT 'no',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,      -- add_account, update_account, fix_fi, assign_etrack, etc.
    target_type TEXT,               -- account, fi, etrack
    target_id TEXT,                 -- etrack_user_id, FI-12345, 1234567
    old_value TEXT,                 -- Previous value (for updates)
    new_value TEXT,                 -- New value (for updates)
    status TEXT DEFAULT 'success',  -- success, failed, skipped, dry_run
    details TEXT,                   -- Additional info or error message
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Reference

### AccountManager

- `add_account(etrack_user_id, **fields)` - Add new account
- `update_account(etrack_user_id, **fields)` - Update existing account
- `delete_account(etrack_user_id)` - Delete account
- `get_account(**field)` - Get single account by any field
- `search_accounts(**fields)` - Search with partial matching
- `translate(identifier, return_field)` - Convert between account forms
- `get_all_accounts()` - Retrieve all accounts

### ReportGenerator

- `generate_report(report_type, show_notes=False)` - Generate reports
  - Types: `'full'`, `'summary'`, `'missing_fields'`, `'table'`

### IOUtils

- `export_to_csv(filename)` - Export accounts to CSV
- `import_from_csv(filename, conflict_mode, allow_empty=False)` - Import accounts from CSV
  - Modes: `'skip'`, `'update'`, `'fail'`
  - allow_empty: If True, empty CSV values clear existing data

## Common Workflows

### New User Discovery
```bash
# 1. Discover users from FI validation
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

# 2. Auto-fetch Veritas emails and names
python3 -m account_manager.cli update-emails

# 3. Auto-fetch JIRA IDs (uses first/last names)
python3 -m account_manager.cli update-jira-ids

# 4. Review incomplete records
python3 -m account_manager.cli list-incomplete
python3 -m account_manager.cli report table --show-notes
```

### Etrack and FI Assignment
```bash
# 1. Ensure user exists and is verified
python3 -m account_manager.cli get user_one
python3 -m account_manager.cli update-verified user_one yes

# 2. Preview the assignment
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --dry-run

# 3. Execute the assignment
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one
```

### Bulk Data Update
```bash
# 1. Export current data
python3 -m account_manager.cli export accounts.csv

# 2. Edit CSV file with correct data

# 3. Import updates (preserves existing data)
python3 -m account_manager.cli import accounts.csv update

# 4. Or import and clear fields with empty values
python3 -m account_manager.cli import accounts.csv update --allow-empty
```

## License

Internal use only.
