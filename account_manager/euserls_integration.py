#!/usr/bin/env python3
"""
euserls Integration Module

This module provides functionality to execute the 'euserls' command and parse
its output to extract Veritas email addresses for etrack users.

The euserls command can be executed locally or remotely via SSH using RMTCMD_HOST.
"""

import subprocess
import os
import shutil
import re
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class EuserInfo:
    """Data class representing euserls output for a user."""
    etrack_user_id: str
    first_name: str
    last_name: str
    phone: str
    pager: str
    status: str
    email: str


class EuserlsExecutor:
    """Execute euserls command and parse output."""

    def __init__(self):
        """Initialize the executor, auto-detecting euserls availability."""
        # Try to find local euserls
        self.euserls_path = shutil.which('euserls')

        if self.euserls_path:
            # Use local euserls
            self.use_ssh = False
        else:
            # Use SSH-based euserls
            self.use_ssh = True
            self.rmtcmd_host = os.environ.get('RMTCMD_HOST')

            if not self.rmtcmd_host:
                raise RuntimeError(
                    "euserls command not found locally and RMTCMD_HOST not set. "
                    "Please install euserls or set RMTCMD_HOST environment variable."
                )

    def get_user_info(self, etrack_user_id: str) -> Optional[EuserInfo]:
        """
        Execute euserls command and parse the output for a specific user.

        Args:
            etrack_user_id: The etrack user ID to query

        Returns:
            EuserInfo object if successful, None if user not found or error
        """
        output = self._execute_euserls(etrack_user_id)
        if not output:
            return None

        return self._parse_output(output, etrack_user_id)

    def get_email(self, etrack_user_id: str) -> Optional[str]:
        """
        Get just the email address for a user.

        Args:
            etrack_user_id: The etrack user ID to query

        Returns:
            Email address string if found, None otherwise
        """
        user_info = self.get_user_info(etrack_user_id)
        return user_info.email if user_info else None

    def _execute_euserls(self, etrack_user_id: str) -> Optional[str]:
        """Execute the euserls command locally or via SSH."""
        try:
            if self.use_ssh:
                # Execute via SSH (use shell=True for SSH command)
                ssh_cmd = f"ssh {self.rmtcmd_host} 'euserls {etrack_user_id}'"
                result = subprocess.run(
                    ssh_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                # Execute locally (use list for local command)
                result = subprocess.run(
                    [self.euserls_path, etrack_user_id],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            if result.returncode != 0:
                print(f"Warning: euserls command failed for {etrack_user_id}")
                print(f"Error: {result.stderr}")
                return None

            return result.stdout

        except subprocess.TimeoutExpired:
            print(f"Error: euserls command timed out for {etrack_user_id}")
            return None
        except Exception as e:
            print(f"Error executing euserls for {etrack_user_id}: {e}")
            return None

    def _parse_output(self, output: str, etrack_user_id: str) -> Optional[EuserInfo]:
        """
        Parse euserls output to extract user information.

        Expected format:
        ---------------------------------------------------------------
        Login           First Last            Phone          Pager          Active
        ===============================================================================

        auser           Amy user          XXX-XXX-XXXX                  Active
        Email:  Amy.user@vcompany.com
        """
        lines = output.strip().split('\n')

        # Find the data line (after the separator lines)
        data_line = None
        email_line = None

        for i, line in enumerate(lines):
            # Skip header and separator lines
            if line.startswith('---') or line.startswith('===') or 'Login' in line:
                continue

            # First non-header line should be the data line
            if not data_line and line.strip():
                data_line = line
                # Next line should be the email
                if i + 1 < len(lines):
                    email_line = lines[i + 1]
                break

        if not data_line or not email_line:
            print(f"Warning: Could not parse euserls output for {etrack_user_id}")
            return None

        # Parse the data line (space-separated fields)
        parts = data_line.split()
        if len(parts) < 2:
            print(f"Warning: Unexpected euserls output format for {etrack_user_id}")
            return None

        login = parts[0]

        # Validate login is not just a placeholder
        if login in ['-', '']:
            print(f"Warning: Invalid login '{login}' for {etrack_user_id}")
            return None

        # Extract email from email line first (most important field)
        email_match = re.search(r'Email:\s+(\S+@\S+)', email_line)
        email = email_match.group(1) if email_match else ""

        if not email:
            print(f"Warning: Could not extract email for {etrack_user_id}")
            return None

        # The last field is typically Active/Inactive status
        status = parts[-1] if len(parts) > 1 else ""

        # Parse name and phone fields (flexible approach)
        # Format can vary: login name(s) [phone] [pager] status
        # Or: login name(s) status (no phone)
        name_parts = []
        phone = ""
        pager = ""

        # Process middle parts (between login and status)
        middle_parts = parts[1:-1] if len(parts) > 2 else []

        phone_index = -1
        for i, part in enumerate(middle_parts):
            # Check if this looks like a phone number (including international formats)
            # Matches: XXX-XXX-XXXX, +XX-X-XXXX-, (XX, (61 2), etc.
            # More aggressive phone detection - if it starts with +, (, or digit and has digits
            is_phone = False
            if part and any(c.isdigit() for c in part):
                # Starts with +, (, or digit - likely phone
                if part[0] in '+(' or part[0].isdigit():
                    is_phone = True
                # Contains X placeholders commonly used for phone
                if 'X' in part and '-' in part:
                    is_phone = True
            # Also catch standalone parenthetical numbers like "(61" or "2)"
            if part and re.match(r'^[\(\d][\dX\-\(\)\+\s]*$', part):
                is_phone = True

            if is_phone:
                phone_index = i
                phone = part
                # Check if next part is continuation of phone or pager
                if i + 1 < len(middle_parts):
                    next_part = middle_parts[i + 1]
                    # If next part also looks like phone/pager continuation, treat as pager
                    if re.match(r'^[\dX\-\(\)\+\s]+\)?$', next_part) or next_part.endswith(')'):
                        pager = next_part
                break

        # Everything before phone (or all of middle if no phone) is name
        if phone_index >= 0:
            name_parts = middle_parts[:phone_index]
        else:
            # No phone found, all middle parts are name (excluding status at the end)
            name_parts = middle_parts

        # Extract first and last name and clean them
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        # Clean up names - remove any trailing phone-like characters/patterns
        # This catches cases like "pentapati +91-2" or "smith (61 2)" where phone got merged with name
        phone_suffix_pattern = r'\s*[\+\(\d][\d\(\)\-\s\+]*$'
        first_name = re.sub(phone_suffix_pattern, '', first_name).strip()
        last_name = re.sub(phone_suffix_pattern, '', last_name).strip()

        return EuserInfo(
            etrack_user_id=login,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            pager=pager,
            status=status,
            email=email
        )


class EuserlsUpdater:
    """Update accounts with missing Veritas emails using euserls."""

    def __init__(self, account_manager, verbose: bool = False):
        """
        Initialize the updater.

        Args:
            account_manager: AccountManager instance
            verbose: Print detailed progress messages
        """
        self.account_manager = account_manager
        self.verbose = verbose
        self.executor = EuserlsExecutor()

    def update_missing_emails(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Update all accounts that have missing Veritas email addresses.

        Args:
            dry_run: If True, only report what would be updated without making changes

        Returns:
            Dictionary with statistics: {'total': n, 'updated': n, 'failed': n, 'skipped': n}
        """
        stats = {'total': 0, 'updated': 0, 'failed': 0, 'skipped': 0}

        # Get all accounts
        accounts = self.account_manager.get_all_accounts()

        for account in accounts:
            etrack_user_id = account['etrack_user_id']
            veritas_email = account.get('veritas_email')
            community_account = account.get('community_account')

            # Skip invalid etrack_user_ids
            if not etrack_user_id or etrack_user_id in ['-', '']:
                if self.verbose:
                    print(f"Skipping invalid etrack_user_id: '{etrack_user_id}'")
                stats['skipped'] += 1
                continue

            # Check what needs to be updated
            needs_email = not veritas_email
            needs_names = not account.get('first_name') and not account.get('last_name')
            needs_community = not community_account

            # Skip if nothing needs updating
            if not needs_email and not needs_names and not needs_community:
                if self.verbose:
                    print(f"Skipping {etrack_user_id}: email, names, and community already set")
                stats['skipped'] += 1
                continue

            stats['total'] += 1

            if self.verbose:
                what_updating = []
                if needs_email:
                    what_updating.append('email')
                if needs_names:
                    what_updating.append('names')
                if needs_community:
                    what_updating.append('community')
                print(f"Fetching {', '.join(what_updating)} for {etrack_user_id}...")

            # Fetch user info using euserls
            user_info = self.executor.get_user_info(etrack_user_id)

            if not user_info:
                print(f"Failed to fetch info for {etrack_user_id}")
                stats['failed'] += 1
                continue

            if dry_run:
                updates = []
                if needs_email:
                    updates.append(f"veritas_email={user_info.email}")
                if needs_names:
                    updates.append(f"first_name={user_info.first_name}")
                    updates.append(f"last_name={user_info.last_name}")
                if needs_community and user_info.email:
                    # Derive community account from email (remove @veritas.com)
                    community = user_info.email.replace('@veritas.com', '')
                    updates.append(f"community_account={community}")
                print(f"Would update {etrack_user_id}: {', '.join(updates)}")
                stats['updated'] += 1
            else:
                # Update the account
                try:
                    update_fields = {}

                    # Update email if missing
                    if needs_email:
                        update_fields['veritas_email'] = user_info.email

                    # Update names if both are missing
                    if needs_names:
                        update_fields['first_name'] = user_info.first_name
                        update_fields['last_name'] = user_info.last_name

                    # Update community account if missing (derive from email)
                    if needs_community and user_info.email:
                        update_fields['community_account'] = user_info.email.replace('@veritas.com', '')

                    self.account_manager.update_account(
                        etrack_user_id=etrack_user_id,
                        **update_fields
                    )

                    updates = []
                    if needs_email:
                        updates.append(f"veritas_email={user_info.email}")
                    if needs_names:
                        updates.append(f"first_name={user_info.first_name}, last_name={user_info.last_name}")
                    if needs_community and user_info.email:
                        updates.append(f"community_account={user_info.email.replace('@veritas.com', '')}")
                    print(f"Updated {etrack_user_id}: {', '.join(updates)}")
                    stats['updated'] += 1
                except Exception as e:
                    print(f"Error updating {etrack_user_id}: {e}")
                    stats['failed'] += 1

        return stats

    def update_single_account(self, etrack_user_id: str, dry_run: bool = False) -> bool:
        """
        Update a single account's Veritas email, names, and community account.

        Args:
            etrack_user_id: The etrack user ID to update
            dry_run: If True, only report what would be updated without making changes

        Returns:
            True if successful, False otherwise
        """
        if self.verbose:
            print(f"Fetching email for {etrack_user_id}...")

        # Fetch user info using euserls
        user_info = self.executor.get_user_info(etrack_user_id)

        if not user_info:
            print(f"Failed to fetch email for {etrack_user_id}")
            return False

        # Check if we should update names (both must be missing)
        account = self.account_manager.get_account(etrack_user_id=etrack_user_id)
        update_names = account and not account.get('first_name') and not account.get('last_name')
        update_community = account and not account.get('community_account') and user_info.email

        if dry_run:
            updates = [f"veritas_email={user_info.email}"]
            if update_names:
                updates.append(f"first_name={user_info.first_name}")
                updates.append(f"last_name={user_info.last_name}")
            if update_community:
                updates.append(f"community_account={user_info.email.replace('@veritas.com', '')}")
            print(f"Would update {etrack_user_id}: {', '.join(updates)}")
            return True

        try:
            update_fields = {'veritas_email': user_info.email}

            # Only update names if both are missing
            if update_names:
                update_fields['first_name'] = user_info.first_name
                update_fields['last_name'] = user_info.last_name

            # Update community account if missing (derive from email)
            if update_community:
                update_fields['community_account'] = user_info.email.replace('@veritas.com', '')

            self.account_manager.update_account(
                etrack_user_id=etrack_user_id,
                **update_fields
            )
            updates = [f"veritas_email={user_info.email}"]
            if update_names:
                updates.append(f"first_name={user_info.first_name}, last_name={user_info.last_name}")
            if update_community:
                updates.append(f"community_account={user_info.email.replace('@veritas.com', '')}")
            print(f"Updated {etrack_user_id}: {', '.join(updates)}")
            return True
        except Exception as e:
            print(f"Error updating {etrack_user_id}: {e}")
            return False


if __name__ == "__main__":
    # Test the euserls integration
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 euserls_integration.py <etrack_user_id>")
        sys.exit(1)

    executor = EuserlsExecutor()
    user_info = executor.get_user_info(sys.argv[1])

    if user_info:
        print(f"\nUser Information:")
        print(f"  Etrack ID: {user_info.etrack_user_id}")
        print(f"  Name: {user_info.first_name} {user_info.last_name}")
        print(f"  Email: {user_info.email}")
        print(f"  Phone: {user_info.phone}")
        print(f"  Status: {user_info.status}")
    else:
        print(f"Failed to fetch information for {sys.argv[1]}")
