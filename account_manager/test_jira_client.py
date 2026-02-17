#!/usr/bin/env python3
"""
Test Jira Client - Verify connection and fetch FI assignees
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from account_manager.jira_client import JiraClient


def test_connection():
    """Test Jira connection"""
    print("Testing Jira Connection...")
    print("=" * 60)

    try:
        client = JiraClient()

        # Test connection
        if client.test_connection():
            print("+ Connection successful!\n")
            return client
        else:
            print("X Connection failed!\n")
            return None

    except Exception as e:
        print(f"X Error initializing Jira client: {e}")
        return None


def test_get_assignee(client, fi_id):
    """Test getting assignee for a FI"""
    print(f"\nFetching assignee for {fi_id}...")
    print("-" * 60)

    assignee = client.get_assignee(fi_id)

    if assignee:
        print(f"+ Assignee: {assignee}")
    else:
        print(f"X Could not fetch assignee (issue may not exist or no assignee)")

    return assignee


def test_get_issue_summary(client, fi_id):
    """Test getting full issue summary"""
    print(f"\nFetching issue summary for {fi_id}...")
    print("-" * 60)

    summary = client.get_issue_summary(fi_id)

    if summary:
        print(f"Key:              {summary.get('key')}")
        print(f"Summary:          {summary.get('summary')}")
        print(f"Status:           {summary.get('status')}")
        print(f"Assignee:         {summary.get('assignee')}")
        print(f"Assignee Display: {summary.get('assignee_display_name')}")
        print(f"Assignee Email:   {summary.get('assignee_email')}")
        print(f"Priority:         {summary.get('priority')}")
        print(f"Created:          {summary.get('created')}")
        print(f"Updated:          {summary.get('updated')}")
    else:
        print(f"X Could not fetch issue summary")

    return summary


def test_multiple_assignees(client, fi_ids):
    """Test fetching multiple assignees"""
    print(f"\nFetching assignees for {len(fi_ids)} FIs...")
    print("-" * 60)

    assignees = client.get_multiple_assignees(fi_ids)

    print(f"\n{'FI ID':<15} {'Assignee':<25}")
    print("-" * 40)

    for fi_id, assignee in assignees.items():
        assignee_str = assignee if assignee else "N/A"
        print(f"{fi_id:<15} {assignee_str:<25}")

    return assignees


def main():
    """Main test function"""
    print("=" * 60)
    print("JIRA CLIENT TEST")
    print("=" * 60)

    # Test connection
    client = test_connection()

    if not client:
        print("\nX Cannot proceed without valid Jira connection")
        print("\nPlease ensure:")
        print("  1. .env file exists with JIRA_SERVER_NAME and JIRA_ACC_TOKEN")
        print("  2. Environment variables are correctly set")
        print("  3. API token has proper permissions")
        return

    # Sample FI IDs from the esql output
    sample_fis = [
        'FI-59131',
        'FI-58985',
        'FI-60908',
        'FI-59217',
        'FI-59523'
    ]

    # Test single FI
    if len(sys.argv) > 1:
        # Use command line argument if provided
        fi_id = sys.argv[1]
        test_get_assignee(client, fi_id)
        test_get_issue_summary(client, fi_id)
    else:
        # Use first sample FI
        print(f"\n{'=' * 60}")
        print("TEST 1: Single FI Assignee")
        print(f"{'=' * 60}")
        test_get_assignee(client, sample_fis[0])

        print(f"\n{'=' * 60}")
        print("TEST 2: Full Issue Summary")
        print(f"{'=' * 60}")
        test_get_issue_summary(client, sample_fis[0])

        print(f"\n{'=' * 60}")
        print("TEST 3: Multiple FI Assignees")
        print(f"{'=' * 60}")
        test_multiple_assignees(client, sample_fis)

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
