#!/usr/bin/env python3
import argparse
import pandas as pd
from tabulate import tabulate


# Function to process input data into a dataframe
def process_table(input_data):
    headers = ["Sr.", "Key", "Summary", "Status", "Assignee", "Reporter",
               "Priority", "Severity", "IssueType", "Labels"]
    data = [line.strip().strip('|').split('|') for line in input_data]

    df = pd.DataFrame(data, columns=headers)

    # Strip whitespace from each field
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # Split the 'Labels' column by comma if there are multiple labels
    df['Labels'] = df['Labels'].apply(lambda x: [label.strip() for label in x.split(',')] if x else [])
    return df


def generate_vertical_report1(df, group_by_column):
    # Ensure there are no missing values
    df.fillna('Unknown', inplace=True)

    # Group the data by the specified column, Status, Priority, and IssueType
    grouped = df.groupby([group_by_column, 'Status', 'Priority', 'IssueType']).size().reset_index(name='Count')

    # Create a list to store rows for the report
    report_data = []

    # Iterate over each unique Assignee/Reporter
    for key in grouped[group_by_column].unique():
        # Add the header row for the Assignee/Reporter
        report_data.append([f"{group_by_column}: {key}", "", "", "", ""])

        # Filter the grouped data for the current Assignee/Reporter
        subset = grouped[grouped[group_by_column] == key]

        # Add rows for each Status, Priority, and IssueType combination
        for _, row in subset.iterrows():
            report_data.append(["",
                                f"Status: {row['Status']}",
                                f"Priority: {row['Priority']}",
                                f"IssueType: {row['IssueType']}",
                                f"Count: {row['Count']}"
                                ])

    # Print the report in vertical format using tabulate
    print(f"\nReport by {group_by_column}:")
    print(tabulate(report_data, headers=[group_by_column, "Status", "Priority", "IssueType", "Count"], tablefmt="grid"))


def generate_vertical_report2(df, group_by_column):
    # Ensure there are no missing values
    df.fillna('Unknown', inplace=True)

    # Group the data by the specified column, Status, Priority, and IssueType
    grouped = df.groupby([group_by_column, 'Status', 'Priority', 'IssueType']).size().reset_index(name='Count')

    # Create a dictionary to organize the report
    report_dict = {}

    # Populate the report dictionary
    for key in grouped[group_by_column].unique():
        report_dict[key] = grouped[grouped[group_by_column] == key]

    # Print the report
    print(f"\nReport by {group_by_column}:\n")
    for key, data in report_dict.items():
        print(f"{group_by_column}: {key}")
        print("-" * 60)
        print(f"{'Status':<20} {'Priority':<15} {'IssueType':<15} {'Count':<5}")
        print("-" * 60)
        total_count = 0  # Initialize total count
        for _, row in data.iterrows():
            print(f"{row['Status']:<20} {row['Priority']:<15} {row['IssueType']:<15} {row['Count']:<5}")
            total_count += row['Count']
        # Print total count at the end
        print("-" * 60)
        print(f"{'Total Count:':<52} {total_count:<5}")
        print("\n")


def generate_detailed_report(df):
    # Ensure there are no missing values
    df.fillna('Unknown', inplace=True)

    # Group the data by Assignee, Reporter, Status, Priority, and IssueType
    grouped = df.groupby(['Assignee', 'Reporter', 'Status', 'Priority', 'IssueType']).size().reset_index(name='Count')

    # Create a list of unique Assignees and Reporters
    unique_assignees = grouped['Assignee'].unique()
    unique_reporters = grouped['Reporter'].unique()

    # Print the report
    print("\nDetailed Report by Assignee and Reporter:\n")

    for assignee in unique_assignees:
        print(f"Assignee: {assignee}")
        print("-" * 80)

        # Filter by Assignee
        assignee_data = grouped[grouped['Assignee'] == assignee]

        # Print Status counts
        status_counts = assignee_data.groupby('Status').sum()['Count']
        print(f"{'Status':<20} {'Count':<5}")
        print("-" * 30)
        for status, count in status_counts.items():
            print(f"{status:<20} {count:<5}")

        print()

        # Print Priority counts
        priority_counts = assignee_data.groupby('Priority').sum()['Count']
        print(f"{'Priority':<20} {'Count':<5}")
        print("-" * 30)
        for priority, count in priority_counts.items():
            print(f"{priority:<20} {count:<5}")
        print()

        # Print Issue Type counts
        issue_type_counts = assignee_data.groupby('IssueType').sum()['Count']
        print(f"{'Issue Type':<20} {'Count':<5}")
        print("-" * 30)
        for issue_type, count in issue_type_counts.items():
            print(f"{issue_type:<20} {count:<5}")

        print("\n" + "-" * 80)

    # Now for the # Reporter
    for reporter in unique_reporters:
        print(f"Reporter: {reporter}")
        print("-" * 80)

        # Filter by Reporter
        reporter_data = grouped[grouped['Reporter'] == reporter]

        # Print  Status counts
        status_counts = reporter_data.groupby('Status').sum()['Count']
        print(f"{'Status':<20} {'Count':<5}")
        print("-" * 30)
        for status, count in status_counts.items():
            print(f"{status:<20} {count:<5}")
        print()

        # Print Priority counts
        priority_counts = reporter_data.groupby('Priority').sum()['Count']
        print(f"{'Priority':<20} {'Count':<5}")
        print("-" * 30)
        for priority, count in priority_counts.items():
            print(f"{priority:<20} {count:<5}")
        print()

        # Print Issue Type counts
        issue_type_counts = reporter_data.groupby('IssueType').sum()['Count']
        print(f"{'Issue Type':<20} {'Count':<5}")
        print("-" * 30)
        for issue_type, count in issue_type_counts.items():
            print(f"{issue_type:<20} {count:<5}")

        print("\n" + "-" * 80)


def main():
    parser = argparse.ArgumentParser(description="Process command-line table entries")
    parser.add_argument("input_file", help="Input file with table entries")
    parser.add_argument("--report", type=int, choices=[1, 2, 3], default=2, 
                        help="Specify report type: 1 for status report, 2 for priority report, 3 for detailed report")
    args = parser.parse_args()

    # Read input file and skip the header
    with open(args.input_file, 'r') as f:
        input_data = f.readlines()[3:-1]  # Skipping the header line in file reading

    # Process the table and generate dataframe
    df = process_table(input_data)

    if args.report == 1:
        generate_vertical_report1(df, "Assignee")
        generate_vertical_report1(df, "Reporter")
    elif args.report == 2:
        generate_vertical_report2(df, "Assignee")
        generate_vertical_report2(df, "Reporter")
    elif args.report == 3:
        generate_detailed_report(df)


if __name__ == "__main__":
    main()
