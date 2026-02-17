#!/usr/bin/env python3
"""
Etrack Integration Module

This module provides functionality to:
1. Query etrack external references using esql
2. Get/update etrack assignee using eset command
"""

import subprocess
import os
import shutil
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ExternalReference:
    """Data class representing an external reference from etrack."""
    incident_no: str
    ext_src: str
    ext_ref_id: str  # e.g., FI-58985

    def __str__(self):
        return f"Incident {self.incident_no}: {self.ext_src} -> {self.ext_ref_id}"


@dataclass
class EtrackInfo:
    """Data class representing etrack incident info."""
    incident_no: str
    assignee: Optional[str]
    state: Optional[str]
    abstract: Optional[str]


class EtrackExecutor:
    """Execute etrack commands (esql, eset) and parse results."""

    def __init__(self, ssh_target: str = None):
        """
        Initialize Etrack executor.

        Args:
            ssh_target: SSH target in format 'user@host' (default: $RMTCMD_HOST env var)
        """
        self.ssh_target = ssh_target or os.getenv('RMTCMD_HOST')

        # Check if esql is available locally
        self.esql_local = shutil.which('esql')
        self.eset_local = shutil.which('eset')

        if not self.esql_local and not self.ssh_target:
            raise RuntimeError(
                "esql command not found locally and RMTCMD_HOST not set. "
                "Please install esql locally or set RMTCMD_HOST environment variable."
            )

    def _execute_command(self, cmd: str, use_shell: bool = True, timeout: int = 60, stdin_input: str = None) -> Optional[str]:
        """
        Execute a command locally or via SSH.

        Args:
            cmd: Command to execute
            use_shell: Whether to use shell execution
            timeout: Command timeout in seconds
            stdin_input: Optional input to pass via stdin

        Returns:
            Command output or None on error
        """
        try:
            if self.ssh_target and not self.esql_local:
                # Execute via SSH - pass stdin through echo pipe
                if stdin_input:
                    # Use printf to safely pass the query, avoiding shell escaping issues
                    ssh_cmd = f"ssh {self.ssh_target} '{cmd}'"
                    result = subprocess.run(
                        ssh_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        input=stdin_input
                    )
                else:
                    ssh_cmd = f"ssh {self.ssh_target} '{cmd}'"
                    result = subprocess.run(
                        ssh_cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
            else:
                # Execute locally - pass query via stdin
                if stdin_input:
                    result = subprocess.run(
                        cmd,
                        shell=use_shell,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        input=stdin_input
                    )
                else:
                    result = subprocess.run(
                        cmd,
                        shell=use_shell,
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )

            if result.returncode != 0:
                print(f"Warning: Command failed: {cmd}")
                print(f"Error: {result.stderr}")
                return None

            return result.stdout

        except subprocess.TimeoutExpired:
            print(f"Error: Command timed out: {cmd}")
            return None
        except Exception as e:
            print(f"Error executing command: {e}")
            return None

    def get_external_references(self, incident_no: str, ext_src: str = "TOOLS_AGILE", verbose: bool = False) -> List[ExternalReference]:
        """
        Get external references for an etrack incident.

        Uses esql to query external_reference table where ext_src matches.

        Args:
            incident_no: Etrack incident number
            ext_src: External source filter (default: TOOLS_AGILE for FI tickets)
            verbose: Print debug information

        Returns:
            List of ExternalReference objects
        """
        # Query external_reference table for this incident
        # Expected columns: incident, ext_src, ext_inc
        query = f"SELECT incident, ext_src, ext_inc FROM external_reference WHERE incident = {incident_no} AND ext_src = '{ext_src}'"

        # Pass query via stdin to avoid shell escaping issues
        cmd = "esql"

        if verbose:
            print(f"  [DEBUG] Running command: {cmd}")
            print(f"  [DEBUG] Query: {query}")

        output = self._execute_command(cmd, stdin_input=query)

        if verbose:
            print(f"  [DEBUG] Raw output:\n{output}")

        if not output:
            return []

        return self._parse_external_references(output, incident_no, verbose=verbose)

    def _parse_external_references(self, output: str, incident_no: str, verbose: bool = False) -> List[ExternalReference]:
        """
        Parse esql output for external references.

        Args:
            output: Raw esql output
            incident_no: Incident number for reference
            verbose: Print debug information

        Returns:
            List of ExternalReference objects
        """
        references = []
        lines = output.strip().split('\n')

        if verbose:
            print(f"  [DEBUG] Parsing {len(lines)} lines")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip header lines
            if 'incident' in line.lower() and 'ext_src' in line.lower():
                if verbose:
                    print(f"  [DEBUG] Skipping header: {line}")
                continue
            if line.startswith('---') or line.startswith('==='):
                continue
            if 'rows selected' in line.lower() or 'row selected' in line.lower():
                continue

            if verbose:
                print(f"  [DEBUG] Processing line: {line}")

            # Parse tab or pipe separated values
            parts = re.split(r'[\t|]+', line)
            parts = [p.strip() for p in parts if p.strip()]

            if verbose:
                print(f"  [DEBUG] Parts: {parts}")

            if len(parts) >= 3:
                # Format: incident | ext_src | ext_ref_id
                ext_src = parts[1]
                ext_ref_id = parts[2]

                # Validate FI ID format if it's from TOOLS_AGILE
                if ext_src == 'TOOLS_AGILE' and re.match(r'^FI-\d+$', ext_ref_id):
                    references.append(ExternalReference(
                        incident_no=incident_no,
                        ext_src=ext_src,
                        ext_ref_id=ext_ref_id
                    ))
                    if verbose:
                        print(f"  [DEBUG] Found FI: {ext_ref_id}")
            elif len(parts) >= 1:
                # Maybe just the ext_ref_id or different column order
                for part in parts:
                    if re.match(r'^FI-\d+$', part):
                        references.append(ExternalReference(
                            incident_no=incident_no,
                            ext_src='TOOLS_AGILE',
                            ext_ref_id=part
                        ))
                        if verbose:
                            print(f"  [DEBUG] Found FI (single): {part}")

        return references

        return references

    def get_etrack_assignee(self, incident_no: str) -> Optional[str]:
        """
        Get current assignee for an etrack incident.

        Args:
            incident_no: Etrack incident number

        Returns:
            Current assignee username or None
        """
        query = f"SELECT assigned_to FROM incident WHERE incident = {incident_no}"
        output = self._execute_command("esql", stdin_input=query)

        if not output:
            return None

        # Parse output - skip headers
        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if 'assigned_to' in line.lower():
                continue
            if line.startswith('---') or line.startswith('==='):
                continue
            # First non-header line should be the username
            return line.strip()

        return None

    def get_etrack_assignees_batch(self, incident_nos: List[str], verbose: bool = False) -> Dict[str, Optional[str]]:
        """
        Get assignees for multiple etrack incidents in a single query.

        Args:
            incident_nos: List of Etrack incident numbers
            verbose: Print debug information

        Returns:
            Dict mapping incident_no -> assignee (or None if not found)
        """
        if not incident_nos:
            return {}

        # Build IN clause with batching (esql may have limits)
        results = {}
        batch_size = 50  # Process 50 incidents per query

        for i in range(0, len(incident_nos), batch_size):
            batch = incident_nos[i:i + batch_size]
            in_list = ','.join(batch)
            query = f"SELECT incident, assigned_to FROM incident WHERE incident IN ({in_list})"

            if verbose:
                print(f"  [DEBUG] Batch query for {len(batch)} incidents...")

            output = self._execute_command("esql", stdin_input=query)

            if not output:
                # Mark all as not found
                for inc in batch:
                    results[inc] = None
                continue

            # Parse output - expect "incident | assigned_to" format
            lines = output.strip().split('\n')
            found_incidents = set()

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if 'incident' in line.lower() and 'assigned_to' in line.lower():
                    continue
                if line.startswith('---') or line.startswith('==='):
                    continue

                # Parse incident and assignee from line
                parts = re.split(r'[\t|]+', line)
                parts = [p.strip() for p in parts if p.strip()]

                if len(parts) >= 2:
                    inc_no = parts[0].strip()
                    assignee = parts[1].strip()
                    results[inc_no] = assignee
                    found_incidents.add(inc_no)

            # Mark unfound incidents as None
            for inc in batch:
                if inc not in found_incidents:
                    results[inc] = None

        return results

    def assign_etrack(self, incident_no: str, user_name: str, dry_run: bool = False) -> bool:
        """
        Assign/reassign an etrack incident to a user.

        Uses: eset -o user_name incident_number

        Args:
            incident_no: Etrack incident number
            user_name: User to assign to (etrack_user_id)
            dry_run: If True, only show what would be done

        Returns:
            True if successful, False otherwise
        """
        cmd = f"eset -o {user_name} {incident_no}"

        if dry_run:
            print(f"  [DRY-RUN] Would execute: {cmd}")
            return True

        print(f"  Executing: {cmd}")
        output = self._execute_command(cmd)

        if output is not None:
            print(f"  + Etrack {incident_no} assigned to {user_name}")
            return True
        else:
            print(f"  X Failed to assign etrack {incident_no} to {user_name}")
            return False

    def get_etrack_info(self, incident_no: str) -> Optional[EtrackInfo]:
        """
        Get basic info about an etrack incident.

        Args:
            incident_no: Etrack incident number

        Returns:
            EtrackInfo object or None
        """
        query = f"SELECT incident, assigned_to, state, abstract FROM incident WHERE incident = {incident_no}"
        output = self._execute_command("esql", stdin_input=query)

        if not output:
            return None

        if not output:
            return None

        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if 'incident' in line.lower() and 'assigned_to' in line.lower():
                continue
            if line.startswith('---') or line.startswith('==='):
                continue

            # Parse the data line
            parts = re.split(r'[\t|]+', line)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) >= 2:
                return EtrackInfo(
                    incident_no=incident_no,
                    assignee=parts[1] if len(parts) > 1 else None,
                    state=parts[2] if len(parts) > 2 else None,
                    abstract=parts[3] if len(parts) > 3 else None
                )

        return None


class MockEtrackExecutor:
    """Mock Etrack executor for testing without actual etrack access."""

    def __init__(self, mock_data: Dict[str, Any] = None):
        """
        Initialize mock executor with optional test data.

        Args:
            mock_data: Dictionary with mock data for testing
        """
        self.mock_data = mock_data or {}
        # Default mock data
        self._default_refs = {
            '1234567': [ExternalReference('1234567', 'TOOLS_AGILE', 'FI-10001')],
            '1234568': [ExternalReference('1234568', 'TOOLS_AGILE', 'FI-10002')],
        }
        self._default_assignees = {
            '1234567': 'user_one',
            '1234568': 'user_two',
        }

    def get_external_references(self, incident_no: str, ext_src: str = "TOOLS_AGILE", verbose: bool = False) -> List[ExternalReference]:
        """Return mock external references."""
        if 'external_refs' in self.mock_data:
            return self.mock_data['external_refs'].get(incident_no, [])
        return self._default_refs.get(incident_no, [])

    def get_etrack_assignee(self, incident_no: str) -> Optional[str]:
        """Return mock assignee."""
        if 'assignees' in self.mock_data:
            return self.mock_data['assignees'].get(incident_no)
        return self._default_assignees.get(incident_no)

    def get_etrack_assignees_batch(self, incident_nos: List[str], verbose: bool = False) -> Dict[str, Optional[str]]:
        """Return mock assignees for batch lookup."""
        results = {}
        for inc in incident_nos:
            results[inc] = self.get_etrack_assignee(inc)
        return results

    def assign_etrack(self, incident_no: str, user_name: str, dry_run: bool = False) -> bool:
        """Mock etrack assignment."""
        action = "[DRY-RUN] Would assign" if dry_run else "Mock assigned"
        print(f"  {action}: Etrack {incident_no} to {user_name}")
        return True

    def get_etrack_info(self, incident_no: str) -> Optional[EtrackInfo]:
        """Return mock etrack info."""
        assignee = self.get_etrack_assignee(incident_no)
        if assignee:
            return EtrackInfo(
                incident_no=incident_no,
                assignee=assignee,
                state='OPEN',
                abstract='Mock incident'
            )
        return None
