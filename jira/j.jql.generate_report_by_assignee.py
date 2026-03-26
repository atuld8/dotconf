#!/usr/bin/env python3

import sys
import re


# Priority sorting order (from highest to lowest)
priority_order = {
    'P1': 1,
    'P2': 2,
    'P3': 3,
    'P4': 4
}


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


def print_jira_report(file):

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
        line = f"\t{key} | {summary} (P: {priority}, S: {severity}, T: {issuetype})"
        if case_number:
            line += f" | Case#: {case_number}"
        if formatted_case_links:
            line += f" | SalesForce Case Link: {formatted_case_links}"
        print(line)
        assignee_issue_count += 1
        total_issues += 1

    if last_assignee is not None:
        print(f"\n\tNumber of issues for {last_assignee}: {assignee_issue_count}\n")
    # Print the total number of issues
    print(f"\n\nTotal number of issues: {total_issues}")


if __name__ == "__main__":
    # You can read the table from a file or standard input
    with sys.stdin if len(sys.argv) == 1 else open(sys.argv[1], 'r') as file:
        print_jira_report(file)
