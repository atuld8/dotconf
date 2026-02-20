"""
Report generation functionality for account data
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from .models import AccountManager


class ReportGenerator:
    """Generates various reports from account data"""

    def __init__(self, account_manager: 'AccountManager'):
        """
        Initialize report generator

        Args:
            account_manager: AccountManager instance
        """
        self.am = account_manager

    def generate_report(self, report_type: str = 'full', show_notes: bool = False) -> str:
        """
        Generate various reports

        Args:
            report_type: Type of report ('full', 'summary', 'missing-fields', 'table')
            show_notes: If True, include notes in the report output

        Returns:
            Formatted report string
        """
        if report_type == 'full':
            return self._generate_full_report(show_notes=show_notes)
        elif report_type == 'summary':
            return self._generate_summary_report()
        elif report_type in ('missing-fields', 'missing_fields'):
            return self._generate_missing_fields_report(show_notes=show_notes)
        elif report_type == 'table':
            return self._generate_table_report(show_notes=show_notes)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

    def _generate_full_report(self, show_notes: bool = False) -> str:
        """Generate a full report of all accounts

        Args:
            show_notes: If True, always show notes field (even if empty)
        """
        accounts = self.am.get_all_accounts()

        report = []
        report.append("=" * 100)
        report.append("FULL ACCOUNT REPORT")
        report.append("=" * 100)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Accounts: {len(accounts)}")
        report.append("=" * 100)
        report.append("")

        for account in accounts:
            report.append(f"ID: {account['id']}")
            report.append(f"  Etrack User ID:    {account['etrack_user_id']}")
            report.append(f"  First Name:        {account.get('first_name') or 'N/A'}")
            report.append(f"  Last Name:         {account.get('last_name') or 'N/A'}")
            report.append(f"  Veritas Email:     {account['veritas_email'] or 'N/A'}")
            report.append(f"  Cohesity Email:    {account['cohesity_email'] or 'N/A'}")
            report.append(f"  Community Account: {account['community_account'] or 'N/A'}")
            report.append(f"  Jira Account:      {account['jira_account'] or 'N/A'}")
            report.append(f"  Manual Verified:   {account.get('manual_verified', 'no')}")
            if show_notes:
                notes = account.get('notes') or 'N/A'
                # Handle multi-line notes with proper indentation
                if '\n' in str(notes):
                    lines = str(notes).split('\n')
                    report.append(f"  Notes:             {lines[0]}")
                    for line in lines[1:]:
                        report.append(f"                     {line}")
                else:
                    report.append(f"  Notes:             {notes}")
            elif account.get('notes'):
                # Only show notes if present (backward compatible behavior)
                notes = account['notes']
                if '\n' in str(notes):
                    lines = str(notes).split('\n')
                    report.append(f"  Notes:             {lines[0]}")
                    for line in lines[1:]:
                        report.append(f"                     {line}")
                else:
                    report.append(f"  Notes:             {notes}")
            report.append(f"  Created:           {account['created_at']}")
            report.append(f"  Updated:           {account['updated_at']}")
            report.append("-" * 100)

        return "\n".join(report)

    def _generate_summary_report(self) -> str:
        """Generate a summary statistics report"""
        self.am.cursor.execute("SELECT COUNT(*) FROM accounts")
        total = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE first_name IS NOT NULL")
        with_first_name = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE last_name IS NOT NULL")
        with_last_name = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE first_name IS NOT NULL AND last_name IS NOT NULL")
        with_both_names = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE veritas_email IS NOT NULL")
        with_veritas = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE cohesity_email IS NOT NULL")
        with_cohesity = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE community_account IS NOT NULL")
        with_community = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE jira_account IS NOT NULL")
        with_jira = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE manual_verified = 'yes'")
        manually_verified = self.am.cursor.fetchone()[0]

        self.am.cursor.execute("SELECT COUNT(*) FROM accounts WHERE notes IS NOT NULL AND notes != ''")
        with_notes = self.am.cursor.fetchone()[0]

        report = []
        report.append("=" * 60)
        report.append("ACCOUNT SUMMARY REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        report.append(f"Total Accounts:             {total}")

        if total > 0:
            report.append(f"With First Name:            {with_first_name} ({with_first_name/total*100:.1f}%)")
            report.append(f"With Last Name:             {with_last_name} ({with_last_name/total*100:.1f}%)")
            report.append(f"With Both Names:            {with_both_names} ({with_both_names/total*100:.1f}%)")
            report.append(f"With Veritas Email:         {with_veritas} ({with_veritas/total*100:.1f}%)")
            report.append(f"With Cohesity Email:        {with_cohesity} ({with_cohesity/total*100:.1f}%)")
            report.append(f"With Community Account:     {with_community} ({with_community/total*100:.1f}%)")
            report.append(f"With Jira Account:          {with_jira} ({with_jira/total*100:.1f}%)")
            report.append(f"Manually Verified:          {manually_verified} ({manually_verified/total*100:.1f}%)")
            report.append(f"With Notes:                 {with_notes} ({with_notes/total*100:.1f}%)")
        else:
            report.append("With First Name:            0 (0.0%)")
            report.append("With Last Name:             0 (0.0%)")
            report.append("With Both Names:            0 (0.0%)")
            report.append("With Veritas Email:         0 (0.0%)")
            report.append("With Cohesity Email:        0 (0.0%)")
            report.append("With Community Account:     0 (0.0%)")
            report.append("With Jira Account:          0 (0.0%)")
            report.append("Manually Verified:          0 (0.0%)")
            report.append("With Notes:                 0 (0.0%)")

        report.append("=" * 60)

        return "\n".join(report)

    def _generate_missing_fields_report(self, show_notes: bool = False) -> str:
        """Generate report of accounts with missing fields

        Args:
            show_notes: If True, show notes for each account
        """
        self.am.cursor.execute("""
            SELECT * FROM accounts
            WHERE first_name IS NULL
               OR last_name IS NULL
               OR veritas_email IS NULL
               OR cohesity_email IS NULL
               OR community_account IS NULL
               OR jira_account IS NULL
            ORDER BY etrack_user_id
        """)

        accounts = [dict(row) for row in self.am.cursor.fetchall()]

        report = []
        report.append("=" * 80)
        report.append("ACCOUNTS WITH MISSING FIELDS")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Accounts with missing data: {len(accounts)}")
        report.append("=" * 80)
        report.append("")

        for account in accounts:
            missing = []
            if not account.get('first_name'):
                missing.append('First Name')
            if not account.get('last_name'):
                missing.append('Last Name')
            if not account['veritas_email']:
                missing.append('Veritas Email')
            if not account['cohesity_email']:
                missing.append('Cohesity Email')
            if not account['community_account']:
                missing.append('Community Account')
            if not account['jira_account']:
                missing.append('Jira Account')

            report.append(f"Etrack User ID: {account['etrack_user_id']}")
            report.append(f"  Missing: {', '.join(missing)}")
            if show_notes and account.get('notes'):
                report.append(f"  Notes: {account['notes']}")
            report.append("")

        return "\n".join(report)

    def _generate_table_report(self, show_notes: bool = False) -> str:
        """Generate a tabular report of all accounts

        Args:
            show_notes: If True, include a Notes column (truncated to 30 chars)
        """
        accounts = self.am.get_all_accounts()

        if not accounts:
            return "No accounts found"

        report = []
        report.append("")
        report.append("ACCOUNT TABLE REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Accounts: {len(accounts)}")
        report.append("")

        # Define column widths (must fit header text)
        col_etrack = 20      # "Etrack User ID" = 14 chars + padding
        col_first = 18       # "First Name" = 10 chars + space for data
        col_last = 18        # "Last Name" = 9 chars + space for data
        col_veritas = 36     # "Veritas Email" = 13 chars + space for data
        col_cohesity = 36    # "Cohesity Email" = 14 chars + space for data
        col_community = 24   # "Community" = 9 chars + space for data
        col_jira = 24        # "Jira Account" = 12 chars + space for data
        col_verified = 10    # "Verified" = 8 chars + space
        col_notes = 35       # "Notes" = 5 chars + space for data

        # Header
        separator = "+" + "-" * (col_etrack + 2) + "+" + "-" * (col_first + 2) + "+" + \
                   "-" * (col_last + 2) + "+" + "-" * (col_veritas + 2) + "+" + \
                   "-" * (col_cohesity + 2) + "+" + "-" * (col_community + 2) + "+" + \
                   "-" * (col_jira + 2) + "+" + "-" * (col_verified + 2) + "+"

        header = f"| {'Etrack User ID':<{col_etrack}} | {'First Name':<{col_first}} | " \
                f"{'Last Name':<{col_last}} | {'Veritas Email':<{col_veritas}} | " \
                f"{'Cohesity Email':<{col_cohesity}} | {'Community':<{col_community}} | " \
                f"{'Jira Account':<{col_jira}} | {'Verified':<{col_verified}} |"

        if show_notes:
            separator += "-" * (col_notes + 2) + "+"
            header = header + f" {'Notes':<{col_notes}} |"

        report.append(separator)
        report.append(header)
        report.append(separator)

        # Data rows
        for account in accounts:
            etrack = (account['etrack_user_id'] or '')[:col_etrack]
            first = (account.get('first_name') or 'N/A')[:col_first]
            last = (account.get('last_name') or 'N/A')[:col_last]
            veritas = (account['veritas_email'] or 'N/A')[:col_veritas]
            cohesity = (account['cohesity_email'] or 'N/A')[:col_cohesity]
            community = (account['community_account'] or 'N/A')[:col_community]
            jira = (account['jira_account'] or 'N/A')[:col_jira]
            verified = (account.get('manual_verified', 'no'))[:col_verified]

            row = f"| {etrack:<{col_etrack}} | {first:<{col_first}} | {last:<{col_last}} | " \
                  f"{veritas:<{col_veritas}} | {cohesity:<{col_cohesity}} | " \
                  f"{community:<{col_community}} | {jira:<{col_jira}} | {verified:<{col_verified}} |"

            if show_notes:
                # Truncate notes and replace newlines with spaces for table format
                notes = (account.get('notes') or 'N/A').replace('\n', ' ')[:col_notes]
                row = row + f" {notes:<{col_notes}} |"

            report.append(row)

        report.append(separator)
        report.append("")

        return "\n".join(report)

    def generate_compact_table(self, show_notes: bool = False) -> str:
        """Generate a compact tabular view (shorter columns)

        Args:
            show_notes: If True, include a Notes column (truncated to 25 chars)
        """
        accounts = self.am.get_all_accounts()

        if not accounts:
            return "No accounts found"

        report = []
        report.append("")
        report.append("COMPACT ACCOUNT TABLE")
        report.append("")

        # Compact column widths (headers: "Etrack", "First", "Last", "Jira", "Cohesity Email", "Community")
        col_etrack = 20      # "Etrack" = 6 chars + space for data
        col_first = 15       # "First" = 5 chars + space for data
        col_last = 15        # "Last" = 4 chars + space for data
        col_jira = 24        # "Jira" = 4 chars + space for data
        col_cohesity = 36    # "Cohesity Email" = 14 chars + space for data
        col_community = 24   # "Community" = 9 chars + space for data
        col_notes = 30       # "Notes" = 5 chars + space for data

        # Header
        separator = "+" + "-" * (col_etrack + 2) + "+" + "-" * (col_first + 2) + "+" + \
                   "-" * (col_last + 2) + "+" + "-" * (col_jira + 2) + "+" + \
                   "-" * (col_cohesity + 2) + "+" + "-" * (col_community + 2) + "+"

        header = f"| {'Etrack':<{col_etrack}} | {'First':<{col_first}} | {'Last':<{col_last}} | " \
                f"{'Jira':<{col_jira}} | {'Cohesity Email':<{col_cohesity}} | " \
                f"{'Community':<{col_community}} |"

        if show_notes:
            separator += "-" * (col_notes + 2) + "+"
            header = header + f" {'Notes':<{col_notes}} |"

        report.append(separator)
        report.append(header)
        report.append(separator)

        # Data rows
        for account in accounts:
            etrack = (account['etrack_user_id'] or '')[:col_etrack]
            first = (account.get('first_name') or 'N/A')[:col_first]
            last = (account.get('last_name') or 'N/A')[:col_last]
            jira = (account['jira_account'] or 'N/A')[:col_jira]
            cohesity = (account['cohesity_email'] or 'N/A')[:col_cohesity]
            community = (account['community_account'] or 'N/A')[:col_community]

            row = f"| {etrack:<{col_etrack}} | {first:<{col_first}} | {last:<{col_last}} | " \
                  f"{jira:<{col_jira}} | {cohesity:<{col_cohesity}} | " \
                  f"{community:<{col_community}} |"

            if show_notes:
                # Truncate notes and replace newlines with spaces for table format
                notes = (account.get('notes') or 'N/A').replace('\n', ' ')[:col_notes]
                row = row + f" {notes:<{col_notes}} |"

            report.append(row)

        report.append(separator)
        report.append(f"\nTotal: {len(accounts)} accounts")

        return "\n".join(report)

    def generate_markdown_table(self, show_notes: bool = False) -> str:
        """Generate a markdown-formatted table

        Args:
            show_notes: If True, include a Notes column
        """
        accounts = self.am.get_all_accounts()

        if not accounts:
            return "No accounts found"

        report = []
        report.append("")
        report.append("# Account Report")
        report.append("")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total: {len(accounts)} accounts")
        report.append("")

        # Markdown table header
        if show_notes:
            report.append("| Etrack User ID | First Name | Last Name | Veritas Email | Cohesity Email | Community Account | Jira Account | Verified | Notes |")
            report.append("|----------------|------------|-----------|---------------|----------------|-------------------|--------------|----------|-------|")
        else:
            report.append("| Etrack User ID | First Name | Last Name | Veritas Email | Cohesity Email | Community Account | Jira Account | Verified |")
            report.append("|----------------|------------|-----------|---------------|----------------|-------------------|--------------|----------|")

        # Data rows
        for account in accounts:
            etrack = account['etrack_user_id'] or ''
            first = account.get('first_name') or 'N/A'
            last = account.get('last_name') or 'N/A'
            veritas = account['veritas_email'] or 'N/A'
            cohesity = account['cohesity_email'] or 'N/A'
            community = account['community_account'] or 'N/A'
            jira = account['jira_account'] or 'N/A'
            verified = account.get('manual_verified', 'no')

            if show_notes:
                # Replace newlines and pipe chars in notes for markdown compatibility
                notes = (account.get('notes') or 'N/A').replace('\n', ' ').replace('|', '\\|')
                row = f"| {etrack} | {first} | {last} | {veritas} | {cohesity} | {community} | {jira} | {verified} | {notes} |"
            else:
                row = f"| {etrack} | {first} | {last} | {veritas} | {cohesity} | {community} | {jira} | {verified} |"
            report.append(row)

        report.append("")

        return "\n".join(report)

    def generate_action_log_report(self, limit: int = 50, action_type: str = None,
                                    target_type: str = None, status: str = None,
                                    since: str = None, table_format: bool = True) -> str:
        """
        Generate a report of recent actions

        Args:
            limit: Maximum number of entries
            action_type: Filter by action type
            target_type: Filter by target type
            status: Filter by status
            since: Filter by date (YYYY-MM-DD)
            table_format: If True, use table format; else use detailed format

        Returns:
            Formatted action log report
        """
        actions = self.am.get_action_log(
            limit=limit,
            action_type=action_type,
            target_type=target_type,
            status=status,
            since=since
        )

        report = []
        report.append("=" * 120)
        report.append("ACTION LOG REPORT")
        report.append("=" * 120)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        filters = []
        if action_type:
            filters.append(f"action_type={action_type}")
        if target_type:
            filters.append(f"target_type={target_type}")
        if status:
            filters.append(f"status={status}")
        if since:
            filters.append(f"since={since}")
        if filters:
            report.append(f"Filters: {', '.join(filters)}")

        report.append(f"Showing: {len(actions)} entries (limit: {limit})")
        report.append("=" * 120)

        if not actions:
            report.append("")
            report.append("No actions found.")
            return "\n".join(report)

        # Status symbols
        status_symbols = {
            'success': '+',
            'failed': 'X',
            'skipped': '○',
            'dry_run': '◌'
        }

        if table_format:
            # Table format
            report.append("")

            # Column widths
            col_st = 3      # Status symbol
            col_ts = 19     # Timestamp
            col_act = 16    # Action type
            col_tgt = 25    # Target
            col_chg = 40    # Change
            col_det = 25    # Details

            # Header
            sep = "+" + "-"*(col_st+2) + "+" + "-"*(col_ts+2) + "+" + "-"*(col_act+2) + "+" + \
                  "-"*(col_tgt+2) + "+" + "-"*(col_chg+2) + "+" + "-"*(col_det+2) + "+"

            hdr = f"| {'St':<{col_st}} | {'Timestamp':<{col_ts}} | {'Action':<{col_act}} | " \
                  f"{'Target':<{col_tgt}} | {'Change':<{col_chg}} | {'Details':<{col_det}} |"

            report.append(sep)
            report.append(hdr)
            report.append(sep)

            for action in actions:
                symbol = status_symbols.get(action['status'], '?')
                timestamp = action['created_at'][:19] if action['created_at'] else 'N/A'
                action_name = (action['action_type'] or '')[:col_act]

                # Target
                if action['target_type'] and action['target_id']:
                    target = f"{action['target_type']}={action['target_id']}"[:col_tgt]
                else:
                    target = ''

                # Change (truncate)
                if action['old_value'] or action['new_value']:
                    old = (action['old_value'] or '-')[:15]
                    new = (action['new_value'] or '-')[:15]
                    change = f"{old} → {new}"[:col_chg]
                else:
                    change = ''

                # Details (truncate, remove newlines)
                details = (action['details'] or '').replace('\n', ' ')[:col_det]

                row = f"| {symbol:<{col_st}} | {timestamp:<{col_ts}} | {action_name:<{col_act}} | " \
                      f"{target:<{col_tgt}} | {change:<{col_chg}} | {details:<{col_det}} |"
                report.append(row)

            report.append(sep)
        else:
            # Detailed format
            report.append("")
            for action in actions:
                symbol = status_symbols.get(action['status'], '?')
                timestamp = action['created_at'][:19] if action['created_at'] else 'N/A'

                report.append(f"{symbol} [{timestamp}] {action['action_type']}")
                if action['target_type'] and action['target_id']:
                    report.append(f"    Target: {action['target_type']}={action['target_id']}")
                if action['old_value'] or action['new_value']:
                    report.append(f"    Change: {action['old_value'] or '(none)'} → {action['new_value'] or '(none)'}")
                if action['details']:
                    details_lines = action['details'].split('\n')
                    report.append(f"    Details: {details_lines[0]}")
                    for line in details_lines[1:]:
                        report.append(f"             {line}")
                report.append("")

        return "\n".join(report)

    def generate_action_summary_report(self, since: str = None) -> str:
        """
        Generate a summary of actions taken

        Args:
            since: Filter by date (YYYY-MM-DD)

        Returns:
            Formatted action summary report
        """
        summary = self.am.get_action_summary(since=since)

        report = []
        report.append("=" * 70)
        report.append("ACTION SUMMARY REPORT")
        report.append("=" * 70)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if since:
            report.append(f"Period: Since {since}")
        else:
            report.append("Period: All time")
        report.append("=" * 70)
        report.append("")

        if not summary:
            report.append("No actions recorded.")
            return "\n".join(report)

        # Calculate totals
        total_success = 0
        total_failed = 0
        total_skipped = 0
        total_dry_run = 0

        # Action type descriptions
        action_descriptions = {
            'add_account': 'Add Account',
            'update_account': 'Update Account',
            'delete_account': 'Delete Account',
            'verify_account': 'Verify Account',
            'fetch_email': 'Fetch Email',
            'fetch_jira_id': 'Fetch Jira ID',
            'assign_fi': 'Assign FI',
            'fix_fi': 'Fix FI Assignment',
            'assign_etrack': 'Assign Etrack',
            'validate_fi': 'Validate FI',
            'import_accounts': 'Import Accounts',
            'export_accounts': 'Export Accounts',
        }

        report.append(f"{'Action Type':<25} {'Success':>10} {'Failed':>10} {'Skipped':>10} {'Dry Run':>10} {'Total':>10}")
        report.append("-" * 75)

        for action_type in sorted(summary.keys()):
            stats = summary[action_type]
            success = stats.get('success', 0)
            failed = stats.get('failed', 0)
            skipped = stats.get('skipped', 0)
            dry_run = stats.get('dry_run', 0)
            total = success + failed + skipped + dry_run

            total_success += success
            total_failed += failed
            total_skipped += skipped
            total_dry_run += dry_run

            display_name = action_descriptions.get(action_type, action_type)
            report.append(f"{display_name:<25} {success:>10} {failed:>10} {skipped:>10} {dry_run:>10} {total:>10}")

        report.append("-" * 75)
        grand_total = total_success + total_failed + total_skipped + total_dry_run
        report.append(f"{'TOTAL':<25} {total_success:>10} {total_failed:>10} {total_skipped:>10} {total_dry_run:>10} {grand_total:>10}")
        report.append("=" * 75)

        # Success rate
        if grand_total > 0:
            actual_attempts = total_success + total_failed
            if actual_attempts > 0:
                success_rate = (total_success / actual_attempts) * 100
                report.append(f"\nSuccess Rate: {success_rate:.1f}% ({total_success}/{actual_attempts} actual attempts)")

        return "\n".join(report)

    def generate_daily_activity_report(self, days: int = 7) -> str:
        """
        Generate a daily activity breakdown

        Args:
            days: Number of days to include (default 7)

        Returns:
            Formatted daily activity report
        """
        report = []
        report.append("=" * 60)
        report.append("DAILY ACTIVITY REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Period: Last {days} days")
        report.append("=" * 60)
        report.append("")

        # Query for daily stats
        self.am.cursor.execute("""
            SELECT date(created_at) as day,
                   action_type,
                   status,
                   COUNT(*) as count
            FROM action_log
            WHERE date(created_at) >= date('now', ?)
            GROUP BY date(created_at), action_type, status
            ORDER BY date(created_at) DESC, action_type
        """, (f'-{days} days',))

        rows = self.am.cursor.fetchall()

        if not rows:
            report.append("No activity in this period.")
            return "\n".join(report)

        # Organize by day
        daily_data = {}
        for row in rows:
            day = row['day']
            if day not in daily_data:
                daily_data[day] = {'success': 0, 'failed': 0, 'actions': {}}
            action_type = row['action_type']
            status = row['status']
            count = row['count']

            if status == 'success':
                daily_data[day]['success'] += count
            elif status == 'failed':
                daily_data[day]['failed'] += count

            if action_type not in daily_data[day]['actions']:
                daily_data[day]['actions'][action_type] = 0
            daily_data[day]['actions'][action_type] += count

        for day in sorted(daily_data.keys(), reverse=True):
            data = daily_data[day]
            total = data['success'] + data['failed']
            report.append(f"📅 {day}")
            report.append(f"   Total: {total} actions (+ {data['success']} success, X {data['failed']} failed)")

            # Show top actions for this day
            sorted_actions = sorted(data['actions'].items(), key=lambda x: -x[1])
            for action, count in sorted_actions[:5]:
                report.append(f"     - {action}: {count}")
            report.append("")

        return "\n".join(report)

    def generate_target_history_report(self, target_type: str, target_id: str) -> str:
        """
        Generate history of actions for a specific target

        Args:
            target_type: Type of target ('account', 'fi', 'etrack')
            target_id: ID of target

        Returns:
            Formatted history report
        """
        actions = self.am.get_action_log(
            limit=100,
            target_type=target_type,
            target_id=target_id
        )

        report = []
        report.append("=" * 80)
        report.append(f"ACTION HISTORY: {target_type}={target_id}")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Actions: {len(actions)}")
        report.append("=" * 80)
        report.append("")

        if not actions:
            report.append("No actions found for this target.")
            return "\n".join(report)

        status_symbols = {
            'success': '+',
            'failed': 'X',
            'skipped': '○',
            'dry_run': '◌'
        }

        for action in actions:
            symbol = status_symbols.get(action['status'], '?')
            timestamp = action['created_at'][:19] if action['created_at'] else 'N/A'

            report.append(f"{symbol} [{timestamp}] {action['action_type']} ({action['status']})")
            if action['old_value'] or action['new_value']:
                report.append(f"    {action['old_value'] or '(none)'} → {action['new_value'] or '(none)'}")
            if action['details']:
                report.append(f"    {action['details']}")
            report.append("")

        return "\n".join(report)

    @staticmethod
    def generate_fi_reassignment_report(mismatches: List[Dict[str, Any]],
                                         group_by_current: bool = True) -> str:
        """
        Generate a report of FI reassignments needed.

        Args:
            mismatches: List of dicts with 'fi_id', 'current_assignee', 'expected_assignee'
            group_by_current: If True, group by current assignee; else by expected

        Returns:
            Formatted reassignment report
        """
        if not mismatches:
            return "No FI reassignments needed."

        report = []
        report.append("=" * 80)
        report.append("                    FI REASSIGNMENT REPORT")

        # Determine if there's a common current assignee
        current_assignees = set(m.get('current_assignee', '') for m in mismatches)
        if len(current_assignees) == 1:
            common_current = list(current_assignees)[0]
            report.append(f"                 Current Assignee: {common_current}")
        else:
            common_current = None

        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
        report.append(f"Total FIs to Reassign: {len(mismatches)}")
        report.append("=" * 80)
        report.append("")

        # Group by target assignee
        by_target = {}
        for m in mismatches:
            target = m.get('expected_assignee', 'Unknown')
            if target not in by_target:
                by_target[target] = []
            by_target[target].append(m['fi_id'])

        # Sort by count descending
        sorted_targets = sorted(by_target.items(), key=lambda x: -len(x[1]))

        report.append("BY TARGET ASSIGNEE")
        report.append("-" * 18)
        report.append(f"{'Assignee':<28} {'Count':>5}   FI IDs")
        report.append(f"{'-'*28}  {'-'*5}   {'-'*40}")

        for target, fi_ids in sorted_targets:
            fi_list = ', '.join(fi_ids[:5])
            if len(fi_ids) > 5:
                fi_list += f", ... (+{len(fi_ids) - 5} more)"
            report.append(f"{target:<28} {len(fi_ids):>5}   {fi_list}")

        report.append("")
        report.append("FULL LIST")
        report.append("-" * 9)
        report.append(f"{'FI ID':<12} {'Current Assignee':<20} {'Should Be':<28}")
        report.append(f"{'-'*12} {'-'*20} {'-'*28}")

        for m in mismatches:
            fi_id = m.get('fi_id', 'N/A')
            current = m.get('current_assignee', 'N/A')
            expected = m.get('expected_assignee', 'N/A')
            report.append(f"{fi_id:<12} {current:<18} →  {expected}")

        report.append("")
        report.append("=" * 80)

        if common_current:
            report.append("TO FIX: Run validate-fi with --fix-from option:")
            report.append("")
            report.append(f"  python3 -m account_manager.cli validate-fi <query> \\")
            report.append(f"      --fix-from={common_current} --dry-run")
            report.append("")
            report.append("  # Remove --dry-run to apply changes")
        else:
            report.append("TO FIX: Run validate-fi with --fix option:")
            report.append("")
            report.append(f"  python3 -m account_manager.cli validate-fi <query> --fix --dry-run")
            report.append("")
            report.append("  # Remove --dry-run to apply changes")

        report.append("=" * 80)

        return "\n".join(report)

