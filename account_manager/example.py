#!/usr/bin/env python3
"""
Example usage of the Account Manager package
"""

import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from account_manager import AccountManager, ReportGenerator, IOUtils


def main():
    """Demonstrate various features"""

    # Initialize components
    print("Initializing Account Manager...\n")
    db = AccountManager("example_accounts.db")
    report_gen = ReportGenerator(db)
    io = IOUtils(db)

    # Add sample accounts
    print("Adding sample accounts...")
    try:
        db.add_account(
            etrack_user_id="ET12345",
            veritas_email="john.doe@vcompany.com",
            cohesity_email="john.doe@ccompany.com",
            community_account="johndoe_community",
            jira_account="john.doe"
        )
        print("  + Added: ET12345 (John Doe)")
    except ValueError as e:
        print(f"  • {e}")

    try:
        db.add_account(
            etrack_user_id="ET67890",
            veritas_email="jane.smith@vcompany.com",
            cohesity_email="jane.smith@ccompany.com",
            community_account="janesmith_community",
            jira_account="jane.smith"
        )
        print("  + Added: ET67890 (Jane Smith)")
    except ValueError as e:
        print(f"  • {e}")

    try:
        db.add_account(
            etrack_user_id="ET11111",
            veritas_email="bob.jones@vcompany.com",
            jira_account="bob.jones"
        )
        print("  + Added: ET11111 (Bob Jones - partial data)")
    except ValueError as e:
        print(f"  • {e}")

    # Translation examples
    print("\n" + "=" * 60)
    print("TRANSLATION EXAMPLES")
    print("=" * 60)

    print("\n1. Etrack User ID → Jira Account:")
    jira = db.translate("ET12345", "jira_account")
    print(f"   ET12345 → {jira}")

    print("\n2. Veritas Email → Cohesity Email:")
    cohesity = db.translate("jane.smith@vcompany.com", "cohesity_email")
    print(f"   jane.smith@vcompany.com → {cohesity}")

    print("\n3. Jira Account → Etrack User ID:")
    etrack = db.translate("bob.jones", "etrack_user_id")
    print(f"   bob.jones → {etrack}")

    print("\n4. Community Account → All Fields:")
    etrack = db.translate("johndoe_community", "etrack_user_id")
    veritas = db.translate("johndoe_community", "veritas_email")
    jira = db.translate("johndoe_community", "jira_account")
    print(f"   johndoe_community →")
    print(f"      Etrack: {etrack}")
    print(f"      Veritas: {veritas}")
    print(f"      Jira: {jira}")

    # Search examples
    print("\n" + "=" * 60)
    print("SEARCH EXAMPLES")
    print("=" * 60)

    print("\n1. Search by Cohesity email domain:")
    results = db.search_accounts(cohesity_email="cohesity")
    print(f"   Found {len(results)} accounts with Cohesity email")
    for acc in results:
        print(f"     - {acc['etrack_user_id']}: {acc['cohesity_email']}")

    print("\n2. Search by Jira account pattern:")
    results = db.search_accounts(jira_account="smith")
    print(f"   Found {len(results)} accounts matching 'smith'")
    for acc in results:
        print(f"     - {acc['etrack_user_id']}: {acc['jira_account']}")

    # Update example
    print("\n" + "=" * 60)
    print("UPDATE EXAMPLE")
    print("=" * 60)

    print("\nUpdating Bob Jones' Cohesity email...")
    db.update_account(
        "ET11111",
        cohesity_email="bob.jones@ccompany.com",
        community_account="bobjones_community"
    )
    updated = db.get_account(etrack_user_id="ET11111")
    print(f"  + Updated: {updated['cohesity_email']}")

    # Reports
    print("\n" + "=" * 60)
    print("REPORTS")
    print("=" * 60)

    print("\nSummary Report:")
    print(report_gen.generate_report('summary'))

    print("\nTable Report:")
    print(report_gen.generate_report('table'))

    print("\nCompact Table Report:")
    print(report_gen.generate_compact_table())

    print("\nMissing Fields Report:")
    print(report_gen.generate_report('missing_fields'))

    # Export example
    print("\n" + "=" * 60)
    print("EXPORT/IMPORT")
    print("=" * 60)

    print("\nExporting to CSV...")
    io.export_to_csv("example_export.csv")

    print("\nCSV file created: example_export.csv")
    print("You can edit it and import back using:")
    print("  io.import_from_csv('example_export.csv', 'update')")

    # Cleanup
    print("\n" + "=" * 60)
    db.close()
    print("Done!")


if __name__ == "__main__":
    main()
