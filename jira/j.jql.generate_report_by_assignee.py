#!/usr/bin/env python3
"""
Jira Report Generator - Group Issues by Assignee

Parses a markdown/text table (typically from Jira JQL export) and generates
a formatted report grouped by assignee with issues sorted by priority.

USAGE:
    # From stdin (pipe from another command)
    cat jira_export.txt | python3 j.jql.generate_report_by_assignee.py

    # From file
    python3 j.jql.generate_report_by_assignee.py jira_export.txt

    # Show help
    python3 j.jql.generate_report_by_assignee.py -h

INPUT FORMAT:
    Expects a markdown-style table with columns (column names are flexible):

    | Key       | Summary           | Assignee   | Priority | Severity | IssueType | Case#  | SalesForce Case Link |
    |-----------|-------------------|------------|----------|----------|-----------|--------|----------------------|
    | NBU-12345 | Fix login bug     | john.doe   | P1       | S1       | Defect    | 123456 | [Link|https://...]   |
    | NBU-12346 | Add new feature   | jane.smith | P2       | S2       | Story     |        |                      |

SUPPORTED COLUMNS:
    Required:
        - Key: Jira issue key (e.g., NBU-12345)

    Optional (flexible naming):
        - Summary: Issue title/description
        - Assignee: Person assigned to the issue
        - Priority: P1, P2, P3, P4 (sorted highest to lowest)
        - Severity: S1, S2, S3, S4
        - IssueType / Issue Type: Story, Defect, Bug, etc.
        - Case# / Salesforce Case #: Support case number
        - SalesForce Case Link / SFDC Case Link: Link to Salesforce case

OUTPUT FORMAT:
    Assignee: john.doe
        NBU-12345 | Fix login bug (P: P1, S: S1, T: Defect) | Case#: 123456 | SalesForce Case Link: ...
        NBU-12347 | Another issue (P: P2, S: S2, T: Story)

        Number of issues for john.doe: 2

    Assignee: jane.smith
        NBU-12346 | Add new feature (P: P2, S: S2, T: Story)

        Number of issues for jane.smith: 1


    Total number of issues: 3

FEATURES:
    - Groups issues by assignee
    - Sorts issues by priority within each assignee (P1 > P2 > P3 > P4)
    - Handles Salesforce case links in markdown format: [label|url]
    - Handles pipes (|) inside markdown links without breaking parsing
    - Shows issue count per assignee and total count

EXAMPLES:
    # Generate report from Jira CLI output
    jira issue list -q "project = NBU AND sprint in openSprints()" --plain | \\
        python3 j.jql.generate_report_by_assignee.py

    # Generate report from saved export file
    python3 j.jql.generate_report_by_assignee.py ~/jira_sprint_export.txt

    # Combine with other tools
    pbpaste | python3 j.jql.generate_report_by_assignee.py  # macOS clipboard
    xclip -o | python3 j.jql.generate_report_by_assignee.py  # Linux clipboard
"""

import sys
import re
import argparse


# Priority sorting order (from highest to lowest)
priority_order = {
    'P1': 1,
    'P2': 2,
    'P3': 3,
    'P4': 4
}

# Supported output columns (for --columns option)
SUPPORTED_COLUMNS = [
    'key',        # Jira issue key (always included)
    'summary',    # Issue summary/title
    'priority',   # Priority (P1, P2, P3, P4)
    'severity',   # Severity (S1, S2, S3, S4)
    'issuetype',  # Issue type (Story, Defect, etc.)
    'case',       # Salesforce case number
    'caselink',   # Salesforce case link
]

DEFAULT_COLUMNS = ['key', 'summary', 'priority', 'severity', 'issuetype', 'case', 'caselink']


def _normalize_header(value):
    return re.sub(r'[^a-z0-9]+', '', value.strip().lower())


def _split_table_row(raw_line):
    placeholder = "\x1f"
    chars = []
    inside_brackets = 0

    for char in raw_line.rstrip("\n"):
        if char == '[':
            inside_brackets += 1
        elif char == ']' and inside_brackets > 0:
            inside_brackets -= 1

        if char == '|' and inside_brackets > 0:
            chars.append(placeholder)
        else:
            chars.append(char)

    return [cell.replace(placeholder, '|').strip() for cell in "".join(chars).split('|')]


def _is_border_row(row):
    joined = "".join(cell.strip() for cell in row)
    return bool(joined) and set(joined) <= {"-", "+", "="}


def _build_header_map(row):
    header_map = {}
    for index, cell in enumerate(row):
        header = cell.strip()
        if header:
            header_map[_normalize_header(header)] = index
    return header_map


def _get_cell(row, header_map, *header_names):
    for header_name in header_names:
        index = header_map.get(_normalize_header(header_name))
        if index is not None and index < len(row):
            return row[index].strip()
    return ""


def _parse_sfdc_case_links(raw_value):
    links = []
    raw = (raw_value or "").strip()
    if not raw or raw == '-':
        return links

    for match in re.finditer(r'\[([^|\]]+)\|([^\]]+)\]', raw):
        links.append((match.group(1).strip(), match.group(2).strip()))

    if links:
        return links

    for token in raw.split():
        token = token.strip(',;')
        if token:
            links.append((token, ""))
    return links


def _format_sfdc_case_links(raw_value):
    links = _parse_sfdc_case_links(raw_value)
    if not links:
        return ""
    return "; ".join(
        f"{label}: {url}" if url else label
        for label, url in links
    )


def print_jira_report(file, columns=None):
    """Generate and print the Jira report grouped by assignee.

    Args:
        file: File object to read input from
        columns: List of columns to display (default: all columns)
    """
    if columns is None:
        columns = DEFAULT_COLUMNS

    # Normalize column names
    columns = [c.lower().strip() for c in columns]

    # list to hold all rows
    rows = []

    header_map = None

    for raw_line in file:
        row = _split_table_row(raw_line)
        if _is_border_row(row):
            continue

        if header_map is None:
            header_map = _build_header_map(row)
            continue

        if not any(cell.strip() for cell in row):
            continue

        key = _get_cell(row, header_map, 'Key')
        summary = _get_cell(row, header_map, 'Summary')
        assignee = _get_cell(row, header_map, 'Assignee') or '-'
        priority = _get_cell(row, header_map, 'Priority') or '-'
        severity = _get_cell(row, header_map, 'Severity') or '-'
        issuetype = _get_cell(row, header_map, 'IssueType', 'Issue Type') or '-'
        case_number = _get_cell(row, header_map, 'Case#', 'Salesforce Case #')
        case_link_raw = _get_cell(row, header_map, 'SalesForce Case Link', 'Salesforce Case Link', 'SFDC Case Link')

        if not key:
            continue

        formatted_case_links = _format_sfdc_case_links(case_link_raw)

        # Append to the list for sorting later
        rows.append((assignee, key, summary, priority, severity, issuetype, case_number, formatted_case_links))

    # Sort the rows by the assignee field
    rows.sort(key=lambda x: (x[0], priority_order.get(x[3], 5)))

    last_assignee = None
    assignee_issue_count = 0
    total_issues = 0

    # print the sorted rows
    for assignee, key, summary, priority, severity, issuetype, case_number, formatted_case_links in rows:
        # Check if we have a new assignee
        if assignee != last_assignee:
            if last_assignee is not None:
                print(f"\n\tNumber of issues for {last_assignee}: {assignee_issue_count}\n")
                print()  # Add a blank line before the next assignee
            print(f"Assignee: {assignee}")
            last_assignee = assignee
            assignee_issue_count = 0

        # Print the Jira ticket details on a single line
        parts = []

        # Key is always first
        if 'key' in columns:
            parts.append(key)

        # Summary
        if 'summary' in columns and summary:
            parts.append(summary)

        # Priority/Severity/Type in parentheses
        pst_parts = []
        if 'priority' in columns:
            pst_parts.append(f"P: {priority}")
        if 'severity' in columns:
            pst_parts.append(f"S: {severity}")
        if 'issuetype' in columns:
            pst_parts.append(f"T: {issuetype}")
        if pst_parts:
            parts.append(f"({', '.join(pst_parts)})")

        # Case number
        if 'case' in columns and case_number:
            parts.append(f"Case#: {case_number}")

        # Case link
        if 'caselink' in columns and formatted_case_links:
            parts.append(f"SalesForce Case Link: {formatted_case_links}")

        line = "\t" + " | ".join(parts)
        print(line)
        assignee_issue_count += 1
        total_issues += 1

    if last_assignee is not None:
        print(f"\n\tNumber of issues for {last_assignee}: {assignee_issue_count}\n")
    # Print the total number of issues
    print(f"\n\nTotal number of issues: {total_issues}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Generate Jira report grouped by assignee from a markdown table',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From stdin (pipe from another command)
  cat jira_export.txt | %(prog)s

  # From file
  %(prog)s jira_export.txt

  # From clipboard (macOS)
  pbpaste | %(prog)s

  # Show only key, summary, and priority
  %(prog)s -c key,summary,priority jira_export.txt

  # Exclude case links
  %(prog)s -c key,summary,priority,severity,issuetype,case jira_export.txt

Input: Markdown-style table with columns: Key, Summary, Assignee, Priority, etc.
Output: Issues grouped by assignee, sorted by priority, with counts.

Supported columns for -c/--columns:
  key        - Jira issue key (e.g., NBU-12345)
  summary    - Issue title/description
  priority   - Priority (P1, P2, P3, P4)
  severity   - Severity (S1, S2, S3, S4)
  issuetype  - Issue type (Story, Defect, Bug, etc.)
  case       - Salesforce case number
  caselink   - Salesforce case link
"""
    )
    parser.add_argument('file', nargs='?', type=argparse.FileType('r'), default=sys.stdin,
                        help='Input file with Jira table (default: stdin)')
    parser.add_argument('-c', '--columns', type=lambda s: [c.strip() for c in s.split(',')],
                        default=DEFAULT_COLUMNS,
                        help='Comma-separated list of columns to display (default: %s). '
                             'Available: %s' % (','.join(DEFAULT_COLUMNS), ','.join(SUPPORTED_COLUMNS)))

    args = parser.parse_args()

    # Validate columns
    invalid_cols = [c for c in args.columns if c.lower() not in SUPPORTED_COLUMNS]
    if invalid_cols:
        print(f"Error: Invalid column(s): {', '.join(invalid_cols)}", file=sys.stderr)
        print(f"Supported columns: {', '.join(SUPPORTED_COLUMNS)}", file=sys.stderr)
        sys.exit(1)

    # Check if stdin is empty and no file provided
    if args.file == sys.stdin and sys.stdin.isatty():
        parser.print_help()
        sys.exit(0)

    print_jira_report(args.file, columns=args.columns)
