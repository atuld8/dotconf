# Veritas Email Auto-Update Guide

## Overview

The `euserls` integration automatically fetches Veritas email addresses from the etrack system for accounts with missing `veritas_email` fields. This eliminates manual data entry and ensures accurate email addresses directly from the source system.

## How It Works

The `euserls` command is a Veritas etrack utility that retrieves user information:

```bash
$ euserls john_doe
---------------------------------------------------------------
Login           First Last            Phone          Pager          Active
===============================================================================

john_doe        John Doe          XXX-XXX-XXXX                  Active
Email:  john.doe@vcompany.com
```

The integration:
1. Identifies accounts with missing `veritas_email`
2. Executes `euserls <etrack_user_id>` for each account
3. Parses the output to extract the email address
4. Updates the database with the fetched email

## Prerequisites

### Option 1: Local euserls Command
The `euserls` command must be available in your PATH:
```bash
$ which euserls
/usr/bin/euserls
```

### Option 2: Remote Execution via SSH
If `euserls` is not available locally, set `RMTCMD_HOST` to execute it remotely:
```bash
export RMTCMD_HOST=user@hostname
```

The integration will automatically use SSH when the local command is not found.

## Commands

### 1. Update All Missing Emails

Update all accounts with missing `veritas_email`:

```bash
# Preview what will be updated (dry run)
python3 -m account_manager.cli update-emails --dry-run

# Actually update the accounts
python3 -m account_manager.cli update-emails

# Show detailed progress
python3 -m account_manager.cli update-emails --verbose
```

**Example Output:**
```
Updating Missing Veritas Emails
============================================================
Fetching email for john_doe...
Updated john_doe: veritas_email=john.doe@vcompany.com
Fetching email for jane_smith...
Updated jane_smith: veritas_email=jane.smith@vcompany.com
Skipping bob_wilson: email already set (bob.wilson@vcompany.com)

============================================================
SUMMARY
============================================================
Accounts needing update: 2
Successfully updated: 2
Failed: 0
Already had email: 1

✓ Updated 2 accounts
Run 'list-incomplete' to see remaining missing fields
```

### 2. Fetch Single Email

Fetch and update email for a specific user:

```bash
# Fetch and update
python3 -m account_manager.cli fetch-email john_doe

# Just show the email (don't update)
python3 -m account_manager.cli fetch-email john_doe --dry-run
```

**Example Output:**
```
Fetching email for: john_doe
============================================================
Fetching email for john_doe...
Updated john_doe: veritas_email=john.doe@vcompany.com

✓ Account updated:
  Etrack User ID: john_doe
  Veritas Email:  john.doe@vcompany.com
```

## Integration with Workflows

### Complete Workflow: Discover → Update Emails → Fill Remaining Fields

```bash
# Step 1: Discover new users from FI validation
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

# Step 2: Auto-update Veritas emails
python3 -m account_manager.cli update-emails

# Step 3: Check what still needs updating
python3 -m account_manager.cli list-incomplete

# Step 4: Update remaining fields manually or via CSV
python3 -m account_manager.cli update john_doe cohesity_email=john.doe@ccompany.com
```

### Preview Before Committing

Always use `--dry-run` first to see what will be updated:

```bash
# Preview
python3 -m account_manager.cli update-emails --dry-run

# Review the output, then apply
python3 -m account_manager.cli update-emails
```

## Error Handling

### euserls Command Not Found

**Error:**
```
✗ Error: euserls command not found locally and RMTCMD_HOST not set.
```

**Solutions:**
1. Install euserls locally and ensure it's in your PATH
2. Set RMTCMD_HOST for remote execution:
   ```bash
   export RMTCMD_HOST=user@hostname.example.com
   ```

### User Not Found in etrack

If a user doesn't exist in the etrack system, the command will fail gracefully:

```
Warning: euserls command failed for unknown_user
Failed to fetch email for unknown_user
```

The command continues processing other users.

### Account Not in Database

Before fetching an email, the account must exist:

```bash
# This will fail if john_doe doesn't exist
python3 -m account_manager.cli fetch-email john_doe

# Add the account first
python3 -m account_manager.cli add john_doe

# Now fetch the email
python3 -m account_manager.cli fetch-email john_doe
```

## Examples

### Example 1: Update All Missing Emails

```bash
$ python3 -m account_manager.cli update-emails --verbose
Updating Missing Veritas Emails
============================================================
Fetching email for alice_jones...
Updated alice_jones: veritas_email=alice.jones@vcompany.com
Fetching email for bob_smith...
Updated bob_smith: veritas_email=bob.smith@vcompany.com
Skipping charlie_brown: email already set (charlie.brown@vcompany.com)

============================================================
SUMMARY
============================================================
Accounts needing update: 2
Successfully updated: 2
Failed: 0
Already had email: 1

✓ Updated 2 accounts
```

### Example 2: Dry Run

```bash
$ python3 -m account_manager.cli update-emails --dry-run
Updating Missing Veritas Emails
============================================================
DRY RUN MODE - No changes will be made
============================================================
Would update john_doe: veritas_email=john.doe@vcompany.com
Would update jane_smith: veritas_email=jane.smith@vcompany.com

============================================================
SUMMARY
============================================================
Accounts needing update: 2
Successfully updated: 2
Failed: 0
Already had email: 0

Run without --dry-run to apply updates
```

### Example 3: Fetch Single Email

```bash
$ python3 -m account_manager.cli fetch-email john_doe
Fetching email for: john_doe
============================================================
Fetching email for john_doe...
Updated john_doe: veritas_email=john.doe@vcompany.com

✓ Account updated:
  Etrack User ID: john_doe
  Veritas Email:  john.doe@vcompany.com
```

### Example 4: Remote Execution

```bash
# Set remote host
$ export RMTCMD_HOST=user@hostname.example.com

# Update emails (will use SSH)
$ python3 -m account_manager.cli update-emails
Updating Missing Veritas Emails
============================================================
Fetching email for john_doe...
Updated john_doe: veritas_email=john.doe@vcompany.com
```

## Statistics and Reporting

After updating emails, use these commands to verify:

```bash
# Show accounts still missing data
python3 -m account_manager.cli list-incomplete

# Generate summary report
python3 -m account_manager.cli report summary

# View specific account
python3 -m account_manager.cli get john_doe
```

## Programmatic Usage

You can also use the integration in your own Python scripts:

```python
from account_manager.models import AccountManager
from account_manager.euserls_integration import EuserlsUpdater

# Initialize
db = AccountManager("accounts.db")
updater = EuserlsUpdater(db, verbose=True)

# Update all missing emails
stats = updater.update_missing_emails(dry_run=False)
print(f"Updated {stats['updated']} accounts")

# Update single account
success = updater.update_single_account("john_doe")

db.close()
```

## Tips

1. **Always dry-run first**: Use `--dry-run` to preview changes before applying them

2. **Use with validate-fi**: Combine with FI validation for a complete workflow:
   ```bash
   python3 -m account_manager.cli validate-fi Query --auto-add
   python3 -m account_manager.cli update-emails
   ```

3. **Batch processing**: The `update-emails` command processes all missing emails in one go

4. **Error resilience**: If some users fail, the command continues processing others

5. **Remote execution**: Use `RMTCMD_HOST` if euserls is only available on specific servers

6. **Verbose output**: Use `--verbose` to see detailed progress and troubleshoot issues

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Command not found | Install euserls or set RMTCMD_HOST |
| Permission denied | Check SSH access to RMTCMD_HOST |
| Timeout | Increase timeout in euserls_integration.py |
| Parse error | Check euserls output format hasn't changed |
| Account not found | User doesn't exist in etrack system |

## See Also

- [CHEATSHEET.md](CHEATSHEET.md) - Quick reference for all commands
- [README.md](README.md) - Complete account manager documentation
- [MINIMAL_AUTO_ADD.md](MINIMAL_AUTO_ADD.md) - Minimal auto-add workflow
