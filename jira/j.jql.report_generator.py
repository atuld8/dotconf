#!/usr/bin/env python3.12

# pip3.12 install pandas tabulate matplotlib

import argparse
import pandas as pd
from tabulate import tabulate
import matplotlib.pyplot as plt


# Function to process input data into a dataframe
def process_table(input_data):
    headers = ["Serial", "Key", "Summary",
               "Status", "Assignee", "Priority",
               "IssueType", "Labels"]
    data = [line.strip().strip('|').split('|') for line in input_data]


    df = pd.DataFrame(data, columns=headers)

    # Strip whitespace from each field
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # Split the 'Labels' column by comma if there are multiple labels
    df['Labels'] = df['Labels'].apply(lambda x: x.split(',') if x else [])
    return df


# Generate reports based on status
def report_by_status(df):
    status_report = df['Status'].value_counts()
    print("\nReport by Status:")
    print(tabulate(status_report.items(), headers=["Status", "Count"], tablefmt="grid"))
    return status_report


# Generate reports for defects by status
def report_defects_by_status(df):
    defects_df = df[df['IssueType'] == 'Defect']
    status_report = defects_df['Status'].value_counts()
    print("\nReport for Defects by Status:")
    print(tabulate(status_report.items(), headers=["Status", "Count"], tablefmt="grid"))
    return status_report


# Generate reports for defects by status
def report_Story_by_status(df):
    defects_df = df[df['IssueType'] == 'Story']
    status_report = defects_df['Status'].value_counts()
    print("\nReport for Story by Status:")
    print(tabulate(status_report.items(), headers=["Status", "Count"], tablefmt="grid"))
    return status_report


# Generate reports based on priority
def report_by_priority(df):
    priority_report = df['Priority'].value_counts()
    print("\nReport by Priority:")
    print(tabulate(priority_report.items(), headers=["Priority", "Count"], tablefmt="grid"))
    return priority_report


# Generate reports based on issue type
def report_by_issue_type(df):
    issue_type_report = df['IssueType'].value_counts()
    print("\nReport by IssueType:")
    print(tabulate(issue_type_report.items(), headers=["IssueType", "Count"], tablefmt="grid"))
    return issue_type_report


# Generate reports based on labels (considering multiple values)
def report_by_labels(df):
    labels_series = pd.Series([label for sublist in df['Labels'] for label in sublist])
    labels_report = labels_series.value_counts()
    print("\nReport by Labels:")
    print(tabulate(labels_report.items(), headers=["Label", "Count"], tablefmt="grid"))
    return labels_report


# Generate bar graph for a report
def generate_bar_chart(report, title):
    report.plot(kind='bar', title=title)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description="Process command-line table entries")
    parser.add_argument("input_file", help="Input file with table entries")
    parser.add_argument("--show-chart", action="store_true", help="Show bar chart if specified")
    args = parser.parse_args()

    # Read input file
    with open(args.input_file, 'r') as f:
        input_data = f.readlines()[3:]  # Skipping the header line

    # Process the table and generate dataframe
    df = process_table(input_data)

    # Generate reports
    status_report = report_by_status(df)
    priority_report = report_by_priority(df)
    issue_type_report = report_by_issue_type(df)
    labels_report = report_by_labels(df)

    # Generate report for defects by status
    defects_status_report = report_defects_by_status(df)
    story_status_report = report_Story_by_status(df)

    if args.show_chart:
        # Generate bar charts for terminal visualization
        generate_bar_chart(status_report, 'Status Distribution')
        generate_bar_chart(priority_report, 'Priority Distribution')
        generate_bar_chart(issue_type_report, 'IssueType Distribution')
        generate_bar_chart(labels_report, 'Labels Distribution')
        generate_bar_chart(defects_status_report, 'Defects Status Distribution')
        generate_bar_chart(story_status_report, 'Story Status Distribution')

if __name__ == "__main__":
    main()
