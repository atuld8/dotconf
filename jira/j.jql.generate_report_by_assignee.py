#!/usr/bin/env python3

import sys
import csv


# Priority sorting order (from highest to lowest)
priority_order = {
    'P1': 1,
    'P2': 2,
    'P3': 3,
    'P4': 4
}


def print_jira_report(file):

    # list to hold all rows
    rows = []

    reader = csv.reader(file, delimiter='|')
    next(reader)  # Skip the header row
    next(reader)  # Skip the header row

    for row in reader:

        # Skip empty rows or rows with insufficient columns
        if len(row) < 9:
            continue

        # Extract fields and trim whitespaces
        sr = row[1].strip()
        key = row[2].strip()
        summary = row[3].strip()
        status = row[4].strip()
        assignee = row[5].strip()
        reporter = row[6].strip()
        priority = row[7].strip()
        severity = row[8].strip()
        issuetype = row[9].strip()

        # Append to the list for sorting later
        rows.append((assignee, key, summary, priority, severity, issuetype))

    # Sort the rows by the assignee field
    rows.sort(key=lambda x: (x[0], priority_order.get(x[3], 5)))

    last_assignee = None
    assignee_issue_count = 0
    total_issues = 0

    # print the sorted rows
    for assignee, key, summary, priority, severity, issuetype in rows:
        # Check if we have a new assignee
        if assignee != last_assignee:
            if last_assignee is not None:
                print(f"\n\tNumber of issues for {last_assignee}: {assignee_issue_count}\n")
                print()  # Add a blank line before the next assignee
            print(f"Assignee: {assignee}")
            last_assignee = assignee
            assignee_issue_count = 0

        # Print the Jira ticket details on a single line
        print(f"\t{key} | {summary} (P: {priority}, S: {severity}, T: {issuetype})")
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
