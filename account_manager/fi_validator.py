"""
FI Validator - Validate FI assignees and severity against Jira and account database
"""

import csv
import io
import json
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from .esql_integration import FIRecord
from .models import AccountManager, is_valid_etrack_user_id
from .account_populator import AccountPopulator, AccountData, AutoPopulateStrategy, format_account_data


def _fi_sort_key(fi_id: str) -> int:
    """Extract numeric part from FI-<digits> for proper numeric sorting."""
    match = re.search(r'FI-(\d+)', fi_id)
    return int(match.group(1)) if match else 0


def _sort_fi_ids(fi_ids) -> list:
    """Sort FI IDs numerically by their numeric part."""
    return sorted(fi_ids, key=_fi_sort_key)


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


@dataclass
class SeverityFIInfo:
    """Severity-relevant FI information for an etrack incident."""
    fi_id: str
    case_priority: Optional[str]
    mapped_severity: Optional[str]
    error: Optional[str] = None


@dataclass
class SeverityValidationResult:
    """Result of comparing etrack severity to linked FI case priority."""
    incident_no: str
    etrack_user_id: str
    who_added_fi: str
    etrack_severity: Optional[str]
    expected_severity: Optional[str]
    dominant_case_priority: Optional[str]
    severity_fis: List[SeverityFIInfo]
    status: str
    unique_case_priorities: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_priority_conflict(self) -> bool:
        return len(self.unique_case_priorities) > 1

    @property
    def matching_fi_count(self) -> int:
        return sum(1 for fi in self.severity_fis if fi.case_priority and not fi.error)


class FIValidator:
    """Validate FI assignees against database"""

    CASE_PRIORITY_TO_SEVERITY = {
        'P1': '1',
        'P2': '2',
        'P3': '3',
        'P4': '4',
    }
    SEVERITY_TO_CASE_PRIORITY = {value: key for key, value in CASE_PRIORITY_TO_SEVERITY.items()}
    CASE_PRIORITY_FIELD_NAME = 'Case Priority'

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

    @classmethod
    def normalize_case_priority(cls, case_priority: Optional[str]) -> Optional[str]:
        """Normalize Jira Case Priority values like P1-P4."""
        if not case_priority:
            return None
        normalized = str(case_priority).strip().upper()
        return normalized if normalized in cls.CASE_PRIORITY_TO_SEVERITY else None

    @classmethod
    def normalize_severity(cls, severity: Optional[str]) -> Optional[str]:
        """Normalize etrack severity values like 1-4."""
        if severity is None:
            return None
        normalized = str(severity).strip()
        return normalized if normalized in cls.SEVERITY_TO_CASE_PRIORITY else None

    def validate_severity_records(self, records: List[FIRecord], etrack_client) -> List[SeverityValidationResult]:
        """
        Validate etrack severity against linked FI Case Priority values.

        Mapping:
            P1 -> 1
            P2 -> 2
            P3 -> 3
            P4 -> 4

        When multiple linked FIs have different priorities, the highest priority wins.
        Example: P1 + P3 => expected severity 1.
        """
        if not records:
            return []

        all_fi_ids = sorted({fi_id for record in records for fi_id in record.fi_ids}, key=_fi_sort_key)

        fi_case_priorities = {}
        if self.jira_client and all_fi_ids:
            print(
                f"Fetching {len(all_fi_ids)} Jira '{self.CASE_PRIORITY_FIELD_NAME}' values "
                f"for severity validation (batched)..."
            )
            raw_priorities = self.jira_client.get_named_field_batch(all_fi_ids, self.CASE_PRIORITY_FIELD_NAME)
            fi_case_priorities = {
                fi_id: self.normalize_case_priority(self.jira_client.extract_field_display_value(value))
                if self.jira_client else None
                for fi_id, value in raw_priorities.items()
            }
            print(f"+ Fetched {len(raw_priorities)} Case Priority values")

        unique_incident_nos = sorted({record.incident_no for record in records}, key=int)
        print(
            f"Fetching etrack severity details for {len(unique_incident_nos)} unique incidents "
            f"(batched)..."
        )
        if hasattr(etrack_client, 'get_etrack_info_batch'):
            etrack_info_map = etrack_client.get_etrack_info_batch(unique_incident_nos)
        else:
            etrack_info_map = {}
            for incident_no in unique_incident_nos:
                etrack_info_map[incident_no] = etrack_client.get_etrack_info(incident_no) if etrack_client else None
        fetched_count = sum(1 for info in etrack_info_map.values() if info is not None)
        print(f"+ Fetched etrack details for {fetched_count}/{len(unique_incident_nos)} incidents")

        results = []
        total_records = len(records)
        for index, record in enumerate(records, 1):
            if index % 50 == 0 or index == total_records:
                print(f"\rValidating severity: {index}/{total_records} records...", end='', flush=True)
            results.append(self._validate_severity_record(record, fi_case_priorities, etrack_info_map.get(record.incident_no)))
        print()
        return results

    def _validate_severity_record(self, record: FIRecord, fi_case_priorities: Dict[str, Optional[str]], etrack_info: Optional[Any]) -> SeverityValidationResult:
        """Validate etrack severity for a single incident using cached Jira field values."""
        etrack_severity = self.normalize_severity(etrack_info.severity if etrack_info else None)

        severity_fis = []
        normalized_priorities = []
        for fi_id in _sort_fi_ids(record.fi_ids):
            case_priority = fi_case_priorities.get(fi_id)
            mapped_severity = self.CASE_PRIORITY_TO_SEVERITY.get(case_priority)
            error = None if case_priority else f"Missing or unsupported {self.CASE_PRIORITY_FIELD_NAME}"
            severity_fis.append(
                SeverityFIInfo(
                    fi_id=fi_id,
                    case_priority=case_priority,
                    mapped_severity=mapped_severity,
                    error=error,
                )
            )
            if case_priority:
                normalized_priorities.append(case_priority)

        unique_case_priorities = sorted(set(normalized_priorities), key=lambda value: self.CASE_PRIORITY_TO_SEVERITY[value])

        if not etrack_info:
            return SeverityValidationResult(
                incident_no=record.incident_no,
                etrack_user_id=record.etrack_user_id,
                who_added_fi=record.who_added_fi,
                etrack_severity=None,
                expected_severity=None,
                dominant_case_priority=None,
                severity_fis=severity_fis,
                status='error',
                unique_case_priorities=unique_case_priorities,
                error='Unable to fetch etrack incident details',
            )

        if not severity_fis:
            status = 'no_fi'
            expected_severity = None
            dominant_case_priority = None
        elif not normalized_priorities:
            status = 'missing_case_priority'
            expected_severity = None
            dominant_case_priority = None
        else:
            dominant_case_priority = min(unique_case_priorities, key=lambda value: int(self.CASE_PRIORITY_TO_SEVERITY[value]))
            expected_severity = self.CASE_PRIORITY_TO_SEVERITY[dominant_case_priority]
            if not etrack_severity:
                status = 'missing_etrack_severity'
            elif etrack_severity == expected_severity:
                status = 'matched' if len(unique_case_priorities) == 1 else 'matched_conflict'
            else:
                status = 'mismatched' if len(unique_case_priorities) == 1 else 'mismatched_conflict'

        return SeverityValidationResult(
            incident_no=record.incident_no,
            etrack_user_id=record.etrack_user_id,
            who_added_fi=record.who_added_fi,
            etrack_severity=etrack_severity,
            expected_severity=expected_severity,
            dominant_case_priority=dominant_case_priority,
            severity_fis=severity_fis,
            status=status,
            unique_case_priorities=unique_case_priorities,
        )

    def get_severity_mismatches(self, results: List[SeverityValidationResult]) -> List[SeverityValidationResult]:
        """Return severity results that need attention or can be fixed."""
        actionable_statuses = {
            'mismatched',
            'mismatched_conflict',
            'missing_case_priority',
            'missing_etrack_severity',
            'error',
        }
        return [result for result in results if result.status in actionable_statuses]

    def generate_severity_report(self, results: List[SeverityValidationResult],
                                   fmt: str = 'text', include_details: bool = True,
                                   exclude_items: set = None) -> str:
        """Generate a severity validation report.

        Args:
            results: Severity validation results.
            fmt: Output format — 'text' (default), 'table', 'csv', or 'json'.
            include_details: For 'text' format only: include per-incident detail blocks.
                             Ignored for 'table', 'csv', and 'json' formats.
            exclude_items: Set of status items to exclude from report. Valid values:
                          'matched', 'mismatched', 'conflict', 'missing_case_priority',
                          'missing_etrack_severity', 'error'. Default: None (no exclusions).
        """
        if exclude_items is None:
            exclude_items = set()

        # Filter results based on exclude_items
        filtered_results = self._filter_severity_results(results, exclude_items)

        if fmt == 'csv':
            return self._severity_report_csv(filtered_results)
        elif fmt == 'json':
            return self._severity_report_json(filtered_results)
        elif fmt == 'table':
            return self._severity_report_table(filtered_results)
        else:
            return self._severity_report_text(filtered_results, include_details=include_details)

    # ------------------------------------------------------------------ #
    # Private format helpers                                               #
    # ------------------------------------------------------------------ #

    def _filter_severity_results(self, results, exclude_items):
        """Filter severity results based on excluded status items.

        Args:
            results: List of SeverityValidationResult objects.
            exclude_items: Set of status items to exclude (e.g., {'matched', 'conflict'}).

        Returns:
            Filtered list of results.
        """
        if not exclude_items:
            return results

        filtered = []
        for r in results:
            # Check which category this result belongs to
            is_matched = r.status in ('matched', 'matched_conflict')
            is_mismatched = r.status in ('mismatched', 'mismatched_conflict')
            is_conflict = r.has_priority_conflict
            is_missing_cp = r.status == 'missing_case_priority'
            is_missing_sev = r.status == 'missing_etrack_severity'
            is_error = r.status == 'error'

            # Skip if any matching category is excluded
            if (is_matched and 'matched' in exclude_items):
                continue
            if (is_mismatched and 'mismatched' in exclude_items):
                continue
            if (is_conflict and 'conflict' in exclude_items):
                continue
            if (is_missing_cp and 'missing_case_priority' in exclude_items):
                continue
            if (is_missing_sev and 'missing_etrack_severity' in exclude_items):
                continue
            if (is_error and 'error' in exclude_items):
                continue

            filtered.append(r)

        return filtered

    def _severity_counts(self, results):
        """Return (matched, mismatched, conflicts, missing_cp, missing_sev, errors) lists."""
        matched = [r for r in results if r.status in ('matched', 'matched_conflict')]
        mismatched = [r for r in results if r.status in ('mismatched', 'mismatched_conflict')]
        conflicts = [r for r in results if r.has_priority_conflict]
        missing_cp = [r for r in results if r.status == 'missing_case_priority']
        missing_sev = [r for r in results if r.status == 'missing_etrack_severity']
        errors = [r for r in results if r.status == 'error']
        return matched, mismatched, conflicts, missing_cp, missing_sev, errors

    def _severity_report_text(self, results: List[SeverityValidationResult],
                               include_details: bool = True) -> str:
        """Full human-readable text report (original behaviour)."""
        report = []
        report.append("=" * 120)
        report.append("FI CASE PRIORITY VS ETRACK SEVERITY REPORT")
        report.append("=" * 120)
        report.append("Mapping: P1 -> 1, P2 -> 2, P3 -> 3, P4 -> 4")
        report.append("Conflict Rule: If one incident links to multiple FIs with different Case Priority values, the highest priority wins.")
        report.append("Example: P1 + P3 => target etrack severity 1")
        report.append(f"Total Records Validated: {len(results)}")

        matched, mismatched, conflicts, missing_case_priority, missing_etrack_severity, errors = \
            self._severity_counts(results)

        report.append(f"Matched Records: {len(matched)}")
        report.append(f"Mismatched Records: {len(mismatched)}")
        report.append(f"Conflict Records: {len(conflicts)}")
        report.append(f"Missing Case Priority: {len(missing_case_priority)}")
        report.append(f"Missing Etrack Severity: {len(missing_etrack_severity)}")
        report.append(f"Errors: {len(errors)}")
        report.append("")

        if not any([mismatched, missing_case_priority, missing_etrack_severity, errors]):
            report.append("+ All etrack severities match the linked FI Case Priority values!")
            report.append("=" * 120)
            return "\n".join(report)

        report.append("=" * 120)
        report.append("SUMMARY TABLE")
        report.append("=" * 120)
        header = (
            f"{'Incident':<12} | {'Etrack Sev':<10} | {'Target Sev':<10} | {'Target CP':<10} | "
            f"{'FI Priorities':<32} | {'Status':<20}"
        )
        report.append(header)
        report.append("-" * 120)

        for result in sorted(results, key=lambda item: int(item.incident_no)):
            fi_priorities = []
            for fi_info in result.severity_fis:
                if fi_info.case_priority:
                    fi_priorities.append(f"{fi_info.fi_id}:{fi_info.case_priority}")
                else:
                    fi_priorities.append(f"{fi_info.fi_id}:N/A")
            priority_text = ', '.join(fi_priorities)
            if len(priority_text) > 30:
                priority_text = priority_text[:27] + '...'
            row = (
                f"{result.incident_no:<12} | {(result.etrack_severity or 'N/A'):<10} | {(result.expected_severity or 'N/A'):<10} | "
                f"{(result.dominant_case_priority or 'N/A'):<10} | {priority_text:<32} | {result.status.upper():<20}"
            )
            report.append(row)

        report.append("-" * 120)

        if include_details:
            report.append("")
            report.append("=" * 120)
            report.append("DETAILS")
            report.append("=" * 120)
            for result in sorted(results, key=lambda item: int(item.incident_no)):
                if result.status == 'matched' and not result.has_priority_conflict:
                    continue
                fi_ids = ', '.join(_sort_fi_ids([fi_info.fi_id for fi_info in result.severity_fis])) or 'N/A'
                report.append(f"Incident: {result.incident_no} | FIs: {fi_ids}")
                report.append(f"  Etrack Assignee: {result.etrack_user_id}")
                report.append(f"  Etrack Severity: {result.etrack_severity or 'N/A'}")
                report.append(f"  Target Severity: {result.expected_severity or 'N/A'}")
                report.append(f"  Dominant Case Priority: {result.dominant_case_priority or 'N/A'}")
                report.append(f"  Status: {result.status}")
                if result.has_priority_conflict:
                    report.append(
                        "  Conflict Resolution: Multiple Case Priority values found; highest priority selected -> "
                        f"{result.dominant_case_priority} / severity {result.expected_severity}"
                    )
                if result.error:
                    report.append(f"  Error: {result.error}")
                report.append("  FI Case Priority Values:")
                for fi_info in result.severity_fis:
                    detail = (
                        f"    {fi_info.fi_id}: {fi_info.case_priority or 'N/A'}"
                        f" -> severity {fi_info.mapped_severity or 'N/A'}"
                    )
                    report.append(detail)
                    if fi_info.error:
                        report.append(f"      Error: {fi_info.error}")
                report.append("")
        else:
            report.append("")
            report.append("COMPACT INSIGHTS (--skip-details)")
            report.append("-" * 120)
            if mismatched:
                target_counts = {}
                for result in mismatched:
                    target = result.expected_severity or 'N/A'
                    target_counts[target] = target_counts.get(target, 0) + 1
                for target, count in sorted(target_counts.items(), key=lambda item: (item[0], -item[1])):
                    report.append(f"  Target severity {target}: {count}")
            if conflicts:
                report.append(f"  Conflict records requiring highest-priority resolution: {len(conflicts)}")
            report.append("Run without --skip-details for per-incident detail.")

        report.append("=" * 120)
        return "\n".join(report)

    def _severity_report_table(self, results: List[SeverityValidationResult]) -> str:
        """Aligned table of all records — no narrative header or detail blocks."""
        matched, mismatched, conflicts, missing_cp, missing_sev, errors = self._severity_counts(results)
        header_line = (
            f"{'Incident':<12} | {'Assignee':<22} | {'Etrack Sev':<10} | {'Target Sev':<10} | "
            f"{'Target CP':<10} | {'Conflict':<8} | {'FI Priorities':<36} | {'Status':<24}"
        )
        sep = "-" * len(header_line)
        rows = [header_line, sep]
        for result in sorted(results, key=lambda r: int(r.incident_no)):
            fi_priorities = [
                f"{fi.fi_id}:{fi.case_priority or 'N/A'}" for fi in result.severity_fis
            ]
            priority_text = ', '.join(fi_priorities)
            if len(priority_text) > 34:
                priority_text = priority_text[:31] + '...'
            row = (
                f"{result.incident_no:<12} | {result.etrack_user_id:<22} | "
                f"{(result.etrack_severity or 'N/A'):<10} | {(result.expected_severity or 'N/A'):<10} | "
                f"{(result.dominant_case_priority or 'N/A'):<10} | {'YES' if result.has_priority_conflict else 'no':<8} | "
                f"{priority_text:<36} | {result.status.upper():<24}"
            )
            rows.append(row)
        rows.append(sep)
        rows.append(
            f"Total: {len(results)}  Matched: {len(matched)}  Mismatched: {len(mismatched)}  "
            f"Conflicts: {len(conflicts)}  Missing CP: {len(missing_cp)}  "
            f"Missing Sev: {len(missing_sev)}  Errors: {len(errors)}"
        )
        return "\n".join(rows)

    def _severity_report_csv(self, results: List[SeverityValidationResult]) -> str:
        """CSV format — one row per incident."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            'incident_no', 'etrack_assignee', 'etrack_severity', 'expected_severity',
            'dominant_case_priority', 'status', 'has_priority_conflict',
            'fi_ids', 'fi_case_priorities'
        ])
        for result in sorted(results, key=lambda r: int(r.incident_no)):
            fi_ids = ';'.join(_sort_fi_ids([fi.fi_id for fi in result.severity_fis]))
            fi_priorities = ';'.join(
                f"{fi.fi_id}:{fi.case_priority or ''}" for fi in result.severity_fis
            )
            writer.writerow([
                result.incident_no,
                result.etrack_user_id,
                result.etrack_severity or '',
                result.expected_severity or '',
                result.dominant_case_priority or '',
                result.status,
                str(result.has_priority_conflict).lower(),
                fi_ids,
                fi_priorities,
            ])
        return buf.getvalue()

    def _severity_report_json(self, results: List[SeverityValidationResult]) -> str:
        """JSON format — summary object plus array of per-incident records."""
        matched, mismatched, conflicts, missing_cp, missing_sev, errors = self._severity_counts(results)
        records = []
        for result in sorted(results, key=lambda r: int(r.incident_no)):
            records.append({
                'incident_no': result.incident_no,
                'etrack_assignee': result.etrack_user_id,
                'etrack_severity': result.etrack_severity,
                'expected_severity': result.expected_severity,
                'dominant_case_priority': result.dominant_case_priority,
                'status': result.status,
                'has_priority_conflict': result.has_priority_conflict,
                'error': result.error,
                'fi_details': [
                    {
                        'fi_id': fi.fi_id,
                        'case_priority': fi.case_priority,
                        'mapped_severity': fi.mapped_severity,
                        'error': fi.error,
                    }
                    for fi in result.severity_fis
                ],
            })
        output = {
            'summary': {
                'total': len(results),
                'matched': len(matched),
                'mismatched': len(mismatched),
                'conflicts': len(conflicts),
                'missing_case_priority': len(missing_cp),
                'missing_etrack_severity': len(missing_sev),
                'errors': len(errors),
            },
            'records': records,
        }
        return json.dumps(output, indent=2)

    def generate_report(self, results: List[ValidationResult], include_details: bool = True) -> str:
        """
        Generate a validation report with both table and detailed formats

        Args:
            results: List of ValidationResult objects
            include_details: If False, omit per-incident detailed sections

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
                fi_ids = ', '.join(_sort_fi_ids([v.fi_id for v in result.fi_validations])) or 'N/A'
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
        if include_details and unknown_users:
            report.append("=" * 120)
            report.append("UNKNOWN USERS (not in database) - DETAILS")
            report.append("-" * 120)
            for result in unknown_users:
                fi_ids = ', '.join(_sort_fi_ids([v.fi_id for v in result.fi_validations])) or 'N/A'
                report.append(f"  Incident: {result.incident_no} | Etrack Assignee: {result.etrack_user_id} | FIs: {fi_ids}")
                report.append(f"    -> Add user: python3 -m account_manager.cli add {result.etrack_user_id}")
            report.append("")

        if include_details and mismatches:
            report.append("=" * 120)
            report.append("MISMATCHES - DETAILS")
            report.append("-" * 120)
            report.append("(FI assignee in Jira does not match etrack assignee's jira_account in DB)")
            report.append("")

            for result in mismatches:
                fi_ids = ', '.join(_sort_fi_ids([v.fi_id for v in result.fi_validations]))
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

        if not include_details and (mismatches or unknown_users):
            mismatch_fi_ids = set()
            mismatch_by_expected = {}
            mismatch_by_current = {}

            for result in mismatches:
                for v in result.fi_validations:
                    if not v.matches:
                        mismatch_fi_ids.add(v.fi_id)
                        expected = v.expected_jira_id or 'N/A'
                        current = v.jira_assignee or 'N/A'
                        mismatch_by_expected[expected] = mismatch_by_expected.get(expected, 0) + 1
                        mismatch_by_current[current] = mismatch_by_current.get(current, 0) + 1

            report.append("COMPACT INSIGHTS (--skip-details)")
            report.append("-" * 120)
            report.append(f"Unique mismatched FIs: {len(mismatch_fi_ids)}")

            if mismatch_by_expected:
                report.append("Top expected assignees (target):")
                for assignee, count in sorted(mismatch_by_expected.items(), key=lambda x: (-x[1], x[0]))[:5]:
                    report.append(f"  {assignee}: {count}")

            if mismatch_by_current:
                report.append("Top current assignees (source):")
                for assignee, count in sorted(mismatch_by_current.items(), key=lambda x: (-x[1], x[0]))[:5]:
                    report.append(f"  {assignee}: {count}")

            report.append("Run without --skip-details for per-incident/per-FI details.")

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
