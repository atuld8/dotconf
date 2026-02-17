"""
FI Validator - Validate FI assignees against Jira and account database
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from .esql_integration import FIRecord
from .models import AccountManager, is_valid_etrack_user_id
from .account_populator import AccountPopulator, AccountData, AutoPopulateStrategy, format_account_data


@dataclass
class AssigneeInfo:
    """Information about a FI assignee"""
    fi_id: str
    jira_assignee: Optional[str]  # Current assignee from Jira
    expected_jira_id: Optional[str]  # Expected from database (etrack assignee's jira_account)
    matches: bool
    error: Optional[str] = None

    def __str__(self):
        status = "+ MATCH" if self.matches else "X MISMATCH"
        return f"{self.fi_id}: {status} (Jira: {self.jira_assignee}, Expected: {self.expected_jira_id})"


@dataclass
class ValidationResult:
    """Result of FI validation"""
    incident_no: str
    etrack_user_id: str  # The etrack assignee (who should own the FI)
    who_added_fi: str    # Who added the FI (may be different from etrack assignee)
    fi_validations: List[AssigneeInfo]
    jira_assignee: Optional[str] = None
    db_jira_account: Optional[str] = None  # Expected jira_account from DB for etrack_user_id
    fi_id: Optional[str] = None  # Primary FI ID
    status: str = "unknown"  # matched, mismatched, unknown_user, error
    was_auto_added: bool = False  # True if account was auto-populated

    @property
    def all_match(self) -> bool:
        """Check if all FI assignments match"""
        return all(v.matches for v in self.fi_validations)

    @property
    def mismatch_count(self) -> int:
        """Count of mismatched FIs"""
        return sum(1 for v in self.fi_validations if not v.matches)


class FIValidator:
    """Validate FI assignees against database"""

    def __init__(self, account_manager: AccountManager, jira_client=None,
                 auto_populate_strategy: str = AutoPopulateStrategy.SKIP):
        """
        Initialize FI Validator

        Args:
            account_manager: AccountManager instance
            jira_client: Optional Jira client
            auto_populate_strategy: Strategy for handling unknown users
                - AUTO: Auto-populate with inferred data
                - INTERACTIVE: Prompt user for confirmation
                - SKIP: Skip and warn (default)
                - FAIL: Fail when unknown user found
        """
        self.am = account_manager
        self.jira_client = jira_client
        self.auto_populate_strategy = auto_populate_strategy
        self.populator = AccountPopulator(jira_client)
        self.new_users_added = []  # Track newly added users
        self._processed_users = set()  # Track users already processed in this session to avoid duplicates

    def get_expected_jira_id(self, etrack_user_id: str, auto_add: bool = True) -> Optional[str]:
        """
        Get expected Jira ID from database using etrack_user_id
        If not found and auto_add is True, attempt to populate account

        Args:
            etrack_user_id: Etrack User ID
            auto_add: Whether to auto-populate if not found

        Returns:
            Jira account ID or None if not found
        """
        jira_account = self.am.translate(etrack_user_id, 'jira_account')

        if not jira_account and auto_add:
            jira_account = self._handle_missing_account(etrack_user_id)

        return jira_account

    def _handle_missing_account(self, etrack_user_id: str, jira_assignee: str = None) -> Optional[str]:
        """
        Handle missing account based on auto_populate_strategy

        AUTO mode: Only adds etrack_user_id, leaves other fields empty for later update
        INTERACTIVE mode: Uses Jira assignee as default and prompts for all fields

        Args:
            etrack_user_id: Etrack User ID
            jira_assignee: Optional Jira assignee (HIGH confidence)

        Returns:
            Jira account if successfully added, None otherwise
        """
        # Validate etrack_user_id before processing
        if not is_valid_etrack_user_id(etrack_user_id):
            print(f"* Skipping invalid etrack_user_id: '{etrack_user_id}' (placeholder/empty value)")
            return None

        # Check if already processed in this session to avoid duplicate attempts
        if etrack_user_id in self._processed_users:
            return None

        # Mark as processed regardless of outcome
        self._processed_users.add(etrack_user_id)

        # Also check if account now exists (may have been added by another process)
        existing = self.am.get_account(etrack_user_id=etrack_user_id)
        if existing:
            return existing.get('jira_account')

        if self.auto_populate_strategy == AutoPopulateStrategy.FAIL:
            raise ValueError(f"Unknown user '{etrack_user_id}' and FAIL strategy is set")

        if self.auto_populate_strategy == AutoPopulateStrategy.SKIP:
            print(f"* Warning: No Jira account found for etrack_user_id '{etrack_user_id}' (skipping auto-population)")
            return None

        if self.auto_populate_strategy == AutoPopulateStrategy.INTERACTIVE:
            # Infer account data with Jira assignee as default
            inferred = self.populator.infer_from_etrack_user_id(etrack_user_id)
            if jira_assignee:
                inferred.jira_account = jira_assignee

            # Prompt user for confirmation
            account_data = self.populator.interactive_populate(etrack_user_id, inferred)
        else:  # AUTO - minimal data, user will update later
            print(f"\n+ Auto-adding minimal account for '{etrack_user_id}' (fields left empty for later update)")
            account_data = AccountData(
                etrack_user_id=etrack_user_id,
                veritas_email=None,
                cohesity_email=None,
                community_account=None,
                jira_account=None,
                source="auto_minimal",
                confidence="low"
            )

        # Add to database
        try:
            self.am.add_account(
                etrack_user_id=account_data.etrack_user_id,
                veritas_email=account_data.veritas_email,
                cohesity_email=account_data.cohesity_email,
                community_account=account_data.community_account,
                jira_account=account_data.jira_account
            )
            self.new_users_added.append(account_data)
            print(f"+ Added account for '{etrack_user_id}' (update later with: cli.py update {etrack_user_id})\n")
            return account_data.jira_account

        except Exception as e:
            print(f"X Failed to add account for '{etrack_user_id}': {e}")
            return None

    def get_jira_assignee(self, fi_id: str) -> Optional[str]:
        """
        Get current assignee from Jira for a FI

        Args:
            fi_id: FI ID (e.g., 'FI-59131')

        Returns:
            Jira assignee username or None

        Note:
            This is a placeholder. Will be implemented with actual Jira API
        """
        if self.jira_client:
            return self.jira_client.get_assignee(fi_id)

        # Placeholder - will be replaced with actual Jira API call
        print(f"Warning: No Jira client configured. Cannot fetch assignee for {fi_id}")
        return None

    def validate_fi_record(self, record: FIRecord) -> ValidationResult:
        """
        Validate a single FI record.

        Validation Logic:
        - etrack_user_id is the etrack assignee (who should own the FI in Jira)
        - who_added_fi is who added the FI (may differ from etrack assignee)
        - We check: FI's Jira assignee == etrack_user_id's jira_account from database

        Example:
        - Etrack 1234567 is assigned to user_one
        - user_one's jira_account in DB = "user.one"
        - FI-10001 should be assigned to "user.one" in Jira
        - If FI-10001 is assigned to "user.two", it's a MISMATCH

        Args:
            record: FIRecord to validate

        Returns:
            ValidationResult with assignee comparisons
        """
        validations = []

        # Skip validation for invalid etrack_user_id values (placeholders like '-', 'N/A', etc.)
        if not is_valid_etrack_user_id(record.etrack_user_id):
            return ValidationResult(
                incident_no=record.incident_no,
                etrack_user_id=record.etrack_user_id,
                who_added_fi=record.who_added_fi,
                fi_validations=[],
                db_jira_account=None,
                status="skipped_invalid_user"
            )

        # Get expected Jira ID for the etrack assignee from database
        expected_jira_id = self.am.translate(record.etrack_user_id, 'jira_account')

        # If not in database and auto-population enabled, try to add
        if not expected_jira_id and self.auto_populate_strategy != AutoPopulateStrategy.SKIP:
            expected_jira_id = self._handle_missing_account(record.etrack_user_id, None)

        # Validate each FI
        for fi_id in record.fi_ids:
            try:
                # Get current Jira assignee for this FI
                jira_assignee = self.get_jira_assignee(fi_id)

                # Compare: FI's Jira assignee should match etrack assignee's jira_account
                matches = False
                if jira_assignee and expected_jira_id:
                    # Case-insensitive comparison
                    matches = jira_assignee.lower() == expected_jira_id.lower()

                validation = AssigneeInfo(
                    fi_id=fi_id,
                    jira_assignee=jira_assignee,
                    expected_jira_id=expected_jira_id,
                    matches=matches,
                    error=None
                )
                validations.append(validation)

            except Exception as e:
                validation = AssigneeInfo(
                    fi_id=fi_id,
                    jira_assignee=None,
                    expected_jira_id=expected_jira_id,
                    matches=False,
                    error=str(e)
                )
                validations.append(validation)

        # Determine overall status
        if not expected_jira_id:
            status = "unknown_user"
        elif all(v.matches for v in validations):
            status = "matched"
        else:
            status = "mismatched"

        return ValidationResult(
            incident_no=record.incident_no,
            etrack_user_id=record.etrack_user_id,
            who_added_fi=record.who_added_fi,
            fi_validations=validations,
            db_jira_account=expected_jira_id,
            status=status
        )

    def validate_records(self, records: List[FIRecord]) -> List[ValidationResult]:
        """
        Validate multiple FI records with batch Jira API calls for performance.

        This method pre-fetches all FI assignees in batch before validation,
        reducing API calls from N (per FI) to ceil(N/50) batch requests.

        Args:
            records: List of FIRecord objects

        Returns:
            List of ValidationResult objects
        """
        if not records:
            return []

        # Collect all unique FI IDs across all records
        all_fi_ids = set()
        for record in records:
            all_fi_ids.update(record.fi_ids)

        all_fi_ids = list(all_fi_ids)
        total_fis = len(all_fi_ids)
        total_records = len(records)

        # Batch fetch all FI assignees from Jira
        fi_assignees = {}
        if self.jira_client and all_fi_ids:
            print(f"Fetching {total_fis} FI assignees from Jira (batched)...")
            fi_assignees = self.jira_client.get_multiple_assignees(all_fi_ids)
            print(f"+ Fetched {len(fi_assignees)} FI assignees")

        # Now validate records using pre-fetched data
        results = []
        for i, record in enumerate(records, 1):
            if i % 50 == 0 or i == total_records:
                print(f"\rValidating: {i}/{total_records} records...", end='', flush=True)
            result = self._validate_fi_record_with_cache(record, fi_assignees)
            results.append(result)
        print()  # New line after progress
        return results

    def _validate_fi_record_with_cache(self, record: FIRecord, fi_assignees: Dict[str, Optional[str]]) -> ValidationResult:
        """
        Validate a single FI record using pre-fetched assignee cache.

        Args:
            record: FIRecord to validate
            fi_assignees: Pre-fetched dict mapping FI ID to assignee name

        Returns:
            ValidationResult with assignee comparisons
        """
        validations = []

        # Get expected Jira ID for the etrack assignee from database
        expected_jira_id = self.am.translate(record.etrack_user_id, 'jira_account')

        # If not in database and auto-population enabled, try to add
        if not expected_jira_id and self.auto_populate_strategy != AutoPopulateStrategy.SKIP:
            expected_jira_id = self._handle_missing_account(record.etrack_user_id, None)

        # Validate each FI using cached data
        for fi_id in record.fi_ids:
            try:
                # Get assignee from cache (or None if not found)
                jira_assignee = fi_assignees.get(fi_id)

                # Compare: FI's Jira assignee should match etrack assignee's jira_account
                matches = False
                if jira_assignee and expected_jira_id:
                    # Case-insensitive comparison
                    matches = jira_assignee.lower() == expected_jira_id.lower()

                validation = AssigneeInfo(
                    fi_id=fi_id,
                    jira_assignee=jira_assignee,
                    expected_jira_id=expected_jira_id,
                    matches=matches,
                    error=None
                )
                validations.append(validation)

            except Exception as e:
                validation = AssigneeInfo(
                    fi_id=fi_id,
                    jira_assignee=None,
                    expected_jira_id=expected_jira_id,
                    matches=False,
                    error=str(e)
                )
                validations.append(validation)

        # Determine overall status
        if not expected_jira_id:
            status = "unknown_user"
        elif all(v.matches for v in validations):
            status = "matched"
        else:
            status = "mismatched"

        return ValidationResult(
            incident_no=record.incident_no,
            etrack_user_id=record.etrack_user_id,
            who_added_fi=record.who_added_fi,
            fi_validations=validations,
            db_jira_account=expected_jira_id,
            status=status
        )

    def get_mismatches(self, results: List[ValidationResult]) -> List[ValidationResult]:
        """
        Filter validation results to only mismatches

        Args:
            results: List of ValidationResult objects

        Returns:
            List of results with at least one mismatch
        """
        return [r for r in results if not r.all_match]

    def generate_report(self, results: List[ValidationResult]) -> str:
        """
        Generate a validation report with both table and detailed formats

        Args:
            results: List of ValidationResult objects

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 120)
        report.append("FI ASSIGNEE VALIDATION REPORT")
        report.append("=" * 120)
        report.append(f"Total Records Validated: {len(results)}")

        mismatches = self.get_mismatches(results)
        unknown_users = [r for r in results if r.status == "unknown_user"]
        matched = [r for r in results if r.status == "matched"]

        report.append(f"Matched Records: {len(matched)}")
        report.append(f"Mismatched Records: {len(mismatches)}")
        report.append(f"Unknown Users (not in DB): {len(unknown_users)}")
        report.append("")

        if not mismatches and not unknown_users:
            report.append("+ All FI assignments match expected values!")
            report.append("=" * 120)
            return "\n".join(report)

        # === TABLE FORMAT ===
        if mismatches or unknown_users:
            report.append("=" * 120)
            report.append("SUMMARY TABLE")
            report.append("=" * 120)

            # Table header
            header = f"{'Incident':<12} | {'Etrack Assignee':<20} | {'FI IDs':<25} | {'Expected (DB)':<20} | {'Actual (Jira)':<20} | {'Status':<12}"
            report.append(header)
            report.append("-" * 120)

            # Unknown users in table
            for result in unknown_users:
                fi_ids = ', '.join([v.fi_id for v in result.fi_validations]) or 'N/A'
                if len(fi_ids) > 23:
                    fi_ids = fi_ids[:20] + '...'
                row = f"{result.incident_no:<12} | {result.etrack_user_id:<20} | {fi_ids:<25} | {'N/A':<20} | {'N/A':<20} | {'UNKNOWN':<12}"
                report.append(row)

            # Mismatches in table
            for result in mismatches:
                for v in result.fi_validations:
                    if not v.matches:
                        expected = (result.db_jira_account or 'N/A')[:18]
                        actual = (v.jira_assignee or 'N/A')[:18]
                        row = f"{result.incident_no:<12} | {result.etrack_user_id:<20} | {v.fi_id:<25} | {expected:<20} | {actual:<20} | {'MISMATCH':<12}"
                        report.append(row)

            report.append("-" * 120)
            report.append("")

        # === DETAILED FORMAT ===
        if unknown_users:
            report.append("=" * 120)
            report.append("UNKNOWN USERS (not in database) - DETAILS")
            report.append("-" * 120)
            for result in unknown_users:
                fi_ids = ', '.join([v.fi_id for v in result.fi_validations]) or 'N/A'
                report.append(f"  Incident: {result.incident_no} | Etrack Assignee: {result.etrack_user_id} | FIs: {fi_ids}")
                report.append(f"    → Add user: python3 -m account_manager.cli add {result.etrack_user_id}")
            report.append("")

        if mismatches:
            report.append("=" * 120)
            report.append("MISMATCHES - DETAILS")
            report.append("-" * 120)
            report.append("(FI assignee in Jira does not match etrack assignee's jira_account in DB)")
            report.append("")

            for result in mismatches:
                fi_ids = ', '.join([v.fi_id for v in result.fi_validations])
                report.append(f"Incident: {result.incident_no} | FIs: {fi_ids}")
                report.append(f"  Etrack Assignee: {result.etrack_user_id}")
                report.append(f"  Expected Jira Account (from DB): {result.db_jira_account or 'N/A'}")
                report.append(f"  Who Added FI: {result.who_added_fi}")
                report.append("  FI Validations:")

                for validation in result.fi_validations:
                    if not validation.matches:
                        report.append(f"    {validation.fi_id}: X MISMATCH")
                        report.append(f"      Current Jira Assignee: {validation.jira_assignee or 'N/A'}")
                        report.append(f"      Should be assigned to: {validation.expected_jira_id or 'N/A'}")
                        if validation.error:
                            report.append(f"      Error: {validation.error}")
                    else:
                        report.append(f"    {validation.fi_id}: + OK (assigned to {validation.jira_assignee})")
                report.append("")

        report.append("=" * 120)
        return "\n".join(report)

    def generate_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Generate summary statistics

        Args:
            results: List of ValidationResult objects

        Returns:
            Dictionary with summary statistics
        """
        total_records = len(results)
        total_fis = sum(len(r.fi_validations) for r in results)

        matched_records = sum(1 for r in results if r.status == "matched")
        mismatched_records = sum(1 for r in results if r.status == "mismatched")
        unknown_user_records = sum(1 for r in results if r.status == "unknown_user")

        total_mismatches = sum(r.mismatch_count for r in results)

        return {
            'total_records': total_records,
            'total_fis': total_fis,
            'matched_records': matched_records,
            'mismatched_records': mismatched_records,
            'unknown_user_records': unknown_user_records,
            'total_fi_mismatches': total_mismatches,
            'match_rate': (matched_records / total_records * 100) if total_records > 0 else 0
        }
