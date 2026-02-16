"""
ESQL Query Executor - Execute and parse esql queries
"""

import subprocess
import os
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re


@dataclass
class FIRecord:
    """Represents a single FI record from esql output"""
    incident_no: str
    etrack_user_id: str
    who_added_fi: str
    fi_ids: List[str]  # List of FI IDs (e.g., ['FI-59131'] or ['FI-58985', 'FI-60908'])

    def __str__(self):
        fi_list = ', '.join(self.fi_ids)
        return f"Incident {self.incident_no}: {self.etrack_user_id} | Added by: {self.who_added_fi} | FIs: {fi_list}"


class EsqlExecutor:
    """Execute esql queries and parse results"""

    def __init__(self, esql_command: str = None, ssh_target: str = None):
        """
        Initialize ESQL executor

        Args:
            esql_command: Path to esql command or None for auto-detect
            ssh_target: SSH target in format 'user@host' (default: $RMTCMD_HOST env var)
        """
        if esql_command:
            self.esql_command = esql_command
            self.use_ssh = False
        else:
            # Try to find local esql
            local_esql = shutil.which('esql')
            if local_esql:
                self.esql_command = local_esql
                self.use_ssh = False
            else:
                # Use SSH-based esql
                self.use_ssh = True
                self.ssh_target = ssh_target or os.getenv('RMTCMD_HOST')

                if not self.ssh_target:
                    raise ValueError(
                        "esql not found locally and RMTCMD_HOST environment variable not set. "
                        "Either install esql locally or set RMTCMD_HOST (format: user@host) for remote execution."
                    )

                self.esql_command = f"ssh {self.ssh_target} esql"

    def execute_query(self, query_name: str, timeout: int = 300) -> str:
        """
        Execute esql query

        Args:
            query_name: Name of the query to execute
            timeout: Command timeout in seconds (default: 300)

        Returns:
            Raw output from esql command

        Raises:
            subprocess.TimeoutExpired: If command times out
            subprocess.CalledProcessError: If command fails
            FileNotFoundError: If esql command not found
        """
        try:
            if self.use_ssh:
                # Use shell=True for SSH command
                cmd = f"{self.esql_command} -r {query_name}"
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=True
                )
            else:
                # Use list for local command
                cmd = [self.esql_command, '-r', query_name]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=True
                )
            return result.stdout

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"esql query '{query_name}' timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"esql query '{query_name}' failed: {e.stderr}")
        except FileNotFoundError:
            raise FileNotFoundError(f"esql command not found: {self.esql_command}")

    def parse_output(self, raw_output: str) -> List[FIRecord]:
        """
        Parse esql output into FIRecord objects, deduplicating by incident_no + etrack_user_id

        Expected format (tab-separated):
        incident_no    etrack_user_id    who_added_fi    FI-IDs

        Example:
        1234567	user_one	user_two	FI-10001
        1234568	user_three	user_four	FI-10002, FI-10003

        Note: Multiple rows may exist for same incident (different who_added_fi).
              These are deduplicated, combining all unique FI IDs.

        Args:
            raw_output: Raw output from esql command

        Returns:
            List of FIRecord objects (deduplicated by incident_no + etrack_user_id)
        """
        # Use dict to deduplicate by (incident_no, etrack_user_id)
        # Key: (incident_no, etrack_user_id) -> {fi_ids: set, who_added_fi: list}
        record_map = {}
        lines = raw_output.strip().split('\n')

        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue

            # Split by tab
            parts = line.split('\t')

            if len(parts) < 4:
                print(f"Warning: Line {line_num} has insufficient fields, skipping: {line}")
                continue

            incident_no = parts[0].strip()
            etrack_user_id = parts[1].strip()
            who_added_fi = parts[2].strip()
            fi_ids_str = parts[3].strip()

            # Skip records with invalid etrack_user_id (placeholder values)
            if not etrack_user_id or etrack_user_id == '-' or etrack_user_id == 'N/A':
                print(f"Warning: Line {line_num} has invalid etrack_user_id '{etrack_user_id}', skipping")
                continue

            # Parse FI IDs (comma-separated)
            fi_ids = [fi.strip() for fi in fi_ids_str.split(',')]

            # Validate FI ID format (FI-XXXXX)
            valid_fi_ids = []
            for fi_id in fi_ids:
                if re.match(r'^FI-\d+$', fi_id):
                    valid_fi_ids.append(fi_id)
                else:
                    print(f"Warning: Invalid FI ID format '{fi_id}' in line {line_num}, skipping")

            if valid_fi_ids:
                key = (incident_no, etrack_user_id)
                if key not in record_map:
                    record_map[key] = {
                        'fi_ids': set(),
                        'who_added_fi': []
                    }
                # Add FI IDs (using set to deduplicate)
                record_map[key]['fi_ids'].update(valid_fi_ids)
                # Track who added (for reference)
                if who_added_fi and who_added_fi not in record_map[key]['who_added_fi']:
                    record_map[key]['who_added_fi'].append(who_added_fi)

        # Convert map to list of FIRecords
        records = []
        for (incident_no, etrack_user_id), data in record_map.items():
            record = FIRecord(
                incident_no=incident_no,
                etrack_user_id=etrack_user_id,
                who_added_fi=', '.join(data['who_added_fi']),  # Combine all who added
                fi_ids=sorted(list(data['fi_ids']))  # Sorted list of unique FI IDs
            )
            records.append(record)

        return records

    def execute_and_parse(self, query_name: str, timeout: int = 300) -> List[FIRecord]:
        """
        Execute query and parse results in one call

        Args:
            query_name: Name of the query to execute
            timeout: Command timeout in seconds

        Returns:
            List of FIRecord objects
        """
        raw_output = self.execute_query(query_name, timeout)
        return self.parse_output(raw_output)

    def execute_raw_query(self, sql: str, timeout: int = 300) -> str:
        """
        Execute raw SQL query via esql using stdin

        Args:
            sql: Raw SQL query string
            timeout: Command timeout in seconds

        Returns:
            Raw output from esql command
        """
        try:
            if self.use_ssh:
                # Execute via SSH, passing SQL through stdin
                cmd = f"ssh {self.ssh_target} esql"
            else:
                cmd = self.esql_command

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=sql,
                check=True
            )
            return result.stdout

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"esql raw query timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"esql raw query failed: {e.stderr}")
        except FileNotFoundError:
            raise FileNotFoundError(f"esql command not found: {self.esql_command}")

    def fetch_incident_by_id(self, incident_no: str, timeout: int = 60) -> List[FIRecord]:
        """
        Fetch FI records for a specific incident number

        Args:
            incident_no: The etrack incident number
            timeout: Command timeout in seconds

        Returns:
            List of FIRecord objects for that incident
        """
        # Step 1: Get incident assignee
        assignee_sql = f"SELECT incident, assigned_to FROM incident WHERE incident = {incident_no}"
        assignee_output = self.execute_raw_query(assignee_sql, timeout)
        
        # Parse assignee
        assignee = None
        for line in assignee_output.strip().split('\n'):
            line = line.strip()
            if not line or 'assigned_to' in line.lower() or line.startswith('---'):
                continue
            parts = line.split('\t')
            if len(parts) >= 2:
                assignee = parts[1].strip()
                break
        
        if not assignee:
            return []
        
        # Step 2: Get FI links from external_reference table
        fi_sql = f"SELECT incident, ext_src, ext_inc FROM external_reference WHERE incident = {incident_no} AND ext_src = 'TOOLS_AGILE'"
        fi_output = self.execute_raw_query(fi_sql, timeout)
        
        # Parse FI IDs
        fi_ids = []
        for line in fi_output.strip().split('\n'):
            line = line.strip()
            if not line or 'ext_src' in line.lower() or line.startswith('---'):
                continue
            parts = re.split(r'[\t|]+', line)
            parts = [p.strip() for p in parts if p.strip()]
            for part in parts:
                if re.match(r'^FI-\d+$', part):
                    fi_ids.append(part)
        
        if not fi_ids:
            return []
        
        # Create FIRecord
        return [FIRecord(
            incident_no=incident_no,
            etrack_user_id=assignee,
            who_added_fi='(unknown)',
            fi_ids=sorted(fi_ids)
        )]

    def fetch_by_fi_id(self, fi_id: str, timeout: int = 60) -> List[FIRecord]:
        """
        Fetch FI records for a specific FI ID (e.g., FI-59131)

        Args:
            fi_id: The FI ID (e.g., FI-59131 or just 59131)
            timeout: Command timeout in seconds

        Returns:
            List of FIRecord objects for incidents linked to that FI
        """
        # Normalize FI ID format
        if not fi_id.startswith('FI-'):
            fi_id = f'FI-{fi_id}'

        # Step 1: Find incident(s) linked to this FI
        incident_sql = f"SELECT incident, ext_src, ext_inc FROM external_reference WHERE ext_src = 'TOOLS_AGILE' AND ext_inc = '{fi_id}'"
        incident_output = self.execute_raw_query(incident_sql, timeout)
        
        # Parse incident numbers
        incident_nos = []
        for line in incident_output.strip().split('\n'):
            line = line.strip()
            if not line or 'ext_src' in line.lower() or line.startswith('---'):
                continue
            parts = re.split(r'[\t|]+', line)
            parts = [p.strip() for p in parts if p.strip()]
            if parts and parts[0].isdigit():
                incident_nos.append(parts[0])
        
        if not incident_nos:
            return []
        
        # Step 2: Get assignee for each incident
        records = []
        for inc_no in incident_nos:
            assignee_sql = f"SELECT incident, assigned_to FROM incident WHERE incident = {inc_no}"
            assignee_output = self.execute_raw_query(assignee_sql, timeout)
            
            assignee = None
            for line in assignee_output.strip().split('\n'):
                line = line.strip()
                if not line or 'assigned_to' in line.lower() or line.startswith('---'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 2:
                    assignee = parts[1].strip()
                    break
            
            if assignee:
                records.append(FIRecord(
                    incident_no=inc_no,
                    etrack_user_id=assignee,
                    who_added_fi='(unknown)',
                    fi_ids=[fi_id]
                ))
        
        return records

    def parse_from_file(self, filename: str) -> List[FIRecord]:
        """
        Parse esql output from a file

        Args:
            filename: Path to file containing esql output

        Returns:
            List of FIRecord objects
        """
        with open(filename, 'r') as f:
            content = f.read()
        return self.parse_output(content)

    def group_by_incident(self, records: List[FIRecord]) -> Dict[str, List[FIRecord]]:
        """
        Group FI records by incident number

        Args:
            records: List of FIRecord objects

        Returns:
            Dictionary mapping incident_no to list of records
        """
        grouped = {}
        for record in records:
            if record.incident_no not in grouped:
                grouped[record.incident_no] = []
            grouped[record.incident_no].append(record)
        return grouped

    def get_unique_fi_ids(self, records: List[FIRecord]) -> List[str]:
        """
        Get list of unique FI IDs from records

        Args:
            records: List of FIRecord objects

        Returns:
            Sorted list of unique FI IDs
        """
        fi_ids = set()
        for record in records:
            fi_ids.update(record.fi_ids)
        return sorted(fi_ids)

    def get_statistics(self, records: List[FIRecord]) -> Dict[str, Any]:
        """
        Get statistics about the records

        Args:
            records: List of FIRecord objects

        Returns:
            Dictionary with statistics
        """
        if not records:
            return {
                'total_records': 0,
                'unique_incidents': 0,
                'unique_fi_ids': 0,
                'unique_etrack_users': 0,
                'unique_fi_adders': 0
            }

        incidents = set(r.incident_no for r in records)
        fi_ids = set()
        for r in records:
            fi_ids.update(r.fi_ids)
        etrack_users = set(r.etrack_user_id for r in records)
        fi_adders = set(r.who_added_fi for r in records)

        return {
            'total_records': len(records),
            'unique_incidents': len(incidents),
            'unique_fi_ids': len(fi_ids),
            'unique_etrack_users': len(etrack_users),
            'unique_fi_adders': len(fi_adders)
        }


def print_records_table(records: List[FIRecord], max_rows: Optional[int] = None):
    """
    Print FI records in a formatted table

    Args:
        records: List of FIRecord objects
        max_rows: Maximum number of rows to display (None for all)
    """
    if not records:
        print("No records to display")
        return

    display_records = records[:max_rows] if max_rows else records

    print("\n" + "=" * 100)
    print(f"{'Incident':<12} {'Etrack User':<20} {'Added By':<20} {'FI IDs':<40}")
    print("=" * 100)

    for record in display_records:
        fi_list = ', '.join(record.fi_ids)
        print(f"{record.incident_no:<12} {record.etrack_user_id:<20} {record.who_added_fi:<20} {fi_list:<40}")

    if max_rows and len(records) > max_rows:
        print(f"\n... and {len(records) - max_rows} more records")

    print("=" * 100)
