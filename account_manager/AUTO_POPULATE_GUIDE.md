# Auto-Population Guide for Account Manager

## Overview

When validating FI assignees, we often discover new users who don't exist in the account database. This guide explains how to handle these situations and the various strategies available.

## Strategies for Handling Unknown Users

### 1. **SKIP** (Default - Safe)
```bash
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI
```

**Behavior:**
- Warns about missing accounts
- Continues validation
- No database modifications

**Use When:**
- First-time exploration
- Want to see what's missing before deciding
- Read-only analysis

**Output:**
```
⚠ Warning: No Jira account found for etrack_user_id 'john_doe' (skipping auto-population)
```

---

### 2. **AUTO** (Convenient - Recommended)
```bash
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add
```

**Behavior:**
- Automatically infers account details
- Adds to database without prompting
- Shows what was added

**Inference Rules:**
```
etrack_user_id:  john_doe (from esql output)
↓
jira_account:    john_doe (same as etrack_user_id)
veritas_email:   john.doe@vcompany.com (underscore → dot)
cohesity_email:  john.doe@ccompany.com (underscore → dot)
community_acct:  john_doe_community (adds suffix)
```

**Use When:**
- Batch processing many new users
- Trusting the inference logic
- Quick setup for initial data load

**Output:**
```
✓ Auto-populating account for 'john_doe':
  Etrack User ID: john_doe
  Jira Account:   john_doe
  Veritas Email:  john.doe@vcompany.com
  Cohesity Email: john.doe@ccompany.com
  Community Acct: john_doe_community
  Source:         inferred_from_etrack
  Confidence:     medium

✓ Added account for 'john_doe' to database
```

---

### 3. **INTERACTIVE** (Careful - Accurate)
```bash
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --interactive
```

**Behavior:**
- Shows inferred data
- Prompts for confirmation/correction
- Allows manual override

**Use When:**
- Want to verify each new user
- Have special cases (different email formats, etc.)
- Need high accuracy

**Interactive Prompt:**
```
============================================================
New User Detected: john_doe
============================================================
Please review and confirm the inferred account details:

Jira Account [john_doe]: ← Press Enter to accept or type new value
Veritas Email [john.doe@vcompany.com]:
Cohesity Email [john.doe@ccompany.com]:
Community Account [john_doe_community]:

✓ Added account for 'john_doe' to database
```

---

### 4. **FAIL** (Strict - Controlled)
```bash
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --fail-on-unknown
```

**Behavior:**
- Fails immediately when unknown user found
- No database modifications
- Forces you to handle manually

**Use When:**
- Production environment with strict controls
- All users should be pre-registered
- Want to catch unexpected users

**Output:**
```
✗ Error: Unknown user 'john_doe' and FAIL strategy is set
```

---

## Common Scenarios & Solutions

### Scenario 1: First Time Running Validation
**Problem:** Many unknown users, want to see what's needed

**Solution:**
```bash
# Step 1: Discover missing users (no changes)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI

# Step 2: Review warnings, then auto-populate
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add
```

---

### Scenario 2: Special Email Formats
**Problem:** Some users have different email patterns

**Solution:**
```bash
# Use interactive mode to correct as needed
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --interactive

# When prompted, override the inferred email:
Veritas Email [john.doe@vcompany.com]: john_doe@vcompany.com ← Type actual format
```

---

### Scenario 3: Bulk Import from CSV
**Problem:** Have user data in spreadsheet/CSV

**Solution:**
```bash
# Create CSV with all user data
# Format: etrack_user_id,veritas_email,cohesity_email,community_account,jira_account

python3 -m account_manager.cli import users.csv update
```

**Example CSV:**
```csv
etrack_user_id,veritas_email,cohesity_email,community_account,jira_account
john_doe,john.doe@vcompany.com,john.doe@ccompany.com,johndoe_comm,john.doe
jane_smith,j.smith@vcompany.com,jane.smith@ccompany.com,janesmith,jane.smith
```

---

### Scenario 4: Mixed - Some Known, Some Unknown
**Problem:** Running validation regularly, occasional new users

**Solution:**
```bash
# Auto-add new users as discovered
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

# Review newly added users
python3 -m account_manager.cli list
python3 -m account_manager.cli report table
```

---

### Scenario 5: Correcting Bad Inferences
**Problem:** Auto-add made mistakes

**Solution:**
```bash
# Update specific user
python3 -m account_manager.cli update john_doe
# Follow prompts to correct fields

# Or export, fix in spreadsheet, re-import
python3 -m account_manager.cli export users.csv
# Edit users.csv
python3 -m account_manager.cli import users.csv update
```

---

## Inference Logic Details

### Username to Email Conversion
```
Input Pattern     → Veritas Email          → Cohesity Email
john_doe          → john.doe@vcompany.com   → john.doe@ccompany.com
jane.smith        → jane.smith@vcompany.com → jane.smith@ccompany.com
bob-jones         → bob-jones@vcompany.com  → bob-jones@ccompany.com
```

**Rule:** Underscore (_) converted to dot (.), otherwise unchanged

### Jira Account Mapping
```
etrack_user_id: john_doe
→ jira_account: john_doe (direct copy)
```

**Rule:** Assumes Jira username matches etrack_user_id

### Community Account
```
etrack_user_id: john_doe
→ community_account: john_doe_community (adds _community suffix)
```

---

## Validation Workflow

### Complete Workflow Example:

```bash
# 1. Check RMTCMD_HOST is set (for esql)
echo $RMTCMD_HOST

# 2. Check Jira credentials (.env file)
cat .env | grep JIRA

# 3. First run - discover issues (read-only)
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI

# 4. Auto-populate missing users
python3 -m account_manager.cli validate-fi RptTerm_Open_SRs_With_Ext_Ref_FI --auto-add

# 5. Review newly added accounts
python3 -m account_manager.cli report table

# 6. Export for record-keeping
python3 -m account_manager.cli export accounts_$(date +%Y%m%d).csv

# 7. Check specific FI
python3 -m account_manager.cli check-assignee FI-59131
```

---

## Troubleshooting

### Problem: Email format is wrong
**Symptom:** Inferred `john.doe@vcompany.com` but actual is `john_doe@vcompany.com`

**Fix:**
```bash
# Option 1: Update manually
python3 -m account_manager.cli update john_doe

# Option 2: Use interactive mode next time
python3 -m account_manager.cli validate-fi Query --interactive
```

---

### Problem: Jira account differs from etrack_user_id
**Symptom:** etrack_user_id is `john_doe` but Jira is `jdoe`

**Fix:**
```bash
# Update jira_account field
python3 -m account_manager.cli update john_doe
# When prompted for Jira Account: jdoe
```

---

### Problem: Confidence level shows "low"
**Meaning:** Data was inferred with less certainty

**Action:**
```bash
# Verify and update if needed
python3 -m account_manager.cli get john_doe
python3 -m account_manager.cli update john_doe  # Correct any fields
```

---

### Problem: Don't want auto-population, need manual control
**Solution:**
```bash
# Use SKIP mode (default)
python3 -m account_manager.cli validate-fi Query

# Then manually add each user
python3 -m account_manager.cli add john_doe
# Or prepare CSV with correct data
python3 -m account_manager.cli import correct_users.csv
```

---

## Best Practices

### For Initial Setup:
1. Use `--interactive` for first batch of users
2. Export to CSV for backup
3. Switch to `--auto-add` for subsequent runs

### For Production:
1. Pre-populate database from HR/LDAP system
2. Use `--fail-on-unknown` to catch unexpected users
3. Regular exports for disaster recovery

### For Development/Testing:
1. Use `--mock` flag to test without Jira
2. Use `--auto-add` for quick iteration
3. Delete accounts.db and regenerate as needed

---

## Data Sources Priority

When multiple sources available:

1. **Manual Entry** (highest confidence)
   - User explicitly provided data
   - Confidence: HIGH

2. **Jira API** (high confidence)
   - Fetched from Jira user profile
   - Confidence: HIGH

3. **LDAP/Active Directory** (high confidence)
   - Corporate directory
   - Confidence: HIGH

4. **Inferred from etrack_user_id** (medium confidence)
   - Pattern-based guessing
   - Confidence: MEDIUM

5. **Default/Placeholder** (low confidence)
   - Fallback values
   - Confidence: LOW

---

## Future Enhancements

Planned improvements:

1. **LDAP Integration**
   - Fetch emails from Active Directory
   - Higher confidence than inference

2. **Jira User API**
   - Get full user profile from Jira
   - Email, display name, etc.

3. **Bulk Validation**
   - Validate all inferred data against external source
   - Mark confidence levels

4. **Audit Trail**
   - Track when accounts were added
   - Who approved them
   - Source of data

---

## Quick Reference

```bash
# Just check (no changes)
validate-fi Query

# Auto-populate new users
validate-fi Query --auto-add

# Confirm each new user
validate-fi Query --interactive

# Fail on unknown users
validate-fi Query --fail-on-unknown

# Test without Jira
validate-fi Query --mock

# Combine options
validate-fi Query --auto-add --mock

# Filter query to SERVICE_REQUEST incidents only
validate-fi Query --perform-sr-type-check

# Single or multiple FIs (defaults to SERVICE_REQUEST only)
validate-fi --fi=FI-59131
validate-fi --fi=FI-59131,FI-59132,FI-59133

# Single or multiple incidents (comma-separated)
validate-fi --incident=1234567,1234568

# FI(s) with all incident types
validate-fi --fi=FI-59131 --all-types
```

---

## Summary

**Choose your strategy based on:**

| Strategy      | Safety | Speed | Accuracy | Use Case                    |
|---------------|--------|-------|----------|-----------------------------|
| SKIP          | ✓✓✓   | ✓✓✓   | N/A      | Discovery, read-only        |
| AUTO          | ✓✓    | ✓✓✓   | ✓✓       | Batch processing, trusted   |
| INTERACTIVE   | ✓✓✓   | ✓     | ✓✓✓      | Careful review, special cases|
| FAIL          | ✓✓✓   | ✓✓    | N/A      | Production, strict control  |

**Recommendation:** Start with **INTERACTIVE** for first few users, then switch to **AUTO** for regular operations.
