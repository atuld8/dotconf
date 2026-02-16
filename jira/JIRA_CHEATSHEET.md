# Jira Tools Cheatsheet

Quick reference for all Jira-related scripts and utilities.

## Environment Setup

```bash
# Required environment variables
export JIRA_SERVER_NAME="your-jira-server.atlassian.net"
export JIRA_ACC_TOKEN="your_api_token"
export JIRA_PROJECT_KEY="FI"
export JIRA_EPIC_LINK="EPIC-1234"        # Default epic for linking
export JIRA_WATCHERS_LIST="user1 user2"  # Default watchers
```

---

## Reporting & Query Tools

### j.et.rpt.py (Primary Report Generator)
Bulk Jira report generator with Etrack/Case integration and analysis.

```bash
# From JQL query
j.et.rpt.py -where "project = FI AND status = Open"

# From file (list of issue IDs)
j.et.rpt.py -f issues.txt

# Custom fields
j.et.rpt.py -where "assignee = currentUser()" --fields key,summary,status,assignee,etrack

# Analysis mode (categorizes by Jira/Etrack/Case status)
j.et.rpt.py -where "..." --analyze

# Output formats
j.et.rpt.py -f issues.txt --csv output.csv
j.et.rpt.py -f issues.txt --json output.json
j.et.rpt.py -f issues.txt --markdown

# With colors and without truncation
j.et.rpt.py -where "..." --color --notruncate
```

### j.printJQLResultInTableFormat..oJql.py
Execute JQL and display results in table format.

```bash
# Basic JQL query
j.printJQLResultInTableFormat..oJql.py "project = FI AND status = Open"

# Exclude columns
j.printJQLResultInTableFormat..oJql.py "project = FI" --excludeCols Summary,Labels
```

### j.sprintBoard.py
Display issues in Kanban-style sprint board.

```bash
# Basic sprint board
j.sprintBoard.py -q "project = FI AND sprint in openSprints()"

# Include sub-tasks
j.sprintBoard.py -q "project = FI AND type in (Story, Defect)" -s
```

### j.jql.generate_reports.py
Generate summary reports from table input (status, priority counts).

```bash
# Pipe from another JQL output
j.printJQLResultInTableFormat..oJql.py "project = FI" | j.jql.generate_reports.py
```

### j.jql.generate_hierarchical_report.py
Generate hierarchical reports grouped by assignee/reporter.

```bash
# Generate report grouped by assignee
j.printJQLResultInTableFormat..oJql.py "project = FI" | j.jql.generate_hierarchical_report.py --group-by Assignee
```

### j.jql.generate_report_by_assignee.py
Generate assignee-wise issue distribution report.

```bash
j.jql.generate_report_by_assignee.py "project = FI AND sprint in openSprints()"
```

---

## Issue Management

### Get Issue Details

```bash
# Get field value (shell)
j.getFldVal_id_fldname.sh FI-12345 Summary

# Get details in table format
j.getDetInTblForm.sh < issues_raw.txt

# With labels
j.getDetInTblFormWithLabels.sh < issues_raw.txt
```

### j.getUserId.py
Search for Jira user by name/email.

```bash
j.getUserId.py "john.doe"
# Returns: Key, Name, Email-Address
```

### Update Assignee

```bash
# Python version
j.updateAssignee.id.assignee.py FI-12345 john.doe

# Reassign to reporter
j.updateAssignee2Reporter.py FI-12345
```

### Update Labels

```bash
# Python version (add/remove)
j.updateLabels.py FI-12345 --add "label1,label2" --remove "old_label"

# Shell version (add only)
j.addLabels..id.labels.sh FI-12345 label1 label2
```

### Update Sprint

```bash
j.updateSprint.py FI-12345 --board "Sprint Board Name"
# Moves issue to active sprint
```

### Update Status

```bash
# Close/Done workflow
j.updateStatusDefault2Close.py FI-12345 --resolution "Fixed"

# Available resolutions:
#   Fixed, Can't Fix, Won't Fix, Duplicate, Incomplete,
#   Cannot Reproduce, Done, Rejected, Won't Do, Not an Issue
```

### Update Summary

```bash
j.updateSummary.py FI-12345 "New summary text"
```

### Update Custom Field

```bash
j.updateFldVal_id_fldname_value.sh FI-12345 "Solution" "Fixed in build 123"
```

### Add Comment

```bash
# Inline comment
j.addComment.sh FI-12345 "This is my comment"

# From file
j.addComment.sh FI-12345 -f comment.txt

# Interactive (Ctrl+D to finish)
j.addComment.sh FI-12345
```

---

## Issue Linking & Relations

### Set Epic Link

```bash
j.setEpicLink.sh FI-12345 EPIC-100

# Uses JIRA_EPIC_LINK env if second arg omitted
j.setEpicLink.sh FI-12345
```

### Unset Epic Link

```bash
j.unsetEpicLink.sh FI-12345
```

### Create Relation Between Issues

```bash
j.createRelationBetweenIssues.py -s FI-123 -d FI-456 -r Relates

# Relation types: Relates, Duplicate, Blocks, Cloners
```

---

## Bulk Operations

### Clone Issues (JQL-based)

```bash
j.cloneIssuesFoundByJQL.TrackedNBSM2.4.py "project = FI AND labels = migrate"
```

### Create Issues from JSON

```bash
j.createJiraFromJsonFile.py issues.json
```

### Create Issues from Excel

```bash
j.createJiraIfEmptyCellAtColumnB.py data.xlsx
```

### Update Excel from Jira

```bash
j.updateExcelBasedOnJiraData.py data.xlsx
```

### Create Sub-tasks

```bash
j.createSubTasks.sh FI-12345 "Subtask 1" "Subtask 2"
```

### Generate Report for List of IDs

```bash
j.generate_report..listJids.sh FI-123 FI-456 FI-789
```

---

## SFDC (Salesforce) Integration

### Get Case Details

```bash
# Single case
sfdc.getCaseDetails.py 5001234567890

# Multiple cases
sfdc.getCaseDetails.py 5001234567890 5001234567891

# JSON output
sfdc.getCaseDetails.py 5001234567890 --format json
```

**Environment setup for SFDC:**
```bash
export SFDC_INSTANCE_URL=https://yourinstance.salesforce.com
export SFDC_ACCESS_TOKEN=your_access_token
# Or use client_id/secret for auto-refresh
```

---

## Watchers & Components

### Update Component, Labels, and Watchers

```bash
j.updateComponent.Labels.Watchers.IfEpicLink.sh FI-12345
```

### Manage Security Issue Watchers

```bash
j.manageSecurityIssueWatchers.py FI-12345 --add user1 --remove user2
```

### Unset Component

```bash
j.unsetComponent.sh FI-12345 "ComponentName"
```

---

## Custom Field ID Lookup

### Convert Field ID to Name

```bash
j.convert_custom_field_id_to_name.py customfield_33802
# Output: Etrack ID
```

---

## Sprint & Board Operations

### Get Sprint Info

```bash
j.updateSprint.py --board "Board Name" --list-sprints
```

---

## File Formats

### Issue List File (for -f option)
```
FI-12345
FI-12346
FI-12347
```

### Story File Template
```
# See story_file_template for creating bulk stories
```

### JSON Issue Format
```json
{
  "fields": {
    "project": {"key": "FI"},
    "summary": "Issue summary",
    "issuetype": {"name": "Story"},
    "assignee": {"name": "john.doe"}
  }
}
```

---

## Common JQL Patterns

```sql
-- My open issues
assignee = currentUser() AND status != Closed

-- Sprint issues
project = FI AND sprint in openSprints()

-- By label
project = FI AND labels = "Tracking"

-- By component
project = FI AND component = "Backend"

-- By date range
project = FI AND created >= -7d

-- Multiple conditions
project = FI AND status = Open AND priority = High ORDER BY created DESC

-- Issues with specific custom field
project = FI AND cf[33802] IS NOT EMPTY
```

---

## Tips & Tricks

1. **Pipe commands together:**
   ```bash
   j.getFldVal_id_fldname.sh FI-123 key | xargs -I{} j.addComment.sh {} "Auto comment"
   ```

2. **Bulk update labels:**
   ```bash
   cat issues.txt | while read id; do j.addLabels..id.labels.sh $id "NewLabel"; done
   ```

3. **Export and analyze:**
   ```bash
   j.et.rpt.py -where "project = FI" --csv report.csv && open report.csv
   ```

4. **Debug API calls:**
   Most scripts will print the URL being called for troubleshooting.

---

## Dependencies

```bash
pip install requests python-dotenv pandas prettytable tabulate matplotlib
```

---

## Script Index (Alphabetical)

| Script | Description |
|--------|-------------|
| `j.addComment.sh` | Add comment to issue |
| `j.addLabels..id.labels.sh` | Add labels to issue |
| `j.cloneIssuesFoundByJQL.*.py` | Clone issues matching JQL |
| `j.convert_custom_field_id_to_name.py` | Lookup custom field names |
| `j.createJiraFromJsonFile.py` | Create issues from JSON |
| `j.createRelationBetweenIssues.py` | Link issues |
| `j.createSubTasks.sh` | Create sub-tasks |
| `j.et.rpt.py` | **Main report tool** with analysis |
| `j.getDetInTblForm.sh` | Format details as table |
| `j.getFldVal_id_fldname.sh` | Get field value |
| `j.getUserId.py` | Search users |
| `j.jql.generate_*.py` | Report generators |
| `j.printJQLResultInTableFormat..oJql.py` | JQL to table |
| `j.setEpicLink.sh` | Set epic link |
| `j.sprintBoard.py` | Kanban board display |
| `j.unsetEpicLink.sh` | Remove epic link |
| `j.updateAssignee.id.assignee.py` | Update assignee |
| `j.updateFldVal_id_fldname_value.sh` | Update any field |
| `j.updateLabels.py` | Manage labels |
| `j.updateSprint.py` | Move to sprint |
| `j.updateStatusDefault2Close.py` | Close issues |
| `j.updateSummary.py` | Update summary |
| `sfdc.getCaseDetails.py` | Salesforce case lookup |

---

*Generated from jira/ folder analysis*
