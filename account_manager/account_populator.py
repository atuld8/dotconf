#!/usr/bin/env python3
"""
Account Populator - Auto-populate account details from various sources
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AccountData:
    """Container for account data from various sources"""
    etrack_user_id: str
    veritas_email: Optional[str] = None
    cohesity_email: Optional[str] = None
    community_account: Optional[str] = None
    jira_account: Optional[str] = None
    source: str = "inferred"  # Source of the data: jira, ldap, inferred, manual
    confidence: str = "low"  # Confidence level: high, medium, low

    def is_complete(self) -> bool:
        """Check if all fields are populated"""
        return all([
            self.etrack_user_id,
            self.veritas_email,
            self.cohesity_email,
            self.jira_account
        ])

    def missing_fields(self) -> list:
        """Get list of missing fields"""
        missing = []
        if not self.veritas_email:
            missing.append('veritas_email')
        if not self.cohesity_email:
            missing.append('cohesity_email')
        if not self.jira_account:
            missing.append('jira_account')
        if not self.community_account:
            missing.append('community_account')
        return missing


class AccountPopulator:
    """Auto-populate account details from various sources"""

    def __init__(self, jira_client=None):
        """
        Initialize Account Populator

        Args:
            jira_client: Optional Jira client for fetching user details
        """
        self.jira_client = jira_client

    def infer_from_etrack_user_id(self, etrack_user_id: str) -> AccountData:
        """
        Infer account details from etrack_user_id

        Strategy (CONSERVATIVE - may not match all patterns):
        - etrack_user_id is the username (e.g., 'john_doe', 'jane.smith')
        - Jira account: MAY BE DIFFERENT (could be firstname.lastname, different format)
        - Veritas email: MAY BE DIFFERENT (could be firstname.lastname@vcompany.com)
        - Cohesity email: MAY BE DIFFERENT (could follow different pattern)
        - Community account: Veritas email WITHOUT @vcompany.com domain

        WARNING: These are LOW CONFIDENCE inferences. Use --interactive mode
                 to verify and correct, or pre-populate from LDAP/HR system.

        Args:
            etrack_user_id: Etrack User ID

        Returns:
            AccountData with inferred fields (LOW CONFIDENCE)
        """
        account = AccountData(etrack_user_id=etrack_user_id)

        # Convert username format: john_doe -> john.doe
        email_username = etrack_user_id.replace('_', '.')

        # GUESS Veritas email (LOW CONFIDENCE)
        # Actual pattern may vary: could be firstname.lastname, abbrev, etc.
        account.veritas_email = f"{email_username}@veritas.com"

        # GUESS Cohesity email (LOW CONFIDENCE)
        # May follow different pattern than Veritas
        account.cohesity_email = f"{email_username}@cohesity.com"

        # Community account = Veritas email without domain
        # e.g., john.doe@vcompany.com -> john.doe
        account.community_account = email_username

        # Jira account: Set to None - too unreliable to guess
        # Could be same as etrack_user_id, could be different
        account.jira_account = None

        account.source = "inferred_from_etrack"
        account.confidence = "low"  # Changed to LOW due to pattern variations

        return account

    def fetch_from_jira(self, jira_username: str) -> Optional[AccountData]:
        """
        Fetch user details from Jira

        Args:
            jira_username: Jira username

        Returns:
            AccountData with Jira user details or None
        """
        if not self.jira_client:
            return None

        try:
            # Get user details from Jira
            # Note: This requires Jira user API endpoint
            # For now, we know jira_account with HIGH confidence
            account = AccountData(
                etrack_user_id=jira_username,  # Assume same, may need correction
                jira_account=jira_username,     # HIGH confidence - from Jira API
                source="jira",
                confidence="medium"  # Medium because etrack_user_id is assumed
            )

            # Try to infer emails from Jira username
            email_username = jira_username.replace('_', '.')
            account.veritas_email = f"{email_username}@veritas.com"
            account.cohesity_email = f"{email_username}@cohesity.com"

            # Community account = email prefix without domain
            account.community_account = email_username

            return account

        except Exception as e:
            print(f"Error fetching from Jira: {e}")
            return None

    def populate_from_jira_assignee(self, fi_id: str, etrack_user_id: str = None) -> Optional[AccountData]:
        """
        Populate account data from FI assignee
        Creates account with HIGH confidence jira_account from Jira,
        and LOW confidence other fields from inference

        Args:
            fi_id: FI ID (e.g., 'FI-59131')
            etrack_user_id: Optional etrack_user_id if known

        Returns:
            AccountData or None
        """
        if not self.jira_client:
            return None

        try:
            # Get assignee from Jira (HIGH confidence)
            jira_assignee = self.jira_client.get_assignee(fi_id)
            if not jira_assignee:
                return None

            # Use provided etrack_user_id or assume same as jira
            etrack_id = etrack_user_id or jira_assignee

            # Infer email format from jira username
            email_username = jira_assignee.replace('_', '.')

            account = AccountData(
                etrack_user_id=etrack_id,
                jira_account=jira_assignee,  # HIGH confidence from Jira API
                veritas_email=f"{email_username}@veritas.com",
                cohesity_email=f"{email_username}@cohesity.com",
                community_account=email_username,  # Email prefix without domain
                source="jira_assignee",
                confidence="medium"  # jira_account is HIGH, others are LOW
            )

            return account

        except Exception as e:
            print(f"Error fetching assignee from {fi_id}: {e}")
            return None

    def merge_account_data(self, *accounts: AccountData) -> AccountData:
        """
        Merge multiple AccountData objects, preferring higher confidence data

        Args:
            *accounts: Variable number of AccountData objects

        Returns:
            Merged AccountData
        """
        if not accounts:
            raise ValueError("At least one account data required")

        # Start with first account
        merged = AccountData(etrack_user_id=accounts[0].etrack_user_id)

        # Confidence ranking
        confidence_rank = {'high': 3, 'medium': 2, 'low': 1}

        # Merge each field, preferring higher confidence
        for account in accounts:
            if account.jira_account and (
                not merged.jira_account or
                confidence_rank.get(account.confidence, 0) > confidence_rank.get(merged.confidence, 0)
            ):
                merged.jira_account = account.jira_account

            if account.veritas_email and not merged.veritas_email:
                merged.veritas_email = account.veritas_email

            if account.cohesity_email and not merged.cohesity_email:
                merged.cohesity_email = account.cohesity_email

            if account.community_account and not merged.community_account:
                merged.community_account = account.community_account

        # Set source and confidence
        sources = [a.source for a in accounts if a.source]
        merged.source = ", ".join(set(sources))

        # Confidence is highest among sources
        merged.confidence = max(
            (a.confidence for a in accounts if a.confidence),
            key=lambda c: confidence_rank.get(c, 0)
        )

        return merged

    def validate_email(self, email: str) -> bool:
        """
        Validate email format

        Args:
            email: Email address

        Returns:
            True if valid format, False otherwise
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def interactive_populate(self, etrack_user_id: str, inferred: AccountData) -> AccountData:
        """
        Interactively populate account data with user input

        Args:
            etrack_user_id: Etrack User ID
            inferred: Inferred AccountData to use as defaults

        Returns:
            AccountData with user-confirmed values
        """
        print(f"\n{'=' * 60}")
        print(f"New User Detected: {etrack_user_id}")
        print(f"{'=' * 60}")
        print("Please review and confirm the inferred account details:")
        print()

        # Jira Account
        print(f"Jira Account [{inferred.jira_account}]: ", end="")
        jira_input = input().strip()
        jira_account = jira_input if jira_input else inferred.jira_account

        # Veritas Email
        print(f"Veritas Email [{inferred.veritas_email}]: ", end="")
        veritas_input = input().strip()
        veritas_email = veritas_input if veritas_input else inferred.veritas_email

        # Cohesity Email
        print(f"Cohesity Email [{inferred.cohesity_email}]: ", end="")
        cohesity_input = input().strip()
        cohesity_email = cohesity_input if cohesity_input else inferred.cohesity_email

        # Community Account
        print(f"Community Account [{inferred.community_account}]: ", end="")
        community_input = input().strip()
        community_account = community_input if community_input else inferred.community_account

        return AccountData(
            etrack_user_id=etrack_user_id,
            jira_account=jira_account,
            veritas_email=veritas_email,
            cohesity_email=cohesity_email,
            community_account=community_account,
            source="manual",
            confidence="high"
        )


class AutoPopulateStrategy:
    """Strategies for auto-populating accounts"""

    # Always auto-populate with inferred data (no confirmation)
    AUTO = "auto"

    # Prompt user to confirm inferred data
    INTERACTIVE = "interactive"

    # Skip auto-population, just warn
    SKIP = "skip"

    # Fail when unknown user is encountered
    FAIL = "fail"


def format_account_data(account: AccountData) -> str:
    """
    Format AccountData for display

    Args:
        account: AccountData to format

    Returns:
        Formatted string
    """
    lines = [
        f"Etrack User ID: {account.etrack_user_id}",
        f"Jira Account:   {account.jira_account or 'N/A'}",
        f"Veritas Email:  {account.veritas_email or 'N/A'}",
        f"Cohesity Email: {account.cohesity_email or 'N/A'}",
        f"Community Acct: {account.community_account or 'N/A'}",
        f"Source:         {account.source}",
        f"Confidence:     {account.confidence}"
    ]

    missing = account.missing_fields()
    if missing:
        lines.append(f"Missing:        {', '.join(missing)}")

    return "\n".join(lines)
