# Account Manager CLI - Quick Cheatsheet

## Get Help
```bash
# General help
python3 -m account_manager.cli help

# Command-specific help
python3 -m account_manager.cli help <command>

# Available: help add, help update, help import, help import-log, help export-log, help validate-fi, help report, help list
```

---

## Account Management

### Add Account (Minimal)
```bash
python3 -m account_manager.cli add john_doe
```

### Update Account
```bash
# Interactive (prompts)
python3 -m account_manager.cli update john_doe

# Direct update
python3 -m account_manager.cli update john_doe jira_account=john.doe veritas_email=john.doe@vcompany.com
```

### View Account
```bash
python3 -m account_manager.cli get john_doe
```

### Delete Account
```bash
python3 -m account_manager.cli delete john_doe
```

---

## Viewing Data

### List Accounts
```bash
python3 -m account_manager.cli list                # All accounts
python3 -m account_manager.cli list-incomplete     # Missing fields only
```

### Search
```bash
python3 -m account_manager.cli search jira_account=john.doe
python3 -m account_manager.cli search cohesity_email=cohesity.com
```

### Reports
```bash
python3 -m account_manager.cli report summary         # Statistics
python3 -m account_manager.cli report table           # Formatted table
python3 -m account_manager.cli report missing_fields  # Incomplete accounts
python3 -m account_manager.cli report full            # Complete details
python3 -m account_manager.cli report compact         # Compact table
python3 -m account_manager.cli report markdown        # Markdown format
```

### Translation
```bash
python3 -m account_manager.cli translate john_doe jira_account
python3 -m account_manager.cli translate john.doe@vcompany.com etrack_user_id
```

---

## Import/Export

### Export Accounts
```bash
python3 -m account_manager.cli export accounts.csv
```

### Import Accounts
```bash
python3 -m account_manager.cli import accounts.csv         # Skip existing
python3 -m account_manager.cli import accounts.csv update  # Update existing
python3 -m account_manager.cli import accounts.csv fail    # Fail if exists
```

### Export Action Log
```bash
python3 -m account_manager.cli export-log                    # All entries
python3 -m account_manager.cli export-log actions.csv        # To specific file
python3 -m account_manager.cli export-log --limit=100        # Last 100 entries
python3 -m account_manager.cli export-log --since=2026-01-01 # Since date
```

### Import Action Log
```bash
python3 -m account_manager.cli import-log actions_backup.csv
```

---

## FI Validation

### Basic Validation
```bash
# Warn only (no changes)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI

# Auto-add missing users (minimal)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

# Interactive (confirm each)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --interactive

# Test mode (no Jira)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --mock

# Strict mode (fail on unknown)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fail-on-unknown

# Fix mismatches (verified accounts only)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix

# Preview fixes without applying (dry-run)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix --dry-run

# Fix only FIs assigned to manager (reassign from manager to correct engineer)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix-from=manager.name

# Interactive fix (prompt y/n/q for each)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix --fix-interactive

# Skip specific FIs during fix
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fix --skip-fi=FI-12345,FI-67890
```
**Note:** `--fix` only updates FIs for accounts with `manual_verified=yes`

### Generate Reassignment Report
```bash
# Generate formatted report of all mismatches
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report

# Generate report for FIs currently assigned to specific user
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --report-from=deepak.tanksale
```

### Show FIs with Conflicting Assignees
```bash
# FIs linked to multiple Etracks with different assignees (detailed format)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --show-conflicts

# Table format
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --show-conflicts --table
```

### Check Single FI
```bash
python3 -m account_manager.cli check-assignee FI-59131
```

### Assign Etrack and FI
```bash
# Assign etrack to user and update linked FI in Jira
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one

# Preview what would be done (no changes)
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --dry-run

# Test mode (no API calls)
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --mock

# With verbose debugging
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --verbose
```
**Note:** Requires verified account (manual_verified = 'yes')

---

## Veritas Email Update (euserls)

### Update Missing Emails
```bash
# Preview what will be updated
python3 -m account_manager.cli update-emails --dry-run

# Update all missing emails
python3 -m account_manager.cli update-emails

# With detailed progress
python3 -m account_manager.cli update-emails --verbose
```

### Fetch Single Email
```bash
# Fetch and update
python3 -m account_manager.cli fetch-email john_doe

# Just show the email
python3 -m account_manager.cli fetch-email john_doe --dry-run
```

---

## Email Lookup (Batch)

### From Etrack IDs
```bash
# From file (one Etrack ID per line)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt

# From stdin
echo -e "123456\n789012" | python3 -m account_manager.cli lookup-etrack-emails
```

### From FI IDs
```bash
# From file (one FI-xxx per line)
python3 -m account_manager.cli lookup-etrack-emails -f fis.txt --input=fi

# From stdin
echo -e "FI-58985\nFI-59001" | python3 -m account_manager.cli lookup-etrack-emails --input=fi
```

### From Usernames (Direct)
```bash
# From file (one username per line)
python3 -m account_manager.cli lookup-etrack-emails -f users.txt --input=user
```

### Output Formats
```bash
# Table (default)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt

# CSV (comma-separated)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --format=csv

# Semicolon-separated (for Excel locales)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --format=semi

# Simple (tab-separated ID and email only)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --format=simple
```

### Email Type
```bash
# Cohesity email (default)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt

# Veritas email
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --email=veritas
```

### Options
```bash
# Include missing/failed lookups in output
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --include-missing

# Verbose (show progress)
python3 -m account_manager.cli lookup-etrack-emails -f etracks.txt --verbose
```

---

## Action Logs

### View Recent Actions
```bash
# View last 50 actions
python3 -m account_manager.cli action-log

# View with limit
python3 -m account_manager.cli action-log --limit=20

# Filter by status
python3 -m account_manager.cli action-log --status=failed
python3 -m account_manager.cli action-log --status=success

# Filter by action type
python3 -m account_manager.cli action-log --type=fix_fi
python3 -m account_manager.cli action-log --type=assign_etrack

# Filter by date
python3 -m account_manager.cli action-log --since=2026-02-01
```

### Action Summary
```bash
# Overall statistics
python3 -m account_manager.cli action-summary

# Since specific date
python3 -m account_manager.cli action-summary --since=2026-02-01

# Daily activity breakdown (last 7 days)
python3 -m account_manager.cli action-summary --daily
```

### Action History for Target
```bash
# History for specific account
python3 -m account_manager.cli action-history account john_doe

# History for specific FI
python3 -m account_manager.cli action-history fi FI-58985

# History for specific etrack
python3 -m account_manager.cli action-history etrack 1234567
```

### Clear Action Log
```bash
# Clear entries older than 30 days
python3 -m account_manager.cli action-clear --before=2026-01-12

# Clear all (prompts for confirmation)
python3 -m account_manager.cli action-clear --all
```

---

## Common Workflows

### Workflow 1: Discover and Update New Users
```bash
# Step 1: Discover new users
python3 -m account_manager.cli validate-fi Query --auto-add

# Step 2: Auto-update Veritas emails
python3 -m account_manager.cli update-emails

# Step 3: See what else needs updating
python3 -m account_manager.cli list-incomplete

# Step 4: Update remaining fields (choose one)
# Option A: Update individually
python3 -m account_manager.cli update john_doe

# Option B: Export, edit, import
python3 -m account_manager.cli export incomplete.csv
# Edit CSV file
python3 -m account_manager.cli import incomplete.csv update

# Step 5: Verify
python3 -m account_manager.cli list-incomplete
python3 -m account_manager.cli validate-fi Query
```

### Workflow 2: Bulk Import
```bash
# Prepare CSV with all data
python3 -m account_manager.cli import users.csv update
python3 -m account_manager.cli report summary
```

### Workflow 3: Find User Information
```bash
# By etrack_user_id
python3 -m account_manager.cli get john_doe

# By Jira account
python3 -m account_manager.cli search jira_account=john.doe

# Translate between IDs
python3 -m account_manager.cli translate john.doe@vcompany.com jira_account
```

### Workflow 4: Assign Etrack and FI to User
```bash
# Step 1: Ensure user is verified
python3 -m account_manager.cli get user_one
python3 -m account_manager.cli update-verified user_one yes

# Step 2: Preview (dry-run)
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --dry-run

# Step 3: Execute
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one

# Note: This assigns both the etrack (via eset) and the linked FI (via Jira API)
```

---

## Options Quick Reference

### validate-fi Options
| Option | Description |
|--------|-------------|
| (none) | SKIP - Warn only, no changes (DEFAULT) |
| --auto-add | AUTO - Add etrack_user_id only |
| --interactive | INTERACTIVE - Prompt for all fields |
| --fail-on-unknown | FAIL - Stop on unknown user |
| --mock | Use mock Jira (testing) |
| --fix | Fix mismatches for verified accounts |
| --dry-run | With --fix: preview without changes |
| --fix-interactive | With --fix: prompt y/n/q each |
| --fix-from=USER | Only fix FIs assigned to USER (implies --fix) |
| --skip-fi=IDS | With --fix: skip comma-separated FI IDs |
| --show-conflicts | Show FIs linked to multiple incidents with different assignees |
| --table | With --show-conflicts: display in table format |
| --incident=NO | Validate single incident by number |
| --fi=ID | Validate single FI by ID (e.g., FI-59131 or 59131) |
| --report | Generate formatted reassignment report (no fixes) |
| --report-from=USER | Generate report for FIs currently assigned to USER |

### assign-etrack-fi Options
| Option | Description |
|--------|-------------|
| --dry-run | Show what would be done (no changes) |
| --mock | Use mock clients (testing) |
| --verbose | Show detailed debug information |

**Requirements:** Account must have jira_account and manual_verified = 'yes'

### import Modes
| Mode | Description |
|------|-------------|
| skip | Skip existing (DEFAULT) |
| update | Update existing |
| fail | Fail if exists |

### report Types
| Type | Description |
|------|-------------|
| full | Complete details |
| summary | Statistics |
| missing_fields | Incomplete accounts |
| table | Formatted table |
| compact | Compact table |
| markdown | Markdown format |

---

## Environment Setup

### Required Environment Variables
```bash
# For esql (remote execution)
export RMTCMD_HOST=user@hostname

# For Jira API
export JIRA_SERVER_NAME=your-jira-server.atlassian.net
export JIRA_ACC_TOKEN=your_bearer_token
export JIRA_PROJECT_KEY=FI
```

### Create .env file
```bash
cat > .env << 'EOF'
RMTCMD_HOST=user@hostname.example.com
JIRA_SERVER_NAME=your-company.atlassian.net
JIRA_ACC_TOKEN=your_token_here
JIRA_PROJECT_KEY=FI
EOF
```

---

## Tips

1. **Always use help**: `python3 -m account_manager.cli help <command>`
2. **Check incomplete regularly**: `list-incomplete` shows what needs attention
3. **Use CSV for bulk**: Faster than individual updates
4. **Test with --mock**: Validate workflow without Jira access
5. **Export often**: Keep backups with `export accounts.csv` and `export-log actions.csv`

---

## Keyboard Shortcuts (when running commands)

- `Ctrl+C` - Cancel current operation
- `Enter` - Accept default value (in interactive mode)
- Type value + `Enter` - Override default

---

## Troubleshooting

### "Unknown command" error
```bash
python3 -m account_manager.cli help   # See all commands
```

### "Account not found"
```bash
python3 -m account_manager.cli list   # Check if account exists
python3 -m account_manager.cli add <id>  # Add if missing
```

### "esql command not found"
```bash
# Check RMTCMD_HOST is set
echo $RMTCMD_HOST

# Should output: user@hostname
```

### "Jira connection failed"
```bash
# Check credentials
echo $JIRA_SERVER_NAME
echo $JIRA_ACC_TOKEN

# Test without Jira
python3 -m account_manager.cli validate-fi Query --mock
```

### "Account is not verified" (assign-etrack-fi)
```bash
# Check account status
python3 -m account_manager.cli get user_one

# Verify the account
python3 -m account_manager.cli update-verified user_one yes
```

### "No FI found" (assign-etrack-fi)
```bash
# Use verbose mode to debug
python3 -m account_manager.cli assign-etrack-fi 1234567 user_one --verbose

# Check if etrack has external reference with ext_src=TOOLS_AGILE
```

---

## Remember

- **add** = minimal account (etrack_user_id only)
- **update** = fill in the details
- **list-incomplete** = see what needs updating
- **--auto-add** = quick discovery, update later
- **--interactive** = careful entry, complete now
- **assign-etrack-fi** = assign etrack + FI (requires verified account)
- **help <command>** = detailed documentation
