"""
JIRA Integration - Fetch JIRA IDs using first and last names
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from .jira_client import JiraClient, MockJiraClient


@dataclass
class JiraUserInfo:
    """Information retrieved from JIRA user search"""
    account_id: str
    display_name: str
    email_address: Optional[str] = None


class JiraIdFetcher:
    """Fetch JIRA account IDs using first and last names."""

    def __init__(self, use_mock: bool = False):
        """
        Initialize the JIRA ID fetcher.

        Args:
            use_mock: If True, use mock client for testing
        """
        self.use_mock = use_mock

        if use_mock:
            self.client = MockJiraClient()
        else:
            try:
                self.client = JiraClient()
            except ValueError as e:
                raise RuntimeError(f"Failed to initialize JIRA client: {e}")

    def search_user_by_name(self, first_name: str, last_name: str,
                             veritas_email: str = None) -> Optional[JiraUserInfo]:
        """
        Search for a JIRA user by first and last name.

        Args:
            first_name: User's first name
            last_name: User's last name
            veritas_email: Optional Veritas email to help disambiguate multiple results

        Returns:
            JiraUserInfo if user found, None otherwise
        """
        if not first_name or not last_name:
            print("Warning: Both first name and last name are required")
            return None

        # Construct search query (full name)
        search_query = f"{first_name} {last_name}"

        try:
            # Search for user
            users = self.client.search_users(search_query)

            if not users:
                # Try alternative format: lastname, firstname
                search_query = f"{last_name}, {first_name}"
                users = self.client.search_users(search_query)

            if not users:
                # Try just last name if it's unique
                users = self.client.search_users(last_name)

            if not users:
                print(f"Warning: No JIRA user found for {first_name} {last_name}")
                return None

            if len(users) == 1:
                # Single match - use it
                user = users[0]
            else:
                # Multiple matches - try to find best match
                user = self._find_best_match(users, first_name, last_name, veritas_email)
                if not user:
                    print(f"Warning: Multiple JIRA users found for {first_name} {last_name}, cannot disambiguate:")
                    for u in users[:5]:  # Show first 5
                        print(f"  - {u.get('displayName', 'N/A')} ({u.get('emailAddress', 'N/A')})")
                    if len(users) > 5:
                        print(f"  ... and {len(users) - 5} more")
                    print(f"  Skipping - please update manually")
                    return None

            return JiraUserInfo(
                account_id=user.get('accountId', ''),
                display_name=user.get('displayName', ''),
                email_address=user.get('emailAddress')
            )

        except Exception as e:
            print(f"Error searching JIRA for {first_name} {last_name}: {e}")
            return None

    def _find_best_match(self, users: list, first_name: str, last_name: str,
                         veritas_email: str = None) -> Optional[dict]:
        """
        Find the best matching user from multiple results.

        Strategy:
        1. Exact display name match (FirstName LastName)
        2. Email match if veritas_email provided (compare prefix)
        3. Email contains first.last pattern

        Args:
            users: List of user dicts from JIRA API
            first_name: Expected first name
            last_name: Expected last name
            veritas_email: Optional Veritas email for comparison

        Returns:
            Best matching user dict or None if can't disambiguate
        """
        expected_name = f"{first_name} {last_name}".lower()
        email_prefix = veritas_email.split('@')[0].lower() if veritas_email else None
        expected_email_pattern = f"{first_name.lower()}.{last_name.lower()}"

        exact_name_matches = []
        email_matches = []
        pattern_matches = []

        for user in users:
            display_name = user.get('displayName', '').lower()
            user_email = user.get('emailAddress', '').lower()

            # Check for exact name match
            if display_name == expected_name:
                exact_name_matches.append(user)

            # Check if email prefix matches veritas email prefix
            if email_prefix and user_email:
                user_email_prefix = user_email.split('@')[0]
                if user_email_prefix == email_prefix:
                    email_matches.append(user)

            # Check if email follows first.last pattern
            if user_email and expected_email_pattern in user_email:
                pattern_matches.append(user)

        # Return best match in priority order
        if len(exact_name_matches) == 1:
            return exact_name_matches[0]

        if len(email_matches) == 1:
            return email_matches[0]

        if len(pattern_matches) == 1:
            return pattern_matches[0]

        # If exact name match found multiple, use first
        if exact_name_matches:
            return exact_name_matches[0]

        # Can't disambiguate
        return None


class JiraIdUpdater:
    """Update accounts with missing JIRA IDs using first and last names."""

    def __init__(self, account_manager, verbose: bool = False, use_mock: bool = False):
        """
        Initialize the updater.

        Args:
            account_manager: AccountManager instance
            verbose: If True, print detailed progress
            use_mock: If True, use mock JIRA client
        """
        self.account_manager = account_manager
        self.verbose = verbose
        self.fetcher = JiraIdFetcher(use_mock=use_mock)

    def update_missing_jira_ids(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Update JIRA account IDs for accounts that are missing them.
        Also updates cohesity_email if available from JIRA and missing locally.

        Only updates accounts where:
        - first_name and last_name are both present
        - jira_account is NULL or empty
        - manual_verified is 'no'

        Args:
            dry_run: If True, don't actually update the database

        Returns:
            Dictionary with stats: {'total': n, 'updated': n, 'skipped': n, 'failed': n}
        """
        stats = {'total': 0, 'updated': 0, 'skipped': 0, 'failed': 0, 'emails_updated': 0}

        # Get all accounts
        accounts = self.account_manager.get_all_accounts()

        print(f"Scanning {len(accounts)} accounts...")
        print()

        for account in accounts:
            etrack_user_id = account['etrack_user_id']
            first_name = account.get('first_name')
            last_name = account.get('last_name')
            jira_account = account.get('jira_account')
            cohesity_email = account.get('cohesity_email')
            manual_verified = account.get('manual_verified', 'no')

            # Check if update is needed
            needs_jira = not jira_account
            needs_cohesity_email = not cohesity_email
            has_names = first_name and last_name
            not_verified = manual_verified == 'no'

            # Skip if already has both JIRA ID and Cohesity email
            if not needs_jira and not needs_cohesity_email:
                stats['skipped'] += 1
                if self.verbose:
                    print(f"Skipping {etrack_user_id}: Already has JIRA account and Cohesity email")
                continue

            # Skip if manually verified (don't auto-update verified accounts)
            if not not_verified:
                stats['skipped'] += 1
                if self.verbose:
                    print(f"Skipping {etrack_user_id}: Manually verified")
                continue

            # Skip if missing names
            if not has_names:
                stats['skipped'] += 1
                if self.verbose:
                    print(f"Skipping {etrack_user_id}: Missing first or last name")
                continue

            stats['total'] += 1

            # Fetch JIRA user info
            veritas_email = account.get('veritas_email')
            if self.verbose:
                print(f"Processing {etrack_user_id} ({first_name} {last_name})...", end=" ")
            else:
                print(f"Processing {etrack_user_id}...", end=" ")

            user_info = self.fetcher.search_user_by_name(first_name, last_name, veritas_email)

            if not user_info or not user_info.account_id:
                print(f"Failed to find JIRA user")
                stats['failed'] += 1
                continue

            # Build update fields
            update_fields = {}
            updates_desc = []

            if needs_jira:
                update_fields['jira_account'] = user_info.display_name
                updates_desc.append(f"jira_account={user_info.display_name}")

            if needs_cohesity_email and user_info.email_address:
                update_fields['cohesity_email'] = user_info.email_address
                updates_desc.append(f"cohesity_email={user_info.email_address}")
                stats['emails_updated'] += 1

            # Update the account
            if dry_run:
                print(f"Would update {', '.join(updates_desc)}")
                stats['updated'] += 1
            else:
                try:
                    self.account_manager.update_account(
                        etrack_user_id=etrack_user_id,
                        **update_fields
                    )
                    print(f"Updated {', '.join(updates_desc)}")
                    stats['updated'] += 1
                except Exception as e:
                    print(f"Error updating {etrack_user_id}: {e}")
                    stats['failed'] += 1

        return stats

    def update_single_account(self, etrack_user_id: str, dry_run: bool = False) -> bool:
        """
        Update JIRA account ID and Cohesity email for a single account.

        Args:
            etrack_user_id: The etrack user ID to update
            dry_run: If True, don't actually update the database

        Returns:
            True if successful, False otherwise
        """
        account = self.account_manager.get_account(etrack_user_id=etrack_user_id)

        if not account:
            print(f"Account not found: {etrack_user_id}")
            return False

        first_name = account.get('first_name')
        last_name = account.get('last_name')

        if not first_name or not last_name:
            print(f"Error: Account must have both first_name and last_name")
            print(f"  First Name: {first_name or '(missing)'}")
            print(f"  Last Name:  {last_name or '(missing)'}")
            return False

        print(f"Searching JIRA for: {first_name} {last_name}")

        user_info = self.fetcher.search_user_by_name(first_name, last_name)

        if not user_info or not user_info.account_id:
            print("Failed to find JIRA user")
            return False

        print(f"\nFound JIRA user:")
        print(f"  Account ID:   {user_info.account_id}")
        print(f"  Display Name: {user_info.display_name}")
        if user_info.email_address:
            print(f"  Email:        {user_info.email_address}")

        # Build update fields
        update_fields = {}

        if not account.get('jira_account'):
            update_fields['jira_account'] = user_info.display_name

        if not account.get('cohesity_email') and user_info.email_address:
            update_fields['cohesity_email'] = user_info.email_address

        if not update_fields:
            print("\nNo fields need updating (already has JIRA ID and Cohesity email)")
            return True

        if not dry_run:
            try:
                self.account_manager.update_account(
                    etrack_user_id=etrack_user_id,
                    **update_fields
                )
                return True
            except Exception as e:
                print(f"Error updating account: {e}")
                return False

        return True
