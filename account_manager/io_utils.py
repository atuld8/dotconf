"""
Import/Export utilities for account data
"""

import csv
import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import AccountManager


class IOUtils:
    """Handles import and export operations"""

    def __init__(self, account_manager: 'AccountManager'):
        """
        Initialize IO utilities

        Args:
            account_manager: AccountManager instance
        """
        self.am = account_manager

    def export_to_csv(self, filename: str = "accounts_export.csv"):
        """
        Export all accounts to CSV file

        Args:
            filename: Output CSV filename
        """
        accounts = self.am.get_all_accounts()

        if not accounts:
            print("No accounts to export")
            return

        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['id', 'etrack_user_id', 'first_name', 'last_name', 'veritas_email', 'cohesity_email',
                         'community_account', 'jira_account', 'manual_verified', 'notes', 'created_at', 'updated_at']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for account in accounts:
                writer.writerow(account)

        self.am.log_action('export_accounts', 'file', filename,
                          new_value=f"{len(accounts)} accounts", status='success')
        print(f"Exported {len(accounts)} accounts to {filename}")

    def import_from_csv(self, filename: str, conflict_mode: str = 'skip', allow_empty: bool = False) -> Dict[str, int]:
        """
        Import accounts from CSV file

        Args:
            filename: Input CSV filename
            conflict_mode: How to handle existing etrack_user_ids
                          'skip' - Skip existing records (default)
                          'update' - Update existing records with new data
                          'fail' - Raise error on conflict
            allow_empty: If True, empty CSV values will overwrite existing data
                         If False (default), only non-empty values update existing data

        Returns:
            Dictionary with statistics: {'added': n, 'updated': n, 'skipped': n, 'errors': n}
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"CSV file not found: {filename}")

        if conflict_mode not in ['skip', 'update', 'fail']:
            raise ValueError("conflict_mode must be 'skip', 'update', or 'fail'")

        stats = {'added': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        errors = []

        with open(filename, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)

            # Validate required fields
            if 'etrack_user_id' not in reader.fieldnames:
                raise ValueError("CSV must contain 'etrack_user_id' column")

            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                etrack_user_id = row.get('etrack_user_id', '').strip()

                if not etrack_user_id:
                    errors.append(f"Row {row_num}: Missing etrack_user_id")
                    stats['errors'] += 1
                    continue

                # Check if account exists
                existing = self.am.get_account(etrack_user_id=etrack_user_id)

                try:
                    if existing:
                        if conflict_mode == 'fail':
                            raise ValueError(f"Account with etrack_user_id '{etrack_user_id}' already exists")
                        elif conflict_mode == 'skip':
                            stats['skipped'] += 1
                            continue
                        elif conflict_mode == 'update':
                            # Update existing record
                            update_data = {}
                            fields = ['first_name', 'last_name', 'veritas_email', 'cohesity_email',
                                      'community_account', 'jira_account', 'manual_verified', 'notes']

                            for field in fields:
                                if field in row:
                                    value = row[field].strip() if row[field] else ''
                                    if value:  # Non-empty value - always update
                                        update_data[field] = value
                                    elif allow_empty:  # Empty value with --allow-empty
                                        update_data[field] = None

                            if update_data:
                                self.am.update_account(etrack_user_id, **update_data)
                                self.am.log_action('import_accounts', 'account', etrack_user_id,
                                                  new_value=str(update_data), status='success')
                                stats['updated'] += 1
                            else:
                                stats['skipped'] += 1
                    else:
                        # Add new record
                        self.am.add_account(
                            etrack_user_id=etrack_user_id,
                            first_name=row.get('first_name', '').strip() or None,
                            last_name=row.get('last_name', '').strip() or None,
                            veritas_email=row.get('veritas_email', '').strip() or None,
                            cohesity_email=row.get('cohesity_email', '').strip() or None,
                            community_account=row.get('community_account', '').strip() or None,
                            jira_account=row.get('jira_account', '').strip() or None,
                            manual_verified=row.get('manual_verified', 'no').strip() or 'no',
                            notes=row.get('notes', '').strip() or None
                        )
                        self.am.log_action('import_accounts', 'account', etrack_user_id,
                                          new_value='added', status='success')
                        stats['added'] += 1

                except Exception as e:
                    errors.append(f"Row {row_num} (etrack_user_id: {etrack_user_id}): {str(e)}")
                    self.am.log_action('import_accounts', 'account', etrack_user_id,
                                      status='failed', details=str(e))
                    stats['errors'] += 1

        # Print summary
        print(f"\nImport completed from {filename}")
        print(f"  Added:   {stats['added']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Errors:  {stats['errors']}")

        if errors:
            print("\nErrors encountered:")
            for error in errors[:10]:  # Show first 10 errors
                print(f"  • {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")

        return stats

    def export_action_log(self, filename: str = "action_log_export.csv", limit: int = None,
                          since: str = None):
        """
        Export action log to CSV file

        Args:
            filename: Output CSV filename
            limit: Maximum number of entries to export (None = all)
            since: Only export entries on or after this date (YYYY-MM-DD)
        """
        # Get all action log entries (use high limit if not specified)
        actions = self.am.get_action_log(limit=limit or 100000, since=since)

        if not actions:
            print("No action log entries to export")
            return

        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['id', 'action_type', 'target_type', 'target_id',
                         'old_value', 'new_value', 'status', 'details', 'created_at']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for action in actions:
                writer.writerow(action)

        print(f"Exported {len(actions)} action log entries to {filename}")

    def import_action_log(self, filename: str) -> Dict[str, int]:
        """
        Import action log from CSV file

        Args:
            filename: Input CSV filename

        Returns:
            Dictionary with statistics: {'added': n, 'errors': n}
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"CSV file not found: {filename}")

        stats = {'added': 0, 'errors': 0}
        errors = []

        with open(filename, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)

            # Validate required fields
            required = ['action_type']
            for field in required:
                if field not in reader.fieldnames:
                    raise ValueError(f"CSV must contain '{field}' column")

            for row_num, row in enumerate(reader, start=2):
                try:
                    self.am.log_action(
                        action_type=row.get('action_type', '').strip(),
                        target_type=row.get('target_type', '').strip() or None,
                        target_id=row.get('target_id', '').strip() or None,
                        old_value=row.get('old_value', '').strip() or None,
                        new_value=row.get('new_value', '').strip() or None,
                        status=row.get('status', 'success').strip() or 'success',
                        details=row.get('details', '').strip() or None
                    )
                    stats['added'] += 1
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    stats['errors'] += 1

        print(f"\nImport completed from {filename}")
        print(f"  Added:  {stats['added']}")
        print(f"  Errors: {stats['errors']}")

        if errors:
            print("\nErrors encountered:")
            for error in errors[:10]:
                print(f"  • {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more errors")

        return stats
