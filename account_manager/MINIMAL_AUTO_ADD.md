# Quick Reference: Auto-Add Minimal Accounts

## Updated Behavior

### AUTO MODE (`--auto-add`)
Now adds **ONLY etrack_user_id**, leaves all other fields empty for manual update later.

```bash
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add
```

**What gets added:**
```
etrack_user_id:    john_doe   ← From esql
jira_account:      NULL       ← Empty - update later
veritas_email:     NULL       ← Empty - update later
cohesity_email:    NULL       ← Empty - update later
community_account: NULL       ← Empty - update later
```

---

## Workflow

### Step 1: Auto-Add Minimal Accounts
```bash
# Run validation with --auto-add
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add
```

**Output:**
```
✓ Auto-adding minimal account for 'john_doe' (fields left empty for later update)
✓ Added account for 'john_doe' (update later with: cli.py update john_doe)

✓ Auto-adding minimal account for 'jane_smith' (fields left empty for later update)
✓ Added account for 'jane_smith' (update later with: cli.py update jane_smith)
```

---

### Step 2: List Incomplete Accounts
```bash
python3 -m account_manager.cli list-incomplete
```

**Output:**
```
Found 2 incomplete accounts:

================================================================================

Etrack User ID: john_doe
  Missing fields: jira_account, veritas_email, cohesity_email, community_account
  Current values:
    Jira:      (empty)
    Veritas:   (empty)
    Cohesity:  (empty)
    Community: (empty)
  To update: python3 -m account_manager.cli update john_doe

Etrack User ID: jane_smith
  Missing fields: jira_account, veritas_email, cohesity_email, community_account
  Current values:
    Jira:      (empty)
    Veritas:   (empty)
    Cohesity:  (empty)
    Community: (empty)
  To update: python3 -m account_manager.cli update jane_smith

================================================================================

Total incomplete: 2 / 2

To see details: python3 -m account_manager.cli report missing_fields
```

---

### Step 3: Update Individual Accounts

#### Option A: Interactive Update
```bash
python3 -m account_manager.cli update john_doe
```

You'll be prompted for each field:
```
Veritas Email [current: None]: john.doe@vcompany.com
Cohesity Email [current: None]: john.doe@ccompany.com
Community Account [current: None]: john.doe
Jira Account [current: None]: john.doe
```

#### Option B: Direct Update (Command Line)
```bash
python3 -m account_manager.cli update john_doe \
  jira_account=john.doe \
  veritas_email=john.doe@vcompany.com \
  cohesity_email=john.doe@ccompany.com \
  community_account=john.doe
```

---

### Step 4: Verify Updates
```bash
# Check specific account
python3 -m account_manager.cli get john_doe

# List all incomplete (should be fewer now)
python3 -m account_manager.cli list-incomplete

# Generate report
python3 -m account_manager.cli report missing_fields
```

---

## Bulk Update Methods

### Method 1: Export → Edit → Import
```bash
# 1. Export incomplete accounts to CSV
python3 -m account_manager.cli export incomplete_accounts.csv

# 2. Edit CSV file in spreadsheet/editor
#    Fill in missing fields

# 3. Import back with 'update' mode
python3 -m account_manager.cli import incomplete_accounts.csv update
```

### Method 2: Script Multiple Updates
```bash
# Create a shell script
cat > update_accounts.sh << 'EOF'
#!/bin/bash
python3 -m account_manager.cli update john_doe \
  jira_account=john.doe \
  veritas_email=john.doe@vcompany.com \
  cohesity_email=john.doe@ccompany.com \
  community_account=john.doe

python3 -m account_manager.cli update jane_smith \
  jira_account=j.smith \
  veritas_email=jane.smith@vcompany.com \
  cohesity_email=jane.smith@ccompany.com \
  community_account=jane.smith
EOF

chmod +x update_accounts.sh
./update_accounts.sh
```

---

## Comparison: AUTO vs INTERACTIVE

| Mode        | etrack_user_id | Other Fields | User Action Required |
|-------------|----------------|--------------|---------------------|
| **AUTO**    | ✓ Added        | Empty (NULL) | Update later manually|
| **INTERACTIVE** | ✓ Added    | Prompted     | Confirm during add  |

### When to use AUTO:
- ✓ Batch processing many users
- ✓ Will update fields later from spreadsheet
- ✓ Want to quickly populate etrack_user_id
- ✓ Have separate data source for emails

### When to use INTERACTIVE:
- ✓ Few new users
- ✓ Know the correct values now
- ✓ Want complete records immediately
- ✓ Don't want to update later

---

## Complete Example Workflow

```bash
# 1. Run validation with auto-add (creates minimal accounts)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

# 2. Export to CSV for bulk edit
python3 -m account_manager.cli export accounts_to_update.csv

# 3. Edit CSV file (add correct emails, jira accounts, etc.)
# Use Excel, Google Sheets, or text editor

# 4. Import updated CSV
python3 -m account_manager.cli import accounts_to_update.csv update

# 5. Verify - should show "All accounts are complete!"
python3 -m account_manager.cli list-incomplete

# 6. Re-run validation - should now have all data
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI
```

---

## Available Commands

### List Commands
```bash
# List all accounts
python3 -m account_manager.cli list

# List only incomplete accounts (missing fields)
python3 -m account_manager.cli list-incomplete

# Show detailed missing fields report
python3 -m account_manager.cli report missing_fields
```

### Update Commands
```bash
# Interactive update (prompts for each field)
python3 -m account_manager.cli update <etrack_user_id>

# Direct update (command line)
python3 -m account_manager.cli update <etrack_user_id> field=value field2=value2

# Get current values
python3 -m account_manager.cli get <etrack_user_id>
```

### Bulk Operations
```bash
# Export for editing
python3 -m account_manager.cli export <filename.csv>

# Import with updates
python3 -m account_manager.cli import <filename.csv> update
```

---

## Tips

1. **Use CSV for bulk updates**: Easier to edit many accounts at once
2. **Check list-incomplete regularly**: See what needs attention
3. **Keep a master CSV**: Export regularly as backup
4. **Use update mode on import**: Won't fail if account exists, just updates
5. **Verify before validation**: Run `list-incomplete` before FI validation to ensure data is ready

---

## Summary

**New AUTO mode behavior:**
- ✓ Adds etrack_user_id only
- ✓ Leaves other fields empty (NULL)
- ✓ Fast batch processing
- ✓ Update later at your convenience

**Best practice:**
1. Use `--auto-add` to discover new users
2. Export to CSV
3. Fill in correct data
4. Import back
5. Run validation again
