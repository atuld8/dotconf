#!/usr/bin/env python3.12

'''
Script to list all Incidents whose EXT_INC (Jira tickets) are in closed state.
EXT_INC column contains Jira ticket IDs starting with FI- or SH-.
Handles 1-to-many relationship where one incident can have multiple FI- or SH- tickets.

Closed states: ["Closed", "Done", "Resolved", "Fixed"]
'''

import os
import re
import argparse
import requests
from collections import defaultdict
from dotenv import load_dotenv
from prettytable import PrettyTable


# Load the environment variables configured on the system
load_dotenv()

# Jira credentials and URL
JIRA_URL = "https://" + os.getenv('JIRA_SERVER_NAME')
JIRA_API_TOKEN = os.getenv('JIRA_ACC_TOKEN')

# Jira API endpoint for issue details
issue_url = f'{JIRA_URL}/rest/api/2/issue'

# Headers
headers = {
    'Authorization': f'Bearer {JIRA_API_TOKEN}',
    'Content-Type': 'application/json'
}

# Closed statuses
CLOSED_STATUSES = ["Closed", "Done", "Resolved", "Fixed", "Solution Provided"]


def parse_input_file(file_path):
    """
    Parse the input file to extract Incident and EXT_INC mappings.
    Returns a dictionary with incident numbers as keys and list of Jira IDs as values.

    Args:
        file_path (str): Path to the input file

    Returns:
        dict: Dictionary mapping incident numbers to list of Jira IDs
    """
    incident_jira_map = defaultdict(list)

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        for line in lines:
            # Skip header lines and separator lines
            if '---' in line or 'INCIDENT' in line or 'EXT_INC' in line:
                continue

            # Extract incident and Jira ID using regex
            # Looking for pattern: | <incident_number> | <FI-xxxxx or SH-xxxxx> |
            match = re.search(r'\|\s*(\d+)\s*\|\s*((?:FI|SH)-\d+)\s*\|', line)
            if match:
                incident = match.group(1).strip()
                jira_id = match.group(2).strip()

                # Avoid duplicates
                if jira_id not in incident_jira_map[incident]:
                    incident_jira_map[incident].append(jira_id)

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

    return dict(incident_jira_map)


def get_jira_statuses_bulk(jira_ids, batch_size=50):
    """
    Get the current status of multiple Jira issues in bulk using JQL.
    This is much faster than making individual API calls.

    Args:
        jira_ids (list): List of Jira ticket IDs (e.g., ['FI-12345', 'SH-67890'])
        batch_size (int): Number of issues to fetch per batch (default 50)

    Returns:
        dict: Dictionary mapping Jira IDs to their status names
    """
    jira_status_map = {}

    # Calculate total batches
    total_batches = (len(jira_ids) + batch_size - 1) // batch_size

    # Process in batches to avoid JQL length limits
    for i in range(0, len(jira_ids), batch_size):
        batch_num = (i // batch_size) + 1
        batch = jira_ids[i:i + batch_size]

        print(f"  Fetching batch {batch_num}/{total_batches} ({len(batch)} tickets)...", end=" ")

        # Create JQL query with keys
        keys_str = ", ".join(batch)
        jql = f"key in ({keys_str})"

        try:
            url = f'{JIRA_URL}/rest/api/2/search'
            params = {
                'jql': jql,
                'maxResults': batch_size,
                'fields': 'key,status'
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                issues = response.json().get('issues', [])
                for issue in issues:
                    key = issue['key']
                    status = issue['fields']['status']['name']
                    jira_status_map[key] = status
                print("✓")
            else:
                print(f"✗ Failed: {response.status_code}")
                # Mark failed fetches as ERROR
                for jira_id in batch:
                    if jira_id not in jira_status_map:
                        jira_status_map[jira_id] = "ERROR"

        except requests.exceptions.RequestException as e:
            print(f"✗ Error: {e}")
            # Mark failed fetches as ERROR
            for jira_id in batch:
                if jira_id not in jira_status_map:
                    jira_status_map[jira_id] = "ERROR"

    # Mark any missing issues as NOT_FOUND
    for jira_id in jira_ids:
        if jira_id not in jira_status_map:
            jira_status_map[jira_id] = "NOT_FOUND"

    return jira_status_map


def get_jira_status(jira_id):
    """
    Get the current status of a Jira issue.

    Args:
        jira_id (str): Jira ticket ID (e.g., FI-12345 or SH-12345)

    Returns:
        str: Status name or None if error
    """
    url = f"{issue_url}/{jira_id}"

    try:
        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code == 200:
            issue_data = response.json()
            status = issue_data['fields']['status']['name']
            return status
        elif response.status_code == 404:
            return "NOT_FOUND"
        else:
            print(f"Failed to fetch {jira_id}: {response.status_code} - {response.text}")
            return "ERROR"

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {jira_id}: {e}")
        return "ERROR"


def check_all_tickets_closed(jira_statuses):
    """
    Check if all Jira tickets are in closed state.

    Args:
        jira_statuses (dict): Dictionary mapping Jira IDs to their statuses

    Returns:
        bool: True if all tickets are closed, False otherwise
    """
    for status in jira_statuses.values():
        if status not in CLOSED_STATUSES:
            return False
    return True


def format_jira_status_string(jira_statuses):
    """
    Format Jira IDs and their statuses into a readable string.

    Args:
        jira_statuses (dict): Dictionary mapping Jira IDs to their statuses

    Returns:
        str: Formatted string like "FI-12345[Closed], SH-67890[Done]"
    """
    status_list = []
    for jira_id, status in sorted(jira_statuses.items()):
        status_list.append(f"{jira_id}[{status}]")
    return ", ".join(status_list)


def main(file_path, show_all=False, show_jira_status=False):
    """
    Main function to process incidents and list those with all Jira tickets closed.

    Args:
        file_path (str): Path to the input file containing incident and Jira mapping
        show_all (bool): If True, show all incidents regardless of status
        show_jira_status (bool): If True, display all Jira tickets status table
    """
    print(f"Reading input file: {file_path}")
    print(f"Closed statuses: {', '.join(CLOSED_STATUSES)}\n")

    # Parse the input file
    incident_jira_map = parse_input_file(file_path)

    if incident_jira_map is None:
        return

    if not incident_jira_map:
        print("No incident-Jira mappings found in the file.")
        return

    print(f"Found {len(incident_jira_map)} unique incidents with Jira mappings.")

    # Collect all unique Jira IDs for bulk fetching
    all_jira_ids = []
    for jira_ids in incident_jira_map.values():
        all_jira_ids.extend(jira_ids)

    # Remove duplicates while preserving order
    unique_jira_ids = list(dict.fromkeys(all_jira_ids))

    print(f"Total unique Jira tickets: {len(unique_jira_ids)}")
    print("Fetching Jira statuses in bulk (this is much faster)...\n")

    # Fetch all statuses in bulk
    all_jira_statuses = get_jira_statuses_bulk(unique_jira_ids)

    print(f"Successfully fetched {len(all_jira_statuses)} Jira statuses.\n")
    print("Processing incidents...\n")

    # Process each incident with the bulk fetched statuses
    all_incidents = []
    closed_count = 0

    for incident, jira_ids in sorted(incident_jira_map.items()):
        jira_statuses = {}

        # Get statuses from bulk fetch results
        for jira_id in jira_ids:
            jira_statuses[jira_id] = all_jira_statuses.get(jira_id, "ERROR")

        all_closed = check_all_tickets_closed(jira_statuses)

        if all_closed:
            closed_count += 1

        all_incidents.append({
            'incident': incident,
            'jira_count': len(jira_ids),
            'jira_statuses': jira_statuses,
            'all_closed': all_closed,
            'status_string': format_jira_status_string(jira_statuses)
        })

    # Display results in table format
    print("\n" + "="*120)
    if show_all:
        print(f"ALL INCIDENTS WITH JIRA STATUS (Total: {len(all_incidents)})")
    else:
        print(f"INCIDENTS WITH ALL JIRA TICKETS IN CLOSED STATE (Total: {closed_count} of {len(all_incidents)})")
    print("="*120 + "\n")

    # Filter based on show_all flag
    incidents_to_display = all_incidents if show_all else [inc for inc in all_incidents if inc['all_closed']]

    if not incidents_to_display:
        print("No incidents found matching the filter criteria.")
        return

    # Create table with separate columns for each Jira ticket
    table = PrettyTable()
    table.field_names = ["Sr.", "Incident", "Jira ID", "Status", "All Closed"]
    table.align["Sr."] = "r"
    table.align["Incident"] = "l"
    table.align["Jira ID"] = "l"
    table.align["Status"] = "l"
    table.align["All Closed"] = "c"

    sr_counter = 1
    for item in incidents_to_display:
        incident = item['incident']
        jira_statuses = item['jira_statuses']

        # Sort Jira IDs for consistent display
        sorted_jira_ids = sorted(jira_statuses.keys())

        # Add first row with incident number
        first_jira = sorted_jira_ids[0]
        all_closed_mark = "✓" if item['all_closed'] else "✗"
        table.add_row([
            sr_counter,
            incident,
            first_jira,
            jira_statuses[first_jira],
            all_closed_mark
        ])

        # Add remaining Jira tickets for the same incident (blank incident column)
        for jira_id in sorted_jira_ids[1:]:
            table.add_row([
                "",
                "",
                jira_id,
                jira_statuses[jira_id],
                ""
            ])

        # Add separator line after each incident (if there are more incidents)
        if sr_counter < len(incidents_to_display):
            table.add_row(["---", "---", "---", "---", "---"])

        sr_counter += 1

    print(table)

    # Display all Jira tickets status table (if enabled)
    if show_jira_status:
        print("\n" + "="*120)
        print("ALL JIRA TICKETS STATUS")
        print("="*120 + "\n")

        # Create a comprehensive Jira status table
        jira_table = PrettyTable()
        jira_table.field_names = ["Sr.", "Jira ID", "Status", "Is Closed"]
        jira_table.align["Sr."] = "r"
        jira_table.align["Jira ID"] = "l"
        jira_table.align["Status"] = "l"
        jira_table.align["Is Closed"] = "c"

        # Collect all unique Jira tickets with their statuses
        jira_status_list = []
        for jira_id in sorted(all_jira_statuses.keys()):
            status = all_jira_statuses[jira_id]
            is_closed = "✓" if status in CLOSED_STATUSES else "✗"
            jira_status_list.append((jira_id, status, is_closed))

        # Add rows to the table
        for idx, (jira_id, status, is_closed) in enumerate(jira_status_list, start=1):
            jira_table.add_row([idx, jira_id, status, is_closed])

        print(jira_table)

    # Summary statistics
    print("\n" + "="*120)
    print("SUMMARY")
    print("="*120)
    print(f"Total incidents processed: {len(incident_jira_map)}")
    print(f"Incidents with all tickets closed: {closed_count}")
    print(f"Incidents with open tickets: {len(all_incidents) - closed_count}")
    print(f"Closed status definitions: {', '.join(CLOSED_STATUSES)}")
    print("="*120)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="List incidents whose EXT_INC (Jira tickets FI-/SH-) are in closed state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/SR_FI_SH
  %(prog)s ~/op/SR_FI_SH --show-all
        """
    )

    parser.add_argument(
        "file_path",
        help="Path to the input file containing incident and EXT_INC mapping"
    )

    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all incidents regardless of closed status (for debugging)"
    )

    parser.add_argument(
        "--show-jira-status",
        action="store_true",
        help="Display a separate table showing all Jira tickets with their current status"
    )

    args = parser.parse_args()

    main(args.file_path, args.show_all, args.show_jira_status)
